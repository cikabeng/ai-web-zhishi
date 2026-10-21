"""文本分块：按段落聚合到目标长度，代码块与句子边界不被硬切。"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.library.parsers import Block

DEFAULT_CHUNK_CHARS = 500
DEFAULT_OVERLAP = 80
MAX_CHUNK_CHARS = 800

_SENTENCE_END = re.compile(r"(?<=[。！？.!?；;])")


@dataclass
class Chunk:
    text: str
    page: int | None
    heading: str
    ordinal: int


def _split_long(text: str, limit: int) -> list[str]:
    """超长文本按句子切，实在没有句子就按长度切。"""
    if len(text) <= limit:
        return [text]

    sentences = [item for item in _SENTENCE_END.split(text) if item.strip()]
    pieces: list[str] = []
    current = ""
    for sentence in sentences:
        if len(current) + len(sentence) <= limit:
            current += sentence
            continue
        if current:
            pieces.append(current)
        while len(sentence) > limit:
            pieces.append(sentence[:limit])
            sentence = sentence[limit:]
        current = sentence
    if current:
        pieces.append(current)
    return pieces


def chunk_blocks(
    blocks: list[Block],
    chunk_chars: int = DEFAULT_CHUNK_CHARS,
    overlap: int = DEFAULT_OVERLAP,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    buffer = ""
    buffer_page: int | None = None
    buffer_heading = ""
    ordinal = 0

    def flush() -> None:
        nonlocal buffer, buffer_page, buffer_heading, ordinal
        body = buffer.strip()
        if not body:
            return
        for piece in _split_long(body, MAX_CHUNK_CHARS):
            ordinal += 1
            chunks.append(
                Chunk(
                    text=piece.strip(),
                    page=buffer_page,
                    heading=buffer_heading,
                    ordinal=ordinal,
                )
            )
        buffer = ""
        buffer_page = None

    for block in blocks:
        text = block.text.strip()
        if not text:
            continue
        if not buffer:
            buffer_page = block.page
            buffer_heading = block.heading

        if len(buffer) + len(text) + 1 <= chunk_chars:
            buffer += ("\n" if buffer else "") + text
            continue

        flush()
        # 新块带一点上一块的结尾做重叠，但必须从句子边界开始，
        # 否则引用片段会出现"ect is not callable"这种半句开头
        tail = ""
        if chunks and overlap:
            previous = chunks[-1].text
            window_start = max(0, len(previous) - overlap)
            boundary = max((previous.rfind(mark, window_start) for mark in "。！？.!?；;"), default=-1)
            if boundary >= 0:
                window_start = boundary + 1
            tail = previous[window_start:].strip()

        buffer = (tail + "\n" + text) if tail else text
        buffer_page = block.page
        buffer_heading = block.heading

    flush()
    return chunks
