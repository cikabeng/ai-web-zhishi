"""P0：健康检查与基础协议测试。"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_ok(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert data["name"] == "知实 AI"
    # conftest 强制 DEMO_MODE=on，保证测试不调用真实模型 API
    assert data["demo_mode"] is True
    assert isinstance(data["llm_configured"], bool)
    assert data["embed_provider"] in {"api", "hash"}

    # 知识库状态取决于本机是否已导入资料，这里只断言"状态与数字自洽"，
    # 不把测试绑死在某个具体环境上。
    knowledge = data["knowledge_base"]
    assert knowledge["status"] in {"not_initialized", "ready"}
    if knowledge["status"] == "ready":
        assert knowledge["documents"] > 0
    else:
        assert knowledge["documents"] == 0


def test_health_does_not_leak_secrets(client: TestClient) -> None:
    text = client.get("/api/health").text.lower()
    assert "api_key" not in text
    assert "sk-" not in text


def test_cors_allows_dev_origin(client: TestClient) -> None:
    response = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_api_root(client: TestClient) -> None:
    response = client.get("/api")
    assert response.status_code == 200
    assert response.json()["docs"] == "/api/docs"


def test_unknown_route_returns_404(client: TestClient) -> None:
    assert client.get("/api/not-exist").status_code == 404
