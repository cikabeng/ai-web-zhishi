"""OCR 通道。

优先顺序（由 OCR_PROVIDER 控制）：
- auto：配置了视觉模型就用视觉模型，否则用本地 rapidocr，都没有则不可用；
- vision：强制走 OpenAI 兼容的视觉模型（需要 VLM_* 配置）；
- rapidocr：强制走本地 OCR（离线可用）；
- none：关闭识别，只保留手动粘贴入口。

无论哪条通道，输出都标记为「识别结果」，并附带置信度或提醒。
"""

from __future__ import annotations

import base64
import io
import threading

import httpx

from app.core.config import Settings, get_settings
from app.errors.images import PreparedImage
from app.errors.schema import Capabilities, OcrCapability, OcrLine, OcrResult

VISION_PROMPT = (
    "请只输出图片中的文字，按原样保留换行和缩进。"
    "不要解释、不要补全、不要猜测看不清的字符；看不清就写 [?]。"
)

_FULLWIDTH = str.maketrans(
    {
        "，": ",",
        "。": ".",
        "：": ":",
        "；": ";",
        "（": "(",
        "）": ")",
        "［": "[",
        "］": "]",
        "｛": "{",
        "｝": "}",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "？": "?",
        "！": "!",
        "～": "~",
        "－": "-",
        "\u3000": " ",
    }
)

_NO_SPACE_BEFORE = set(",.:;!?)]}%")
_NO_SPACE_AFTER = set("([{")


class OcrUnavailable(RuntimeError):
    """当前没有任何可用的 OCR 通道。"""


class OcrFailed(RuntimeError):
    """OCR 通道存在但识别失败。"""


def normalize_text(text: str) -> str:
    """把常见全角标点还原成半角，便于后续正则解析。"""
    cleaned = text.translate(_FULLWIDTH)
    cleaned = "\n".join(line.rstrip() for line in cleaned.splitlines())
    return cleaned.strip()


def join_tokens(tokens: list[str]) -> str:
    """把同一行里被切开的小块拼起来：英文之间补空格，标点前后不补。"""
    result = ""
    for token in tokens:
        token = token.strip()
        if not token:
            continue
        if not result:
            result = token
            continue
        previous = result[-1]
        first = token[0]
        if previous in _NO_SPACE_AFTER or first in _NO_SPACE_BEFORE:
            result += token
        elif previous in ",:;":
            result += " " + token
        elif first == "<" and previous.isalnum():
            result += " " + token
        elif (previous.isalnum() or previous in "_'\"") and (first.isalnum() or first in "_'\"$"):
            result += " " + token
        else:
            result += token
    return result


def group_lines(items: list, tolerance_ratio: float = 0.6) -> list[OcrLine]:
    """把 OCR 的单词级框按纵坐标聚成行，再按横坐标拼接。

    items 的形态来自 rapidocr：[[box], text, score]。
    """
    entries: list[dict[str, float | str]] = []
    for item in items or []:
        try:
            box, text, score = item[0], item[1], item[2]
        except (IndexError, TypeError):
            continue
        if not text or not str(text).strip():
            continue
        ys = [point[1] for point in box]
        xs = [point[0] for point in box]
        entries.append(
            {
                "cy": sum(ys) / len(ys),
                "height": max(ys) - min(ys),
                "x": min(xs),
                "text": str(text).strip(),
                "score": float(score),
            }
        )

    if not entries:
        return []

    heights = sorted(float(entry["height"]) for entry in entries)
    median_height = heights[len(heights) // 2] or 12.0
    tolerance = max(8.0, median_height * tolerance_ratio)

    entries.sort(key=lambda entry: (float(entry["cy"]), float(entry["x"])))

    groups: list[list[dict[str, float | str]]] = []
    for entry in entries:
        if groups and abs(float(entry["cy"]) - _center(groups[-1])) <= tolerance:
            groups[-1].append(entry)
        else:
            groups.append([entry])

    lines: list[OcrLine] = []
    for group in groups:
        group.sort(key=lambda entry: float(entry["x"]))
        text = normalize_text(join_tokens([str(entry["text"]) for entry in group]))
        if not text:
            continue
        score = sum(float(entry["score"]) for entry in group) / len(group)
        lines.append(OcrLine(text=text, confidence=round(score, 4)))

    return _apply_indentation(lines, groups, median_height)


def _apply_indentation(
    lines: list[OcrLine],
    groups: list[list[dict[str, float | str]]],
    median_height: float,
) -> list[OcrLine]:
    """按左侧留白还原缩进——代码截图没有缩进几乎没法读。"""
    if not groups:
        return lines

    left_edges = [min(float(entry["x"]) for entry in group) for group in groups]
    baseline = min(left_edges)
    char_width = max(6.0, median_height * 0.55)

    indented: list[OcrLine] = []
    for line, left in zip(lines, left_edges):
        spaces = int(round((left - baseline) / char_width))
        spaces = max(0, min(8, spaces))
        indented.append(
            OcrLine(
                text=(" " * spaces) + line.text if spaces else line.text,
                confidence=line.confidence,
            )
        )
    return indented


def _center(group: list[dict[str, float | str]]) -> float:
    return sum(float(entry["cy"]) for entry in group) / len(group)


class OcrProvider:
    name = "none"
    kind = "none"

    def available(self) -> bool:
        return False

    def recognize(self, image: PreparedImage) -> OcrResult:
        raise OcrUnavailable("当前没有可用的 OCR 通道")


class NullOcrProvider(OcrProvider):
    name = "none"
    kind = "none"


class RapidOcrProvider(OcrProvider):
    """本地 OCR，离线可用；首次加载模型约 1–2 秒。"""

    name = "rapidocr"
    kind = "local"

    _engine = None
    _lock = threading.Lock()

    def available(self) -> bool:
        try:
            import rapidocr_onnxruntime  # noqa: F401
        except Exception:  # pragma: no cover - 依赖缺失时的降级
            return False
        return True

    def _get_engine(self):
        if RapidOcrProvider._engine is None:
            with RapidOcrProvider._lock:
                if RapidOcrProvider._engine is None:
                    from rapidocr_onnxruntime import RapidOCR

                    RapidOcrProvider._engine = RapidOCR()
        return RapidOcrProvider._engine

    def recognize(self, image: PreparedImage) -> OcrResult:
        try:
            import numpy as np
            from PIL import Image as PilImage
        except Exception as exc:  # pragma: no cover
            raise OcrUnavailable("本地 OCR 依赖缺失") from exc

        try:
            with PilImage.open(io.BytesIO(image.data)) as pil:
                array = np.array(pil.convert("RGB"))
            result, _ = self._get_engine()(array)
        except Exception as exc:
            raise OcrFailed(f"本地 OCR 识别失败：{exc}") from exc

        lines = group_lines(result or [])
        if not lines:
            raise OcrFailed("没有从图片中识别到文字")

        text = "\n".join(line.text for line in lines)
        scored = [line.confidence for line in lines if line.confidence is not None]
        mean_confidence = round(sum(scored) / len(scored), 4) if scored else None
        low_confidence = bool(mean_confidence is not None and mean_confidence < 0.8)

        warnings: list[str] = ["以下文字由本地 OCR 识别，请核对行号、变量名与缩进。"]
        weak = [line for line in lines if line.confidence is not None and line.confidence < 0.6]
        if weak:
            warnings.append(f"有 {len(weak)} 行置信度偏低（低于 0.60），建议重点核对。")

        return OcrResult(
            provider=self.name,
            text=text,
            lines=lines,
            mean_confidence=mean_confidence,
            low_confidence=low_confidence,
            warnings=warnings,
        )


class VisionOcrProvider(OcrProvider):
    """OpenAI 兼容的视觉模型通道（需要模型本身支持图像输入）。"""

    name = "vision"
    kind = "remote"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def available(self) -> bool:
        return self.settings.vlm_configured

    def recognize(self, image: PreparedImage) -> OcrResult:
        if not self.available():
            raise OcrUnavailable("未配置视觉模型（VLM_BASE_URL / VLM_API_KEY / VLM_MODEL）")

        encoded = base64.b64encode(image.data).decode("ascii")
        payload = {
            "model": self.settings.vlm_model,
            "temperature": 0,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": VISION_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{image.mime};base64,{encoded}"},
                        },
                    ],
                }
            ],
        }
        url = f"{self.settings.vlm_base_url.rstrip('/')}/chat/completions"
        headers = {"Authorization": f"Bearer {self.settings.vlm_api_key}"}

        try:
            with httpx.Client(timeout=self.settings.ocr_timeout) as client:
                response = client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
        except Exception as exc:
            raise OcrFailed(f"视觉模型调用失败：{exc}") from exc

        text = normalize_text(content if isinstance(content, str) else "")
        if not text:
            raise OcrFailed("视觉模型没有返回文字")

        lines = [OcrLine(text=line, confidence=None) for line in text.splitlines() if line.strip()]
        return OcrResult(
            provider=self.name,
            text=text,
            lines=lines,
            mean_confidence=None,
            low_confidence=False,
            warnings=["以下文字由视觉模型识别，模型可能补全或改写内容，请务必核对。"],
        )


def get_ocr_provider(settings: Settings | None = None) -> OcrProvider:
    resolved = settings or get_settings()
    preference = resolved.ocr_provider.strip().lower()

    vision = VisionOcrProvider(resolved)
    rapid = RapidOcrProvider()

    if preference == "vision":
        return vision
    if preference == "rapidocr":
        return rapid
    if preference == "none":
        return NullOcrProvider()

    if vision.available():
        return vision
    if rapid.available():
        return rapid
    return NullOcrProvider()


def capabilities(settings: Settings | None = None) -> Capabilities:
    resolved = settings or get_settings()
    vision = VisionOcrProvider(resolved)
    rapid = RapidOcrProvider()
    active = get_ocr_provider(resolved)

    return Capabilities(
        active=active.name,
        providers=[
            OcrCapability(
                provider="vision",
                available=vision.available(),
                kind="remote",
                note="远程视觉模型，需配置 VLM_BASE_URL / VLM_API_KEY / VLM_MODEL",
            ),
            OcrCapability(
                provider="rapidocr",
                available=rapid.available(),
                kind="local",
                note="本地 OCR，离线可用，首次识别需加载模型",
            ),
        ],
        max_image_mb=resolved.ocr_max_image_mb,
        formats=["png", "jpeg", "webp"],
    )
