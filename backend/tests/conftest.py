"""pytest 公共夹具。

重要：测试必须离线、可重复。
本机 .env 里可能配了真实模型 Key，这里在导入应用之前强制演示模式，
避免单元测试真的去调用外部 API（既慢又花钱，还会因为网络波动而随机失败）。
"""

from __future__ import annotations

import os

os.environ["DEMO_MODE"] = "on"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client() -> TestClient:
    # 用 with 触发 lifespan，确保启动逻辑（创建 storage 目录）也被测到
    with TestClient(app) as test_client:
        yield test_client
