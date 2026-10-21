"""按 5 个标准问题核对检索与回答，输出 PASS / FAIL。

运行（会先把示例资料导入知识库）：
    .venv\\Scripts\\python.exe scripts\\check_demo.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.library.store import get_store  # noqa: E402
from app.retrieval.service import get_retriever  # noqa: E402
from app.teaching.engine import TeachingEngine  # noqa: E402
from app.teaching.types import TeachingMode, TeachingRequest  # noqa: E402

CASES_PATH = PROJECT_ROOT / "backend" / "data" / "demo_cases.json"
SAMPLES_DIR = PROJECT_ROOT / "backend" / "data" / "samples"


def seed_if_needed() -> None:
    store = get_store()
    if store.stats()["indexed"] > 0:
        return
    for path in sorted(SAMPLES_DIR.glob("*.md")):
        store.add_document(path.name, path.read_bytes())


def main() -> int:
    seed_if_needed()
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    engine = TeachingEngine()
    retriever = get_retriever()

    passed = 0
    print(f"{'ID':<4}{'分类':<10}{'引用':<22}{'资料充分':<10}结果")
    print("-" * 72)

    for case in cases:
        hits = retriever.search(case["question"], top_k=4)
        response = engine.respond(
            TeachingRequest(
                question=case["question"],
                mode=TeachingMode.study,
                current_level=0,
                target_level=1,
                retrieval=hits,
            )
        )

        category_ok = response.category.value == case["expect_category"]
        sufficient_ok = response.insufficient_evidence is (not case["expect_sufficient"])

        if case["expect_doc"]:
            cited_docs = {citation.doc_name for citation in response.citations}
            doc_ok = case["expect_doc"] in cited_docs
            doc_display = ",".join(sorted(cited_docs))[:20] or "（无引用）"
        else:
            doc_ok = len(response.citations) == 0
            doc_display = "（无引用）" if doc_ok else "错误地产生了引用"

        ok = category_ok and sufficient_ok and doc_ok
        passed += 1 if ok else 0
        print(
            f"{case['id']:<4}{response.category.value:<10}{doc_display:<22}"
            f"{str(not response.insufficient_evidence):<10}{'PASS' if ok else 'FAIL'}"
        )
        if not ok:
            print(
                f"     期望 category={case['expect_category']} doc={case['expect_doc']} "
                f"sufficient={case['expect_sufficient']}；实际 category={response.category.value} "
                f"citations={[c.doc_name for c in response.citations]} "
                f"insufficient={response.insufficient_evidence}"
            )

    total = len(cases)
    print("-" * 72)
    print(f"通过 {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
