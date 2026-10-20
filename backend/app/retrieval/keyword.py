"""临时关键词检索器（P1 将被 Chroma 向量检索替换）。

为什么先做这个：
- 教学引擎需要一个**真实**的检索结果作为输入，否则演示里的引用就是编的；
- 它只依赖标准库，可以先把整条链路跑通；
- 对外契约与将来的向量检索一致，替换时引擎和 API 都不用改。

明确的能力边界：这是**字面匹配**，不具备语义理解，命中率低于向量检索。

两个降噪手段：
1. 按问题分类路由到对应课程文档（这是 P1 用 Chroma `where` 做元数据过滤的雏形）；
2. 只保留 IDF 达到下限的查询词，避免「什么」「报错」这类通用词让任何问题都命中。
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.core.config import PROJECT_ROOT
from app.teaching.types import ProblemCategory, RetrievedChunk

DEFAULT_SAMPLES_DIR = PROJECT_ROOT / "backend" / "data" / "samples"
IDF_FLOOR = 2.0

# 中文虚词与疑问词：它们在任何文档里都会出现，不能作为相关性的证据
STOPWORDS: frozenset[str] = frozenset(
    {
        "什么", "是什", "么是", "怎么", "么样", "怎样", "如何", "为什", "哪些", "哪个",
        "是否", "能否", "可以", "一下", "这个", "那个", "这些", "那些", "我们", "你们",
        "他们", "它们", "它的", "的是", "了吗", "时候", "这种", "那种", "如果", "因为",
        "所以", "但是", "而且", "然后", "还是", "就是", "一个", "一些", "这样", "那样",
        "的", "了", "是", "在", "和", "与", "或", "也", "就", "都", "很", "被", "把",
        "让", "给", "对", "从", "到", "会", "能", "要", "有", "我", "你", "他", "它",
        "这", "那",
    }
)

# 分类 -> 对应示例文档（P1 换成 metadata filter）
CATEGORY_DOCS: dict[ProblemCategory, tuple[str, ...]] = {
    ProblemCategory.error: ("python_errors.md",),
    ProblemCategory.sql: ("sql_basics.md",),
    ProblemCategory.web: ("web_debug.md",),
}

_CJK_RUN = re.compile(r"[\u4e00-\u9fff]+")
_ASCII_WORD = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]{1,}")


@dataclass(frozen=True)
class Paragraph:
    doc_name: str
    index: int
    heading: str
    text: str


def tokenize(text: str) -> set[str]:
    """中文按二元组切分，英文按单词切分，都转小写。"""
    lowered = text.lower()
    tokens: set[str] = {word for word in _ASCII_WORD.findall(lowered)}
    for run in _CJK_RUN.findall(lowered):
        if len(run) == 1:
            tokens.add(run)
            continue
        for position in range(len(run) - 1):
            tokens.add(run[position : position + 2])
    return tokens


def _parse_markdown(path: Path) -> list[Paragraph]:
    text = path.read_text(encoding="utf-8")
    paragraphs: list[Paragraph] = []

    heading = ""
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer
        if not buffer:
            return
        body = " ".join(buffer).strip()
        if body:
            paragraphs.append(
                Paragraph(
                    doc_name=path.name,
                    index=len(paragraphs) + 1,
                    heading=heading,
                    text=body,
                )
            )
        buffer = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("#"):
            flush()
            heading = line.lstrip("#").strip()
            continue
        if not line:
            flush()
            continue
        buffer.append(line)
    flush()
    return paragraphs


def _load_directory(directory: Path) -> tuple[Paragraph, ...]:
    if not directory.exists():
        return ()
    paragraphs: list[Paragraph] = []
    for path in sorted(directory.glob("*.md")):
        paragraphs.extend(_parse_markdown(path))
    return tuple(paragraphs)


class KeywordRetriever:
    """IDF 加权的关键词检索；分数 ∈ [0, 1]。"""

    def __init__(self, samples_dir: Path | None = None) -> None:
        self.samples_dir = samples_dir or DEFAULT_SAMPLES_DIR
        paragraphs = _load_directory(self.samples_dir)

        document_frequency: dict[str, int] = {}
        entries: list[tuple[Paragraph, frozenset[str]]] = []
        for paragraph in paragraphs:
            tokens = frozenset(tokenize(paragraph.text + " " + paragraph.heading))
            entries.append((paragraph, tokens))
            for token in tokens:
                document_frequency[token] = document_frequency.get(token, 0) + 1

        self._entries = tuple(entries)
        self._df = document_frequency
        self._total = max(1, len(entries))

    def _idf(self, token: str) -> float:
        frequency = self._df.get(token, 0)
        return math.log((self._total + 1) / (frequency + 1)) + 1.0

    def content_tokens(self, text: str) -> set[str]:
        """只保留有区分度的词；虚词、疑问词和 OOV 词的处理都在这里。"""
        return {
            token
            for token in tokenize(text)
            if token not in STOPWORDS and self._idf(token) >= IDF_FLOOR
        }

    @property
    def document_count(self) -> int:
        return len({paragraph.doc_name for paragraph, _ in self._entries})

    @property
    def paragraph_count(self) -> int:
        return len(self._entries)

    def search(
        self,
        query: str,
        top_k: int = 4,
        min_score: float = 0.01,
        category: ProblemCategory | None = None,
    ) -> list[RetrievedChunk]:
        query_tokens = self.content_tokens(query)
        if not query_tokens or not self._entries:
            return []

        entries = self._entries
        if category in CATEGORY_DOCS:
            allowed = set(CATEGORY_DOCS[category])
            routed = tuple(entry for entry in entries if entry[0].doc_name in allowed)
            if routed:
                entries = routed

        total_weight = sum(self._idf(token) for token in query_tokens) or 1.0

        scored: list[tuple[float, Paragraph]] = []
        for paragraph, paragraph_tokens in entries:
            matched = query_tokens & paragraph_tokens
            if not matched:
                continue

            gain = sum(self._idf(token) for token in matched)
            score = gain / total_weight
            # 命中词越多，越可能是真正相关的段落
            score = min(1.0, score * (1 + 0.08 * (len(matched) - 1)))

            if query_tokens & tokenize(paragraph.heading):
                score = min(1.0, score + 0.1)

            if score >= min_score:
                scored.append((round(score, 4), paragraph))

        scored.sort(key=lambda item: (-item[0], item[1].doc_name, item[1].index))

        return [
            RetrievedChunk(
                chunk_id=f"{paragraph.doc_name}#p{paragraph.index}",
                doc_name=paragraph.doc_name,
                text=paragraph.text,
                score=score,
                paragraph_from=paragraph.index,
                heading=paragraph.heading or None,
            )
            for score, paragraph in scored[:top_k]
        ]


@lru_cache(maxsize=1)
def get_retriever() -> KeywordRetriever:
    return KeywordRetriever()

