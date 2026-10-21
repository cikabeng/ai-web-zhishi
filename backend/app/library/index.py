"""Chroma 持久化索引（离线哈希向量 + 字面覆盖率混合打分）。"""

from __future__ import annotations

import threading
from pathlib import Path

from app.core.config import get_settings
from app.library.chunker import Chunk
from app.library.embeddings import embed_batch, embed_text, lexical_coverage
from app.teaching.types import RetrievedChunk

COLLECTION_NAME = "library_chunks_v1"
VECTOR_WEIGHT = 0.75
LEXICAL_WEIGHT = 0.25


class LibraryIndex:
    """对外只暴露 add / delete / search / count 四个动作。"""

    _client_lock = threading.Lock()
    _clients: dict[str, object] = {}

    def __init__(self, path: Path | None = None) -> None:
        settings = get_settings()
        self.path = Path(path or (settings.storage_dir / "chroma"))
        self.path.mkdir(parents=True, exist_ok=True)

    def _collection(self):
        key = str(self.path)
        with self._client_lock:
            if key not in self._clients:
                import chromadb
                from chromadb.config import Settings as ChromaSettings

                client = chromadb.PersistentClient(
                    path=key,
                    settings=ChromaSettings(anonymized_telemetry=False, allow_reset=True),
                )
                self._clients[key] = client.get_or_create_collection(
                    name=COLLECTION_NAME,
                    metadata={"hnsw:space": "cosine"},
                )
        return self._clients[key]

    def add(self, doc_id: str, doc_name: str, chunks: list[Chunk]) -> None:
        if not chunks:
            return
        collection = self._collection()
        ids = [f"{doc_id}:{chunk.ordinal}" for chunk in chunks]
        documents = [chunk.text for chunk in chunks]
        metadatas = [
            {
                "doc_id": doc_id,
                "doc_name": doc_name,
                "page": chunk.page if chunk.page is not None else -1,
                "heading": chunk.heading or "",
                "ordinal": chunk.ordinal,
            }
            for chunk in chunks
        ]
        collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embed_batch(documents),
        )

    def delete(self, doc_id: str) -> None:
        try:
            self._collection().delete(where={"doc_id": doc_id})
        except Exception:  # 索引为空时删除会抛错，忽略即可
            return

    def count(self) -> int:
        try:
            return int(self._collection().count())
        except Exception:
            return 0

    def get_chunks(self, doc_id: str, limit: int = 5) -> list[dict]:
        """分块预览（只读，用于核对解析质量）。"""
        try:
            result = self._collection().get(
                where={"doc_id": doc_id},
                limit=limit,
                include=["documents", "metadatas"],
            )
        except Exception:
            return []
        documents = result.get("documents") or []
        metadatas = result.get("metadatas") or []
        return [
            {
                "text": text,
                "page": int(metadata.get("page", -1)),
                "heading": metadata.get("heading") or "",
                "ordinal": int(metadata.get("ordinal", 0)),
            }
            for text, metadata in zip(documents, metadatas)
        ]

    def search(self, query: str, top_k: int = 6, min_score: float = 0.0) -> list[RetrievedChunk]:
        if not query.strip():
            return []
        collection = self._collection()
        if self.count() == 0:
            return []

        result = collection.query(
            query_embeddings=[embed_text(query)],
            n_results=max(top_k * 2, top_k),
            include=["documents", "metadatas", "distances"],
        )

        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]

        hits: list[RetrievedChunk] = []
        for text, metadata, distance in zip(documents, metadatas, distances):
            cosine = max(0.0, 1.0 - float(distance))
            lexical = lexical_coverage(query, text)
            score = round(VECTOR_WEIGHT * cosine + LEXICAL_WEIGHT * lexical, 4)
            if score < min_score:
                continue

            page = int(metadata.get("page", -1))
            hits.append(
                RetrievedChunk(
                    chunk_id=f"{metadata.get('doc_id')}:{metadata.get('ordinal')}",
                    doc_name=str(metadata.get("doc_name", "未知文档")),
                    text=text,
                    score=score,
                    page_from=page if page > 0 else None,
                    paragraph_from=None if page > 0 else int(metadata.get("ordinal", 0)),
                    heading=str(metadata.get("heading") or "") or None,
                )
            )

        hits.sort(key=lambda item: item.score, reverse=True)
        return hits[:top_k]
