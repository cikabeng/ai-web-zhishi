"""教学引擎 HTTP 接口测试。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.teaching import DEMO_QUESTION


def test_categories_endpoint(client: TestClient) -> None:
    response = client.get("/api/teaching/categories")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 6
    assert {item["value"] for item in items} == {
        "concept",
        "error",
        "experiment",
        "sql",
        "web",
        "assignment",
    }


def test_levels_endpoint(client: TestClient) -> None:
    response = client.get("/api/teaching/levels")
    assert response.status_code == 200
    items = response.json()
    assert [item["level"] for item in items] == [1, 2, 3, 4]
    assert items[0]["name"] == "知识点提示"


def test_hint_uses_real_retrieval(client: TestClient) -> None:
    response = client.post("/api/teaching/hint", json={"question": DEMO_QUESTION})
    assert response.status_code == 200

    data = response.json()
    assert data["level"] == 1
    assert data["category"] == "error"
    assert data["citations"], "应当由后端检索出真实引用，而不是空数组"
    assert data["citations"][0]["doc_name"].endswith(".md")
    assert data["insufficient_evidence"] is False
    assert data["check_question"]["question"]


def test_hint_cannot_skip_levels(client: TestClient) -> None:
    response = client.post(
        "/api/teaching/hint",
        json={"question": DEMO_QUESTION, "current_level": 0, "target_level": 4},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["level"] == 1
    assert data["clamped"] is True


def test_hint_level4_is_labelled(client: TestClient) -> None:
    response = client.post(
        "/api/teaching/hint",
        json={"question": DEMO_QUESTION, "current_level": 3, "target_level": 4, "mode": "study"},
    )
    data = response.json()
    assert data["level"] == 4
    assert data["example_generated"] is True
    example = next(block for block in data["blocks"] if block["kind"] == "example")
    assert "AI 生成示例" in example["title"]


def test_guided_mode_clamps_level3_without_attempt(client: TestClient) -> None:
    response = client.post(
        "/api/teaching/hint",
        json={"question": DEMO_QUESTION, "current_level": 2, "target_level": 3, "mode": "guided"},
    )
    data = response.json()
    assert data["level"] == 2
    assert data["clamp_reason"] == "guided_requires_attempt"


def test_study_mode_reaches_level3_without_attempt(client: TestClient) -> None:
    response = client.post(
        "/api/teaching/hint",
        json={"question": DEMO_QUESTION, "current_level": 2, "target_level": 3, "mode": "study"},
    )
    assert response.json()["level"] == 3


def test_feedback_on_submission(client: TestClient) -> None:
    payload = {
        "question": DEMO_QUESTION,
        "current_level": 1,
        "target_level": 1,
        "submission": {"kind": "thinking", "text": "我怀疑 get_student 没有 return，所以 info 是 None"},
    }
    response = client.post("/api/teaching/feedback", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["verdict"] in {"on_track", "partial", "off_track"}
    assert data["safety"]["code_execution"] == "disabled"
    assert data["next_question"]


def test_feedback_requires_submission(client: TestClient) -> None:
    response = client.post("/api/teaching/feedback", json={"question": DEMO_QUESTION})
    assert response.status_code == 400


def test_invalid_question_rejected(client: TestClient) -> None:
    assert client.post("/api/teaching/hint", json={"question": ""}).status_code == 422


def test_demo_case_returns_real_retrieval(client: TestClient) -> None:
    response = client.get("/api/teaching/demo-case")
    assert response.status_code == 200
    data = response.json()
    assert data["question"]
    assert data["retrieval"], "演示接口应返回真实检索结果"
    assert "临时" in data["retriever"]
