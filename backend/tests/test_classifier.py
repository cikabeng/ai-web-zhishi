"""问题分类器测试：六类问题、用户覆盖、低置信度兜底。"""

from __future__ import annotations

from app.teaching.classifier import classify
from app.teaching.types import ProblemCategory

CASES: list[tuple[str, ProblemCategory]] = [
    ("TypeError: 'NoneType' object is not subscriptable，第 12 行报错", ProblemCategory.error),
    ("SQL 里 WHERE class_id = NULL 为什么查不出数据？", ProblemCategory.sql),
    ("Vue 页面请求接口时报 CORS 错误怎么处理？", ProblemCategory.web),
    ("实验三的步骤是什么，怎么运行？", ProblemCategory.experiment),
    ("这个作业要求的功能点我不会，帮我写一下完整代码", ProblemCategory.assignment),
    ("闭包是什么？和普通函数有什么区别？", ProblemCategory.concept),
]


def test_six_categories() -> None:
    for question, expected in CASES:
        result = classify(question)
        assert result.category == expected, f"{question} 被分到了 {result.category}"
        assert result.source == "auto"
        assert 0.0 <= result.confidence <= 1.0


def test_user_override_wins() -> None:
    result = classify("TypeError 报错", category=ProblemCategory.web)
    assert result.category == ProblemCategory.web
    assert result.source == "user"
    assert result.confidence == 1.0


def test_low_confidence_fallback() -> None:
    result = classify("你好")
    assert result.category == ProblemCategory.concept
    assert result.confidence < 0.5
    assert result.signals


def test_error_signal_beats_retrieval_text() -> None:
    # 检索到的资料是 SQL 的，但问题本身是 Python 报错，不能被资料带偏
    result = classify(
        "Traceback (most recent call last): TypeError: 'NoneType' object is not subscriptable",
        retrieval_text="SELECT * FROM students WHERE class_id IS NULL",
    )
    assert result.category == ProblemCategory.error


def test_options_are_ranked() -> None:
    result = classify("SQL 查询报错：Unknown column 'class_id'", retrieval_text="数据库 SQL")
    assert result.options
    scores = [option.confidence for option in result.options]
    assert scores == sorted(scores, reverse=True)
