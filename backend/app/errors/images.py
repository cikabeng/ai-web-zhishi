"""上传图片的校验与预处理。

三道校验：大小 → 真实格式（按文件头，不信扩展名）→ 能否解码。
预处理：超长边缩放到上限、统一转 PNG，降低 OCR 与视觉模型的开销。
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image, UnidentifiedImageError

ALLOWED_FORMATS: dict[str, str] = {
    "PNG": "image/png",
    "JPEG": "image/jpeg",
    "WEBP": "image/webp",
}

_MAGIC: list[tuple[bytes, str]] = [
    (b"\x89PNG\r\n\x1a\n", "PNG"),
    (b"\xff\xd8\xff", "JPEG"),
]


class ImageValidationError(Exception):
    """带 HTTP 状态码的图片校验错误。"""

    def __init__(self, code: str, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


@dataclass(frozen=True)
class PreparedImage:
    data: bytes
    mime: str
    width: int
    height: int
    resized: bool
    original_bytes: int


def detect_format(raw: bytes) -> str | None:
    for magic, name in _MAGIC:
        if raw.startswith(magic):
            return name
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "WEBP"
    return None


def prepare_image(
    raw: bytes,
    declared_type: str | None,
    max_bytes: int,
    max_side: int,
) -> PreparedImage:
    if not raw:
        raise ImageValidationError("empty_file", "上传的文件是空的", 400)

    if len(raw) > max_bytes:
        raise ImageValidationError(
            "too_large",
            f"图片大小 {len(raw) / 1024 / 1024:.1f} MB，超过上限 {max_bytes / 1024 / 1024:.0f} MB",
            413,
        )

    detected = detect_format(raw)
    if detected is None:
        raise ImageValidationError(
            "unsupported_format",
            "只支持 PNG、JPEG、WEBP 三种图片格式（GIF、BMP、PDF 等不支持）",
            415,
        )

    if declared_type and declared_type.split(";")[0].strip().lower() not in ALLOWED_FORMATS.values():
        raise ImageValidationError(
            "unsupported_type",
            f"声明的类型 {declared_type} 不受支持，请上传 PNG / JPEG / WEBP 图片",
            415,
        )

    try:
        with Image.open(io.BytesIO(raw)) as image:
            image.load()  # 真正解码，能发现被截断/损坏的文件
            width, height = image.size
            if width < 40 or height < 20:
                raise ImageValidationError("too_small", "图片太小，无法识别文字", 422)

            resized = False
            if max(width, height) > max_side:
                ratio = max_side / max(width, height)
                image = image.resize((max(1, int(width * ratio)), max(1, int(height * ratio))))
                resized = True

            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")

            buffer = io.BytesIO()
            image.save(buffer, format="PNG", optimize=True)
            prepared = buffer.getvalue()
            out_width, out_height = image.size
    except ImageValidationError:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ImageValidationError("invalid_image", f"图片无法解析，可能已损坏：{exc}", 422) from exc

    return PreparedImage(
        data=prepared,
        mime="image/png",
        width=out_width,
        height=out_height,
        resized=resized,
        original_bytes=len(raw),
    )
