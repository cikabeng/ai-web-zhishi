"""临时关键词检索器测试。"""

from __future__ import annotations

from app.retrieval.keyword import KeywordRetriever, tokenize
from app.teaching.types import ProblemCategory


def test_tokenize_chinese_uses_bigrams() -> None:
    tokens = tokenize("报错信息")
    assert "报错" in tokens
    assert "信息" in tokens


def test_tokenize_keeps_english_identifiers() -> None:
    tokens = tokenize("TypeError occurs in get_student")
    assert "typeerror" in tokens
    assert "get_student" in tokens


def test_search_finds_python_error_doc() -> None:
    retriever = KeywordRetriever()
    hits = retriever.search("TypeError NoneType 报错 怎么排查", top_k=3)

    assert hits, "示例资料里应当能检索到 Python 报错相关内容"
    assert hits[0].doc_name == "python_errors.md"
    assert hits[0].paragraph_from is not None
    assert hits[0].chunk_id.startswith("python_errors.md#p")
    assert 0 < hits[0].score <= 1


def test_results_are_sorted_by_score() -> None:
    hits = KeywordRetriever().search("SQL NULL 查询", top_k=5)
    scores = [hit.score for hit in hits]
    assert scores == sorted(scores, reverse=True)


def test_empty_query_returns_empty() -> None:
    assert KeywordRetriever().search("", top_k=3) == []


def test_retriever_reports_counts() -> None:
    retriever = KeywordRetriever()
    assert retriever.document_count >= 3
    assert retriever.paragraph_count >= 10


def test_stopwords_are_not_content_tokens() -> None:
    retriever = KeywordRetriever()
    tokens = retriever.content_tokens("闭包是什么")
    assert "闭包" in tokens
    assert "什么" not in tokens
    assert "是什" not in tokens


def test_category_routing_prefers_matching_doc() -> None:
    retriever = KeywordRetriever()
    hits = retriever.search("NULL 比较为什么查不出数据", top_k=3, category=ProblemCategory.sql)
    assert hits
    assert all(hit.doc_name == "sql_basics.md" for hit in hits)


def test_out_of_scope_question_returns_nothing() -> None:
    retriever = KeywordRetriever()
    hits = retriever.search(
        "量子计算机会取代经典计算机吗？", top_k=3, category=ProblemCategory.concept
    )
    assert hits == []
