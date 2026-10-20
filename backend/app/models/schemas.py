"""请求 / 响应模型（Pydantic）。

约定：所有对外结构都定义在这里，路由函数只做协议转换。
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class KnowledgeBaseStatus(BaseModel):
    """知识库状态。P0 阶段尚未接入存储，如实返回 not_initialized。"""

    status: Literal["not_initialized", "ready", "degraded"] = Field(
        default="not_initialized", description="知识库是否就绪"
    )
    documents: int = Field(default=0, description="已索引文档数")
    chunks: int = Field(default=0, description="已索引文本块数")


class HealthResponse(BaseModel):
    """GET /api/health 的响应。"""

    status: Literal["ok"] = "ok"
    name: str
    version: str
    env: str
    demo_mode: bool = Field(description="true 表示未配置大模型，回答走模板")
    llm_configured: bool
    llm_model: str | None = None
    embed_provider: Literal["api", "hash"]
    embed_model: str | None = None
    embed_dim: int | None = None
    knowledge_base: KnowledgeBaseStatus
    server_time: datetime


class ErrorResponse(BaseModel):
    """统一错误结构。"""

    code: str
    message: str
    detail: str | None = None
