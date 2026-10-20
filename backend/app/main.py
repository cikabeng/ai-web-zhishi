"""知实 AI — FastAPI 应用入口。

启动方式（在 backend 目录下）：
    ..\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import health
from app.core.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("zhishi")

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """应用启动/关闭时的一次性工作。"""
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    logger.info(
        "启动 %s v%s | env=%s | demo_mode=%s | embed=%s",
        settings.app_name,
        settings.app_version,
        settings.app_env,
        settings.demo_mode,
        settings.resolved_embed_provider,
    )
    yield
    logger.info("服务已停止")


app = FastAPI(
    title=f"{settings.app_name} API",
    description="高校软件工程实训智能答疑知识库（RAG）。仅基于本地课程资料作答，并给出可核对的引用。",
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """把 Pydantic 校验错误整理成统一结构，前端只需处理一种错误格式。"""
    return JSONResponse(
        status_code=422,
        content={
            "code": "validation_error",
            "message": "请求参数不合法",
            "detail": str(exc.errors()[:3]),
        },
    )


@app.get("/api", tags=["system"], summary="接口根")
def api_root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/api/docs",
        "health": "/api/health",
    }
