"""检索服务：优先查知识库（Chroma 哈希向量 + 字面混合），不足时回落到示例资料的词面检索。"""

from __future__ import annotations

from functools import lru_cache

from app.library.index import LibraryIndex
from app.retrieval.keyword import KeywordRetriever
from app.teaching.types import ProblemCategory, RetrievedChunk


class CompositeRetriever:
    def __init__(self) -> None:
        self.library = LibraryIndex()
        self.keyword = KeywordRetriever()

    def search(
        self,
        query: str,
        top_k: int = 4,
        category: ProblemCategory | None = None,
        min_score: float = 0.01,
    ) -> list[RetrievedChunk]:
        hits: list[RetrievedChunk] = []
        try:
            hits = self.library.search(query, top_k=top_k, min_score=min_score)
        except Exception:
            hits = []

        if len(hits) < top_k:
            hits.extend(
                self.keyword.search(query, top_k=top_k - len(hits), category=category)
            )

        seen: set[tuple[str, str]] = set()
        merged: list[RetrievedChunk] = []
        for hit in sorted(hits, key=lambda item: item.score, reverse=True):
            key = (hit.doc_name, hit.text[:60])
            if key in seen:
                continue
            seen.add(key)
            merged.append(hit)
        return merged[:top_k]


@lru_cache(maxsize=1)
def get_retriever() -> CompositeRetriever:
    return CompositeRetriever()
