"""截图报错分析的 HTTP 接口。

两个入口共用同一套下游分析：
- `analyze-image`：上传截图 → 校验 → OCR → 分析；
- `analyze-text`：手动粘贴或编辑后的文本 → 分析。
"""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.errors.analyzer import ErrorAnalyzer
from app.errors.images import ImageValidationError, prepare_image
from app.errors.ocr import OcrFailed, OcrUnavailable, capabilities, get_ocr_provider
from app.errors.samples import sample_png
from app.errors.schema import Capabilities, ErrorAnalysis
from app.teaching.guards import sanitize_text

router = APIRouter(prefix="/errors", tags=["errors"])
analyzer = ErrorAnalyzer()


class AnalyzeTextRequest(BaseModel):
    text: str = Field(min_length=3, max_length=8000)
    edited: bool = Field(default=False, description="内容是否经过用户修改")


@router.get("/capabilities", response_model=Capabilities, summary="OCR 能力与可用通道")
def ocr_capabilities() -> Capabilities:
    return capabilities()


@router.get("/sample-image", summary="演示用报错截图")
def sample_image() -> Response:
    return Response(content=sample_png(), media_type="image/png", headers={"Cache-Control": "no-store"})


@router.post("/analyze-text", response_model=ErrorAnalysis, summary="分析粘贴的报错文本")
def analyze_text(payload: AnalyzeTextRequest) -> ErrorAnalysis:
    text = sanitize_text(payload.text, 8000)
    if len(text) < 3:
        raise HTTPException(status_code=422, detail="报错文本太短，无法分析")
    return analyzer.analyze(text, "text", ocr=None, edited=payload.edited)


@router.post("/analyze-image", response_model=ErrorAnalysis, summary="上传报错截图并分析")
async def analyze_image(file: UploadFile = File(...)) -> ErrorAnalysis:
    settings = get_settings()
    raw = await file.read()

    try:
        prepared = prepare_image(raw, file.content_type, settings.ocr_max_bytes, settings.ocr_max_side)
    except ImageValidationError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message) from exc

    provider = get_ocr_provider(settings)
    if not provider.available():
        raise HTTPException(
            status_code=503,
            detail="当前没有可用的 OCR 通道。可以配置 VLM_BASE_URL / VLM_API_KEY / VLM_MODEL 启用视觉模型，"
            "或改用「手动粘贴报错文本」。",
        )

    try:
        ocr = await run_in_threadpool(provider.recognize, prepared)
    except OcrUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except OcrFailed as exc:
        raise HTTPException(
            status_code=422,
            detail=f"{exc}。可以换一张更清晰的截图，或改用「手动粘贴报错文本」。",
        ) from exc

    if not ocr.text.strip():
        raise HTTPException(status_code=422, detail="没有识别到文字，请换一张更清晰的截图或手动粘贴")

    return analyzer.analyze(ocr.text, "image", ocr=ocr, edited=False)
