"""文档解析：PDF / DOCX / TXT / Markdown → 带页码或段落的文本块。

原则：拿不到的元数据就留空，绝不编造页码。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

SUPPORTED_EXT = {"pdf", "docx", "txt", "md"}


class ParseError(Exception):
    """解析失败，消息会直接展示给用户。"""


@dataclass
class Block:
    text: str
    page: int | None = None
    heading: str = ""


def _clean(text: str) -> str:
    text = text.replace("\u00a0", " ").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _heading_from_line(line: str) -> str:
    candidate = line.strip()
    if 0 < len(candidate) <= 40 and not candidate.endswith(("。", ".", "，", ",", "；", ";")):
        return candidate
    return ""


def parse_pdf(path: Path) -> list[Block]:
    try:
        import pymupdf  # type: ignore
    except ImportError:  # pragma: no cover - 兼容旧包名
        try:
            import fitz as pymupdf  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise ParseError("PDF 解析组件不可用，请先安装 pymupdf") from exc

    blocks: list[Block] = []
    try:
        document = pymupdf.open(path)
    except Exception as exc:
        raise ParseError(f"PDF 打开失败：{exc}") from exc

    try:
        if document.needs_pass:
            raise ParseError("PDF 已加密，无法解析")
        for index, page in enumerate(document, start=1):
            text = _clean(page.get_text("text") or "")
            if not text:
                continue
            heading = ""
            for line in text.splitlines():
                heading = _heading_from_line(line)
                if heading:
                    break
            blocks.append(Block(text=text, page=index, heading=heading))
    finally:
        document.close()

    if not blocks:
        raise ParseError("PDF 没有可提取的文本层（可能是扫描件，需要 OCR）")
    return blocks


def parse_docx(path: Path) -> list[Block]:
    try:
        from docx import Document
    except ImportError as exc:  # pragma: no cover
        raise ParseError("DOCX 解析组件不可用，请先安装 python-docx") from exc

    try:
        document = Document(str(path))
    except Exception as exc:
        raise ParseError(f"DOCX 打开失败：{exc}") from exc

    blocks: list[Block] = []
    heading = ""
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer
        text = _clean("\n".join(buffer))
        if text:
            blocks.append(Block(text=text, page=None, heading=heading))
        buffer = []

    for paragraph in document.paragraphs:
        content = paragraph.text.strip()
        if not content:
            continue
        style = (paragraph.style.name or "").lower() if paragraph.style is not None else ""
        if style.startswith("heading") or "标题" in style:
            flush()
            heading = content
            continue
        buffer.append(content)
    flush()

    if not blocks:
        raise ParseError("DOCX 中没有可提取的文字")
    return blocks


def parse_text_file(path: Path) -> list[Block]:
    raw: str | None = None
    for encoding in ("utf-8-sig", "utf-8", "gbk"):
        try:
            raw = path.read_text(encoding=encoding)
            break
        except UnicodeDecodeError:
            continue
    if raw is None:
        raise ParseError("文本编码无法识别（支持 UTF-8 / GBK）")

    text = _clean(raw)
    if not text:
        raise ParseError("文件内容为空")

    if path.suffix.lower() == ".md":
        blocks: list[Block] = []
        heading = ""
        buffer: list[str] = []

        def flush() -> None:
            nonlocal buffer
            body = _clean("\n".join(buffer))
            if body:
                blocks.append(Block(text=body, page=None, heading=heading))
            buffer = []

        for line in text.splitlines():
            if line.lstrip().startswith("#"):
                flush()
                heading = line.lstrip("#").strip()
                continue
            buffer.append(line)
        flush()
        return blocks or [Block(text=text)]

    return [Block(text=text)]


def parse_document(path: Path) -> list[Block]:
    ext = path.suffix.lower().lstrip(".")
    if ext == "pdf":
        return parse_pdf(path)
    if ext == "docx":
        return parse_docx(path)
    if ext in {"txt", "md"}:
        return parse_text_file(path)
    raise ParseError(f"不支持的文件类型：.{ext}")
