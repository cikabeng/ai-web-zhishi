"""P0：健康检查与基础协议测试。"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_ok(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert data["name"] == "知实 AI"
    assert isinstance(data["demo_mode"], bool)
    # 演示模式必须与"是否配置了大模型"严格一致，不允许出现伪造状态
    assert data["demo_mode"] is (not data["llm_configured"])
    assert data["embed_provider"] in {"api", "hash"}
    assert data["knowledge_base"]["status"] == "not_initialized"


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
