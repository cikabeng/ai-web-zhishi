"""截图报错分析接口测试（OCR 用假实现，避免加载真实模型）。"""

from __future__ import annotations

import io
from urllib.parse import unquote

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.errors.ocr import OcrFailed
from app.errors.schema import OcrLine, OcrResult

TRACEBACK = """Traceback (most recent call last):
  File "demo.py", line 12, in <module>
    print(info['score'])
TypeError: 'NoneType' object is not subscriptable"""


def png_bytes(size: tuple[int, int] = (200, 80)) -> bytes:
    image = Image.new("RGB", size, (22, 24, 30))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


class FakeProvider:
    name = "fake"
    kind = "local"

    def available(self) -> bool:
        return True

    def recognize(self, image) -> OcrResult:
        lines = [OcrLine(text=line, confidence=0.92) for line in TRACEBACK.splitlines()]
        return OcrResult(
            provider="fake",
            text=TRACEBACK,
            lines=lines,
            mean_confidence=0.92,
            low_confidence=False,
            warnings=["以下文字由测试 OCR 识别"],
        )


class FailingProvider(FakeProvider):
    def recognize(self, image) -> OcrResult:
        raise OcrFailed("模拟识别失败")


class NoProvider(FakeProvider):
    name = "none"
    kind = "none"

    def available(self) -> bool:
        return False


def test_capabilities(client: TestClient) -> None:
    response = client.get("/api/errors/capabilities")
    assert response.status_code == 200
    data = response.json()
    assert data["active"] in {"rapidocr", "vision", "none"}
    assert data["manual_text_fallback"] is True
    assert any(item["provider"] == "rapidocr" for item in data["providers"])


def test_analyze_text(client: TestClient) -> None:
    response = client.post("/api/errors/analyze-text", json={"text": TRACEBACK})
    assert response.status_code == 200

    data = response.json()
    assert data["source"] == "text"
    assert data["parsed"]["exception_type"] == "TypeError"
    assert data["parsed"]["line"] == 12
    assert data["parsed"]["line_estimated"] is False
    assert data["causes"], "应当给出可能原因"
    assert data["steps"], "应当给出排查步骤"
    assert isinstance(data["citations"], list)
    assert data["retrieval"]["hit_count"] >= 0
    assert data["teaching_entry"]["path"].startswith("/teaching?question=")
    assert data["safety"]["code_execution"] == "disabled"


def test_analyze_edited_text_keeps_teaching_entry(client: TestClient) -> None:
    fixed = TRACEBACK.replace("line 12", "line 18")
    response = client.post("/api/errors/analyze-text", json={"text": fixed, "edited": True})
    assert response.status_code == 200
    data = response.json()
    assert data["edited"] is True
    assert data["parsed"]["line"] == 18
    question = unquote(data["teaching_entry"]["path"].split("question=", 1)[1])
    assert "line 18" in question


def test_analyze_javascript(client: TestClient) -> None:
    text = "Uncaught TypeError: Cannot read properties of undefined (reading 'map')\n    at renderList (app.js:42:13)"
    response = client.post("/api/errors/analyze-text", json={"text": text})
    assert response.status_code == 200
    data = response.json()
    assert data["parsed"]["language"] == "javascript"
    assert data["parsed"]["line"] == 42


def test_image_analysis_with_fake_ocr(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.api.errors.get_ocr_provider", lambda settings=None: FakeProvider())

    response = client.post(
        "/api/errors/analyze-image",
        files={"file": ("shot.png", png_bytes(), "image/png")},
    )
    assert response.status_code == 200

    data = response.json()
    assert data["source"] == "image"
    assert data["ocr"]["provider"] == "fake"
    assert data["recognized_text"].startswith("Traceback")
    assert data["parsed"]["line_estimated"] is True, "截图识别的行号必须标记为可能不准"
    assert data["safety"]["line_numbers"] == "recognized/uncertain"
    assert any("识别" in warning for warning in data["warnings"])


def test_image_rejects_wrong_format(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.api.errors.get_ocr_provider", lambda settings=None: FakeProvider())
    response = client.post(
        "/api/errors/analyze-image",
        files={"file": ("shot.gif", b"GIF89a" + b"\x00" * 100, "image/gif")},
    )
    assert response.status_code == 415
    assert "PNG" in response.json()["message"]


def test_image_rejects_too_large(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.api.errors.get_ocr_provider", lambda settings=None: FakeProvider())
    oversized = b"\x89PNG\r\n\x1a\n" + b"0" * (9 * 1024 * 1024)
    response = client.post(
        "/api/errors/analyze-image",
        files={"file": ("big.png", oversized, "image/png")},
    )
    assert response.status_code == 413


def test_image_rejects_corrupt_file(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.api.errors.get_ocr_provider", lambda settings=None: FakeProvider())
    corrupt = b"\x89PNG\r\n\x1a\n" + b"not-a-real-png" * 20
    response = client.post(
        "/api/errors/analyze-image",
        files={"file": ("broken.png", corrupt, "image/png")},
    )
    assert response.status_code == 422


def test_ocr_unavailable_returns_503(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.api.errors.get_ocr_provider", lambda settings=None: NoProvider())
    response = client.post(
        "/api/errors/analyze-image",
        files={"file": ("shot.png", png_bytes(), "image/png")},
    )
    assert response.status_code == 503
    assert "OCR" in response.json()["message"]


def test_ocr_failure_returns_422(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.api.errors.get_ocr_provider", lambda settings=None: FailingProvider())
    response = client.post(
        "/api/errors/analyze-image",
        files={"file": ("shot.png", png_bytes(), "image/png")},
    )
    assert response.status_code == 422
    assert "手动粘贴" in response.json()["message"]
