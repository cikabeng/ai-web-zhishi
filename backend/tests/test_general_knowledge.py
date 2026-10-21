"""通用知识层与证据覆盖度测试。

核心场景：课程资料只"沾边"（讲的是 NoneType），但报错是 int+str。
系统必须识别"资料没覆盖"，给出明确标注的通用知识，而不是简单拒答。
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.knowledge.general import GENERAL_LABEL, diagnose_error
from app.teaching.engine import TeachingEngine
from app.teaching.types import RetrievedChunk, TeachingMode, TeachingRequest

OPERAND_ERROR = "TypeError: unsupported operand type(s) for +: 'int' and 'str'"

QUESTION = (
    "我写了 def add(a, b): res = a + b，然后 print(add(1, \"2\"))，"
    "报错 TypeError: unsupported operand type(s) for +: 'int' and 'str'，怎么排查？"
)

# 只讲 NoneType 的资料：对 int+str 来说只是"沾边"
NEARBY_CHUNK = RetrievedChunk(
    chunk_id="python_errors.md#p4",
    doc_name="python_errors.md",
    text="TypeError: 'NoneType' object is not subscriptable 表示对一个 None 做了方括号取值。",
    score=0.62,
    paragraph_from=4,
)


def test_operand_diagnosis_is_specific() -> None:
    diagnosis = diagnose_error("unsupported operand type(s) for +: 'int' and 'str'")
    assert diagnosis is not None
    assert diagnosis.pattern == "operand_type"
    assert diagnosis.marker == "unsupported operand"
    assert "int" in diagnosis.summary and "str" in diagnosis.summary
    assert any("类型" in cause for cause in diagnosis.causes)
    assert any("type(" in step for step in diagnosis.steps)


def test_concat_and_other_patterns() -> None:
    assert diagnose_error('can only concatenate str (not "int") to str').pattern == "concat"
    assert diagnose_error("'NoneType' object is not callable").pattern == "not_callable"
    assert diagnose_error("list index out of range").pattern == "index_range"
    assert diagnose_error("unexpected indent").pattern == "indent"
    assert diagnose_error("ZeroDivisionError: division by zero").pattern == "zero_division"
    assert diagnose_error("ModuleNotFoundError: No module named 'flask'").pattern == "module_missing"
    assert diagnose_error("name 'total' is not defined").pattern == "name_error"


def test_unknown_message_returns_none() -> None:
    assert diagnose_error("程序跑不起来，帮我看一下") is None
    assert diagnose_error("") is None


def test_engine_adds_labelled_general_block_when_evidence_does_not_cover() -> None:
    engine = TeachingEngine(llm=None)
    request = TeachingRequest(
        question=QUESTION,
        mode=TeachingMode.study,
        current_level=0,
        target_level=1,
        retrieval=[NEARBY_CHUNK],
    )
    response = engine.respond(request)

    general = next(
        (block for block in response.blocks if block.meta.get("source") == "general"),
        None,
    )
    assert general is not None, "资料没覆盖时必须补通用知识，而不是只拒答"
    assert general.title == GENERAL_LABEL
    assert "int" in general.content and "str" in general.content
    assert "非课程资料" in general.title


def test_engine_skips_general_block_when_evidence_covers() -> None:
    covering = RetrievedChunk(
        chunk_id="python_type_errors.md#p2",
        doc_name="python_type_errors.md",
        text="unsupported operand type(s) for +: 'int' and 'str' 表示整数和字符串相加，Python 不做隐式转换。",
        score=0.9,
        paragraph_from=2,
    )
    engine = TeachingEngine(llm=None)
    response = engine.respond(
        TeachingRequest(
            question=QUESTION,
            mode=TeachingMode.study,
            current_level=0,
            target_level=1,
            retrieval=[covering],
        )
    )
    assert not any(block.meta.get("source") == "general" for block in response.blocks)


def test_api_reports_general_knowledge_and_coverage(client: TestClient) -> None:
    payload = {
        "text": (
            "Traceback (most recent call last):\n"
            '  File "demo.py", line 2, in add\n'
            "    res = a + b\n"
            "TypeError: unsupported operand type(s) for +: 'int' and 'str'"
        )
    }
    response = client.post("/api/errors/analyze-text", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["evidence_coverage"] in {"full", "partial", "none"}
    # 不论资料是否覆盖，原因必须是针对 int+str 的，而不是泛泛而谈
    assert any("类型" in cause for cause in data["causes"])
    if data["evidence_coverage"] != "full":
        assert data["general_knowledge"] is not None
        assert data["general_knowledge"]["label"] == GENERAL_LABEL
