"""演示：截图报错分析（真实本地 OCR，不经 HTTP）。

运行：
    .venv\\Scripts\\python.exe scripts\\demo_errors.py
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.errors.analyzer import ErrorAnalyzer  # noqa: E402
from app.errors.images import prepare_image  # noqa: E402
from app.errors.ocr import get_ocr_provider  # noqa: E402
from app.errors.samples import sample_png  # noqa: E402

BAR = "=" * 76


def main() -> None:
    raw = sample_png()
    shot = PROJECT_ROOT / ".tmp" / "demo-error-shot.png"
    shot.parent.mkdir(parents=True, exist_ok=True)
    shot.write_bytes(raw)

    print(BAR)
    print("知实 AI · 截图报错分析演示")
    print(BAR)
    print(f"示例图片：{shot}（{len(raw) / 1024:.0f} KB，服务端绘制）")

    prepared = prepare_image(raw, "image/png", max_bytes=8 * 1024 * 1024, max_side=1600)
    print(f"校验通过：{prepared.width}x{prepared.height}, 缩放={prepared.resized}")

    provider = get_ocr_provider()
    print(f"OCR 通道：{provider.name}（available={provider.available()}）")
    ocr = provider.recognize(prepared)
    print(f"\n识别置信度：{ocr.mean_confidence}（低置信={ocr.low_confidence}）")
    print("---- 识别文本 ----")
    for line in ocr.text.splitlines():
        print(f"  | {line}")

    analysis = ErrorAnalyzer().analyze(ocr.text, "image", ocr=ocr)

    print("\n---- 解析字段 ----")
    parsed = analysis.parsed
    for label, value in (
        ("异常类型", parsed.exception_type),
        ("错误信息", parsed.message),
        ("文件名", parsed.file),
        ("行号", parsed.line),
        ("行号是否估算", parsed.line_estimated),
        ("代码片段", parsed.code_snippet),
        ("语言", parsed.language),
        ("缺失字段", parsed.missing or "无"),
    ):
        print(f"  {label}: {value}")

    print("\n---- 错误解释 ----")
    print(f"  {analysis.explanation.replace(chr(10), ' ')[:120]}")

    print("\n---- 可能原因 ----")
    for item in analysis.causes:
        print(f"  - {item}")

    print("\n---- 排查步骤 ----")
    for index, item in enumerate(analysis.steps, start=1):
        print(f"  {index}. {item}")

    print("\n---- 教材引用 ----")
    for citation in analysis.citations:
        print(f"  [{citation.index}] 《{citation.doc_name}》{citation.location} 相关度 {citation.score:.2f}")

    print("\n---- 检索与安全 ----")
    print(f"  命中 {analysis.retrieval['hit_count']} 条，是否充分：{analysis.retrieval['sufficient']}")
    print(f"  安全标记：{analysis.safety}")

    print("\n---- 提醒 ----")
    for warning in analysis.warnings:
        print(f"  ! {warning}")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
