"""分块测试：长度、句子边界、页码与重叠。"""

from __future__ import annotations

from app.library.chunker import chunk_blocks
from app.library.parsers import Block


def test_short_block_single_chunk() -> None:
    chunks = chunk_blocks([Block(text="闭包是指函数内部定义的函数。", page=3)])
    assert len(chunks) == 1
    assert chunks[0].page == 3
    assert chunks[0].ordinal == 1


def test_long_text_is_split_within_limit() -> None:
    # 单块只在硬上限（800 字）处切分，这里构造超过上限的文本
    text = "这是一句测试用的话。" * 150
    chunks = chunk_blocks([Block(text=text, page=1)], chunk_chars=200)
    assert len(chunks) > 1
    assert all(len(chunk.text) <= 800 for chunk in chunks)


def test_overlap_starts_at_sentence_boundary() -> None:
    first = "第一段的内容到这里结束。" * 8
    second = "第二段是新的内容。" * 4
    chunks = chunk_blocks(
        [Block(text=first, page=1), Block(text=second, page=2)],
        chunk_chars=120,
        overlap=60,
    )
    assert len(chunks) >= 2
    # 第二块如果带重叠，必须从句子开头而不是半句开始
    for chunk in chunks[1:]:
        assert not chunk.text.startswith(("段", "容", "束")), chunk.text[:20]


def test_page_metadata_is_kept() -> None:
    chunks = chunk_blocks(
        [Block(text="第一页内容。", page=1), Block(text="第二页内容。", page=2)],
        chunk_chars=8,
    )
    pages = [chunk.page for chunk in chunks]
    assert pages == [1, 2]
