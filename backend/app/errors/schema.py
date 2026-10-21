"""截图报错分析的数据契约。

字段命名与前端 `api/errors.ts` 一一对应。
所有"可能不准"的字段都必须显式标记，不允许把猜测当事实。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.teaching.types import Citation


class OcrLine(BaseModel):
    text: str
    confidence: float | None = Field(default=None, description="单行置信度，视觉模型通道为 null")


class OcrResult(BaseModel):
    provider: str = Field(description="rapidocr / vision")
    text: str
    lines: list[OcrLine]
    mean_confidence: float | None = None
    low_confidence: bool = False
    warnings: list[str] = Field(default_factory=list)


class ParsedFrame(BaseModel):
    file: str | None = None
    line: int | None = None
    function: str | None = None
    code: str | None = None


class ParsedError(BaseModel):
    exception_type: str | None = None
    message: str | None = None
    file: str | None = None
    line: int | None = None
    line_estimated: bool = Field(
        default=False,
        description="true 表示行号来自截图识别，可能不准，不得当作事实使用",
    )
    frames: list[ParsedFrame] = Field(default_factory=list)
    code_snippet: str | None = None
    language: Literal["python", "javascript", "sql", "unknown"] = "unknown"
    missing: list[str] = Field(default_factory=list, description="未能识别出的字段")


class TeachingEntry(BaseModel):
    question: str
    path: str
    level: int = 1


class ErrorAnalysis(BaseModel):
    source: Literal["image", "text"]
    recognized_text: str
    edited: bool = False
    ocr: OcrResult | None = None
    parsed: ParsedError

    category: str
    category_label: str
    explanation: str
    causes: list[str]
    steps: list[str]
    citations: list[Citation]
    retrieval: dict[str, object]
    teaching_entry: TeachingEntry
    warnings: list[str] = Field(default_factory=list)

    safety: dict[str, str] = Field(default_factory=dict)


class OcrCapability(BaseModel):
    provider: str
    available: bool
    kind: Literal["local", "remote", "none"]
    note: str


class Capabilities(BaseModel):
    active: str
    providers: list[OcrCapability]
    max_image_mb: int
    formats: list[str]
    manual_text_fallback: bool = True