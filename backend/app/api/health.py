"""系统级路由：健康检查。"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.library.store import get_store
from app.models.schemas import HealthResponse, KnowledgeBaseStatus

router = APIRouter(tags=["system"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="健康检查",
    description="返回服务状态、运行模式与知识库概况。前端首页据此显示连接状态。",
)
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    stats = get_store().stats()
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
        # 数字来自知识库登记表，没有文档时如实返回未初始化
        knowledge_base=KnowledgeBaseStatus(
            status="ready" if stats["indexed"] else "not_initialized",
            documents=stats["documents"],
            chunks=stats["chunks"],
        ),
        server_time=datetime.now(timezone.utc),
    )
