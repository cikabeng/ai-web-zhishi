"""知识库管理：文件落盘、元数据登记、解析入库与删除。

存储结构（都在 storage/library 下，已 gitignore）：
    registry.json          文档清单与状态
    files/<doc_id>.<ext>   原始文件
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import get_settings
from app.library.chunker import Chunk, chunk_blocks
from app.library.index import LibraryIndex
from app.library.parsers import SUPPORTED_EXT, Block, ParseError, parse_document


class LibraryError(Exception):
    def __init__(self, code: str, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class LibraryStore:
    def __init__(self, root: Path | None = None, index: LibraryIndex | None = None) -> None:
        settings = get_settings()
        self.root = Path(root or (settings.storage_dir / "library"))
        self.files_dir = self.root / "files"
        self.registry_path = self.root / "registry.json"
        self.index = index or LibraryIndex()
        self._lock = threading.Lock()
        self.files_dir.mkdir(parents=True, exist_ok=True)

    # ---------------- 元数据读写 ----------------

    def _load(self) -> dict:
        if not self.registry_path.exists():
            return {"documents": []}
        try:
            payload = json.loads(self.registry_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"documents": []}
        if "documents" not in payload:
            payload["documents"] = []
        return payload

    def _save(self, payload: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = self.registry_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.registry_path)

    # ---------------- 查询 ----------------

    def list_documents(self) -> list[dict]:
        documents = self._load()["documents"]
        return sorted(documents, key=lambda item: item.get("created_at", ""), reverse=True)

    def get(self, doc_id: str) -> dict | None:
        return next((item for item in self._load()["documents"] if item["id"] == doc_id), None)

    def stats(self) -> dict:
        documents = self._load()["documents"]
        indexed = [item for item in documents if item.get("status") == "indexed"]
        return {
            "documents": len(documents),
            "indexed": len(indexed),
            "failed": len([item for item in documents if item.get("status") == "failed"]),
            "chunks": sum(int(item.get("chunks", 0)) for item in documents),
            "chars": sum(int(item.get("chars", 0)) for item in documents),
            "status": "ready" if indexed else "not_initialized",
        }

    # ---------------- 写入 ----------------

    def add_document(self, filename: str, raw: bytes) -> tuple[dict, bool]:
        settings = get_settings()
        ext = Path(filename).suffix.lower().lstrip(".")
        if ext not in SUPPORTED_EXT:
            raise LibraryError(
                "unsupported_format",
                f"只支持 {'、'.join(sorted(SUPPORTED_EXT))} 格式，当前是 .{ext or '未知'}",
                415,
            )
        if not raw:
            raise LibraryError("empty_file", "上传的文件是空的", 400)
        if len(raw) > settings.upload_max_bytes:
            raise LibraryError(
                "too_large",
                f"文件大小 {len(raw) / 1024 / 1024:.1f} MB，超过上限 {settings.upload_max_mb} MB",
                413,
            )

        digest = hashlib.sha256(raw).hexdigest()
        with self._lock:
            payload = self._load()
            existing = next(
                (item for item in payload["documents"] if item.get("sha256") == digest),
                None,
            )
            if existing:
                return existing, True

            doc_id = f"d_{digest[:10]}"
            record = {
                "id": doc_id,
                "name": Path(filename).name,
                "ext": ext,
                "size": len(raw),
                "sha256": digest,
                "status": "parsing",
                "error": None,
                "pages": 0,
                "chunks": 0,
                "chars": 0,
                "created_at": _now(),
            }
            payload["documents"].append(record)
            self._save(payload)

            target = self.files_dir / f"{doc_id}.{ext}"
            target.write_bytes(raw)

        return self._parse_and_index(doc_id, target), False

    def _parse_and_index(self, doc_id: str, path: Path) -> dict:
        payload = self._load()
        record = next(item for item in payload["documents"] if item["id"] == doc_id)
        try:
            blocks: list[Block] = parse_document(path)
            chunks: list[Chunk] = chunk_blocks(blocks)
            if not chunks:
                raise ParseError("解析后没有可索引的文本")

            self.index.delete(doc_id)
            self.index.add(doc_id, record["name"], chunks)

            record.update(
                {
                    "status": "indexed",
                    "error": None,
                    "chunks": len(chunks),
                    "chars": sum(len(chunk.text) for chunk in chunks),
                    "pages": len({block.page for block in blocks if block.page}),
                }
            )
        except (ParseError, LibraryError) as exc:
            record.update({"status": "failed", "error": str(exc), "chunks": 0, "chars": 0})
        except Exception as exc:  # 索引写入失败等
            record.update({"status": "failed", "error": f"索引失败：{exc}", "chunks": 0, "chars": 0})

        with self._lock:
            latest = self._load()
            for index, item in enumerate(latest["documents"]):
                if item["id"] == doc_id:
                    latest["documents"][index] = record
                    break
            self._save(latest)
        return record

    def reindex(self, doc_id: str) -> dict:
        record = self.get(doc_id)
        if not record:
            raise LibraryError("not_found", "文档不存在", 404)

        path = self.files_dir / f"{doc_id}.{record['ext']}"
        if not path.exists():
            raise LibraryError("file_missing", "原始文件已丢失，请删除后重新上传", 409)

        with self._lock:
            payload = self._load()
            for item in payload["documents"]:
                if item["id"] == doc_id:
                    item.update({"status": "parsing", "error": None})
            self._save(payload)
        return self._parse_and_index(doc_id, path)

    def delete(self, doc_id: str) -> None:
        record = self.get(doc_id)
        if not record:
            raise LibraryError("not_found", "文档不存在", 404)

        self.index.delete(doc_id)
        path = self.files_dir / f"{doc_id}.{record['ext']}"
        if path.exists():
            path.unlink(missing_ok=True)

        with self._lock:
            payload = self._load()
            payload["documents"] = [item for item in payload["documents"] if item["id"] != doc_id]
            self._save(payload)


def get_store() -> LibraryStore:
    return LibraryStore()
