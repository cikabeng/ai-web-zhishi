"""模型接入测试：提示词约束、客户端容错、引擎回退与状态标记。"""

from __future__ import annotations

import httpx
import pytest

from app.core.config import Settings
from app.llm.client import LLMClient, LLMError
from app.llm.prompts import build_messages
from app.teaching.engine import TeachingEngine
from app.teaching.types import RetrievedChunk, TeachingMode, TeachingRequest

CHUNKS = [
    RetrievedChunk(
        chunk_id="python_errors.md#p4",
        doc_name="python_errors.md",
        text="TypeError: 'NoneType' object is not subscriptable 表示对一个 None 做了下标取值。",
        score=0.82,
        paragraph_from=4,
    )
]

QUESTION = "TypeError: 'NoneType' object is not subscriptable 怎么排查？"


class FakeLLM:
    available = True
    model_name = "fake-model"

    def __init__(self, reply: str = "模型解释：先确认变量是不是 None [1]") -> None:
        self.reply = reply

    def compose_hint(self, **kwargs) -> str:
        return self.reply


class BrokenLLM(FakeLLM):
    available = True

    def compose_hint(self, **kwargs) -> str:
        raise LLMError("模拟超时")


def make_request(**overrides) -> TeachingRequest:
    payload = {
        "question": QUESTION,
        "mode": TeachingMode.study,
        "current_level": 0,
        "target_level": 1,
        "retrieval": CHUNKS,
    }
    payload.update(overrides)
    return TeachingRequest(**payload)


def test_prompt_contains_sources_and_rules() -> None:
    messages = build_messages(
        question=QUESTION,
        level=1,
        category_label="编程报错",
        mode="guided",
        chunks=CHUNKS,
        attempt=None,
    )
    system = messages[0]["content"]
    user = messages[1]["content"]

    assert "只能依据" in system
    assert "不要给出可以直接提交的完整实现" in system
    assert "[1]" in user
    assert "python_errors.md" in user


def test_prompt_does_not_leak_api_key() -> None:
    messages = build_messages(
        question=QUESTION,
        level=1,
        category_label="编程报错",
        mode="guided",
        chunks=CHUNKS,
        attempt="我怀疑是 None",
    )
    joined = " ".join(message["content"] for message in messages)
    assert "sk-" not in joined


def test_client_parses_openai_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        return httpx.Response(200, json={"choices": [{"message": {"content": "来自模型的回答 [1]"}}]})

    settings = Settings(
        LLM_API_KEY="sk-test",
        LLM_BASE_URL="http://localhost:1/v1",
        LLM_MODEL="fake-model",
        DEMO_MODE="off",
    )
    client = LLMClient(settings, transport=httpx.MockTransport(handler))
    assert client.available is True
    assert client.chat([{"role": "user", "content": "hi"}]) == "来自模型的回答 [1]"


def test_client_raises_on_server_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("time.sleep", lambda *_: None)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    settings = Settings(
        LLM_API_KEY="sk-test",
        LLM_BASE_URL="http://localhost:1/v1",
        LLM_MODEL="fake-model",
        DEMO_MODE="off",
    )
    client = LLMClient(settings, transport=httpx.MockTransport(handler))
    with pytest.raises(LLMError):
        client.chat([{"role": "user", "content": "hi"}])


def test_engine_uses_model_text_and_keeps_citations() -> None:
    engine = TeachingEngine(llm=FakeLLM())
    response = engine.respond(make_request())

    assert response.llm_status == "model"
    assert response.llm_model == "fake-model"
    explain = next(block for block in response.blocks if block.kind == "explain")
    assert explain.content.startswith("模型解释")
    assert explain.meta.get("source") == "llm"
    # 引用仍然来自检索结果，不是模型编的
    assert [citation.chunk_id for citation in response.citations] == ["python_errors.md#p4"]


def test_engine_falls_back_when_model_fails() -> None:
    engine = TeachingEngine(llm=BrokenLLM())
    response = engine.respond(make_request())

    assert response.llm_status == "fallback"
    explain = next(block for block in response.blocks if block.kind == "explain")
    assert "模型解释" not in explain.content
    assert response.citations, "回退时引用不能丢"


def test_engine_uses_template_when_model_unavailable() -> None:
    class DisabledLLM(FakeLLM):
        available = False

    engine = TeachingEngine(llm=DisabledLLM())
    response = engine.respond(make_request())

    assert response.llm_status == "template"
    assert response.llm_model is None


def test_level4_is_not_rewritten_by_model() -> None:
    engine = TeachingEngine(llm=FakeLLM())
    response = engine.respond(make_request(current_level=3, target_level=4))

    assert response.level == 4
    example = next(block for block in response.blocks if block.kind == "example")
    assert example.meta.get("source") != "llm"
