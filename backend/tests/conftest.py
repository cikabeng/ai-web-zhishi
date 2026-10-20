"""pytest 公共夹具。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client() -> TestClient:
    # 用 with 触发 lifespan，确保启动逻辑（创建 storage 目录）也被测到
    with TestClient(app) as test_client:
        yield test_client
