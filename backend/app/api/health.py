"""系统级路由：健康检查。"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.models.schemas import HealthResponse, KnowledgeBaseStatus

router = APIRouter(tags=["system"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="健康检查",
    description="返回服务状态、运行模式与知识库概况。前端首页据此显示连接状态。",
)
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(
        name=settings.app_name,
        version=settings.app_version,
        env=settings.app_env,
        demo_mode=settings.demo_mode,
        llm_configured=settings.llm_configured,
        llm_model=settings.llm_model or None,
        embed_provider=settings.resolved_embed_provider,  # type: ignore[arg-type]
        embed_model=settings.embed_model or None,
        embed_dim=settings.embed_dim,
        # P0 尚未接入文档存储，如实标记为未初始化，不伪造数字
        knowledge_base=KnowledgeBaseStatus(status="not_initialized", documents=0, chunks=0),
        server_time=datetime.now(timezone.utc),
    )
