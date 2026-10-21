"""四级提示的格式与教学约束测试。

这些断言是"分层教学"这个卖点的底线：任何一条挂掉，说明功能退化了。
"""

from __future__ import annotations

import pytest

from app.teaching.engine import TeachingEngine
from app.teaching.guards import code_line_count, detect_complete_implementation
from app.teaching.types import (
    ProblemCategory,
    RetrievedChunk,
    StudentSubmission,
    TeachingMode,
    TeachingRequest,
)

QUESTION = "运行时报错：TypeError: 'NoneType' object is not subscriptable，info = get_student('李四') 之后 print(info['score']) 就挂了，怎么排查？"

CHUNKS = [
    RetrievedChunk(
        chunk_id="python_errors.md#p4",
        doc_name="python_errors.md",
        text="TypeError: 'NoneType' object is not subscriptable 的含义是：对一个 None 使用了方括号取值。",
        score=0.82,
        paragraph_from=4,
        heading="三、TypeError 与 NoneType 的关系",
    ),
    RetrievedChunk(
        chunk_id="python_errors.md#p2",
        doc_name="python_errors.md",
        text="Python 的函数如果执行完所有语句都没有遇到 return，会隐式返回 None。",
        score=0.55,
        paragraph_from=2,
        heading="二、函数没有 return 时会发生什么",
    ),
]

engine = TeachingEngine()


def make_request(**overrides) -> TeachingRequest:
    payload = {
        "question": QUESTION,
        # 层级机制用学习模式测试；引导模式的额外约束单独测
        "mode": TeachingMode.study,
        "current_level": 0,
        "target_level": 1,
        "retrieval": CHUNKS,
    }
    payload.update(overrides)
    return TeachingRequest(**payload)


def kinds(response) -> list[str]:
    return [block.kind for block in response.blocks]


# ---------------------------------------------------------------- L1


def test_level1_is_concept_only() -> None:
    response = engine.respond(make_request())

    assert response.level == 1
    assert response.level_name == "知识点提示"
    assert "explain" in kinds(response)
    assert "code" not in kinds(response), "L1 不允许出现代码块"
    assert response.citations, "有检索结果时必须给出引用"
    assert response.check_question.question
    assert response.check_question.purpose


def test_level1_citations_come_only_from_retrieval() -> None:
    response = engine.respond(make_request())
    allowed = {chunk.chunk_id for chunk in CHUNKS}
    assert {citation.chunk_id for citation in response.citations} <= allowed
    assert [citation.index for citation in response.citations] == list(
        range(1, len(response.citations) + 1)
    )


def test_level1_marks_missing_location_honestly() -> None:
    chunk = RetrievedChunk(chunk_id="x#p1", doc_name="x.md", text="没有页码也没有段落的资料", score=0.9)
    response = engine.respond(make_request(retrieval=[chunk]))
    assert response.citations[0].location == "未标注位置"


# ---------------------------------------------------------------- L2


def test_level2_is_steps_only() -> None:
    response = engine.respond(make_request(current_level=1, target_level=2))
    assert response.level == 2
    assert "steps" in kinds(response)
    assert "code" not in kinds(response), "L2 只给思路，不给代码"
    steps = next(block for block in response.blocks if block.kind == "steps")
    assert "1." in steps.content and "2." in steps.content


# ---------------------------------------------------------------- L3


def test_level3_snippet_is_short_and_incomplete() -> None:
    response = engine.respond(make_request(current_level=2, target_level=3))
    assert response.level == 3
    code = next(block for block in response.blocks if block.kind == "code")
    assert code_line_count(code.content) <= 6
    assert not detect_complete_implementation(code.content)
    assert "def " not in code.content, "局部示例不允许给出完整函数定义"
    assert "explain" in kinds(response)


# ---------------------------------------------------------------- L4


def test_level4_example_is_labelled_as_ai_generated() -> None:
    response = engine.respond(make_request(current_level=3, target_level=4))
    assert response.level == 4
    assert response.example_generated is True

    example = next(block for block in response.blocks if block.kind == "example")
    assert "AI 生成示例" in example.title
    assert example.meta.get("generated_by_ai") == "true"
    assert "非教材原文" in example.title + example.content
    assert "和你的问题相比" in example.content
    assert response.safety.get("example_label") == "AI 生成示例"


# ---------------------------------------------------------------- 升级约束


@pytest.mark.parametrize(
    ("current", "target", "expected", "clamped"),
    [
        (0, 1, 1, False),
        (0, 4, 1, True),
        (1, 4, 2, True),
        (2, 4, 3, True),
        (3, 4, 4, False),
        (4, 4, 4, False),
    ],
)
def test_only_one_level_up_per_step(current: int, target: int, expected: int, clamped: bool) -> None:
    response = engine.respond(make_request(current_level=current, target_level=target))
    assert response.level == expected
    assert response.clamped is clamped


def test_next_level_handles_last_level() -> None:
    at_four = engine.respond(make_request(current_level=3, target_level=4))
    assert at_four.next_level is None
    assert "continue" not in at_four.allowed_actions

    at_two = engine.respond(make_request(current_level=1, target_level=2))
    assert at_two.next_level == 3
    assert "continue" in at_two.allowed_actions


# ---------------------------------------------------------------- 资料不足


def test_insufficient_evidence_is_explicit() -> None:
    response = engine.respond(make_request(retrieval=[]))
    assert response.insufficient_evidence is True
    assert response.citations == []
    assert "limit" in kinds(response)
    text = " ".join(block.content for block in response.blocks)
    assert "没有检索到" in text


def test_low_score_chunks_are_filtered() -> None:
    weak = RetrievedChunk(chunk_id="weak#p1", doc_name="weak.md", text="几乎不相关", score=0.01)
    response = engine.respond(make_request(retrieval=[weak], min_evidence_score=0.5))
    assert response.insufficient_evidence is True


def test_default_threshold_rejects_weak_chunks() -> None:
    weak = RetrievedChunk(chunk_id="weak#p1", doc_name="weak.md", text="只是沾边", score=0.10)
    response = engine.respond(make_request(retrieval=[weak]))
    assert response.insufficient_evidence is True


def test_level4_still_marks_generated_when_evidence_missing() -> None:
    response = engine.respond(make_request(current_level=3, target_level=4, retrieval=[]))
    assert response.example_generated is True
    example = next(block for block in response.blocks if block.kind == "example")
    assert "AI 生成示例" in example.title


# ---------------------------------------------------------------- 换一种解释 / 模式


def test_rephrase_changes_wording_but_keeps_level() -> None:
    first = engine.respond(make_request(variant=0))
    again = engine.respond(make_request(variant=0, action="rephrase"))

    assert again.level == first.level
    first_text = next(block for block in first.blocks if block.kind == "explain").content
    again_text = next(block for block in again.blocks if block.kind == "explain").content
    assert first_text != again_text


def test_guided_and_study_differ() -> None:
    guided = engine.respond(make_request(mode=TeachingMode.guided))
    study = engine.respond(make_request(mode=TeachingMode.study))
    guided_notes = " ".join(block.content for block in guided.blocks if block.kind == "note")
    study_notes = " ".join(block.content for block in study.blocks if block.kind == "note")
    assert guided_notes != study_notes


def test_guided_mode_blocks_level3_without_attempt() -> None:
    blocked = engine.respond(make_request(mode=TeachingMode.guided, current_level=2, target_level=3))
    assert blocked.level == 2, "引导模式下未提交尝试不允许进入 L3"
    assert blocked.clamp_reason == "guided_requires_attempt"
    assert any("提交尝试" in block.title for block in blocked.blocks)


def test_guided_mode_allows_level3_after_attempt() -> None:
    submitted = engine.respond(
        make_request(
            mode=TeachingMode.guided,
            current_level=2,
            target_level=3,
            submission=StudentSubmission(kind="thinking", text="我怀疑 info 是 None，因为函数没有返回值"),
        )
    )
    assert submitted.level == 3
    assert submitted.clamp_reason is None


def test_study_mode_allows_level3_without_attempt() -> None:
    response = engine.respond(make_request(mode=TeachingMode.study, current_level=2, target_level=3))
    assert response.level == 3


# ---------------------------------------------------------------- 分类可覆盖


def test_category_can_be_overridden_by_user() -> None:
    response = engine.respond(make_request(category=ProblemCategory.sql))
    assert response.category == ProblemCategory.sql
    assert response.category_source == "user"
