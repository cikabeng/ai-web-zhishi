"""演示：同一道 Python 报错，从 Level 1 逐步引导到 Level 4。

运行：
    .venv\\Scripts\\python.exe scripts\\demo_teaching.py

说明：检索结果来自 `app.retrieval.keyword`（真实的关键词检索，读取
backend/data/samples 下的示例课程资料），不是写死的假引用。
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.retrieval.keyword import get_retriever  # noqa: E402
from app.teaching.engine import TeachingEngine  # noqa: E402
from app.teaching.types import TeachingMode, TeachingRequest  # noqa: E402

QUESTION = (
    "运行 Python 时报错：TypeError: 'NoneType' object is not subscriptable。"
    "代码里先执行 info = get_student('李四')，然后 print(info['score'])，"
    "get_student 在查不到时会走到函数末尾。这种情况怎么排查？"
)

BAR = "=" * 78


def show(response) -> None:
    print(f"\n【分类】{response.category_label}（{response.category}，"
          f"置信度 {response.category_confidence}，来源 {response.category_source}）")
    print(f"【层级】L{response.level} {response.level_name} —— {response.level_intent}")
    if response.clamped:
        print(f"【限制】请求 L{response.requested_level}，服务端压回 L{response.level}（每次只能 +1）")

    for block in response.blocks:
        print(f"\n── {block.title} [{block.kind}]")
        if block.citations:
            print(f"   引用：{block.citations}")
        for line in block.content.splitlines():
            print(f"   {line}")

    print(f"\n【检查问题】{response.check_question.question}")
    print(f"            （用途：{response.check_question.purpose}）")
    print(f"【可用操作】{', '.join(response.allowed_actions)}")
    print(f"【安全标记】{response.safety}")


def main() -> None:
    engine = TeachingEngine()
    retriever = get_retriever()
    hits = retriever.search(QUESTION, top_k=4)

    print(BAR)
    print("知实 AI · 分层教学引擎演示")
    print(BAR)
    print(f"学生问题：{QUESTION}")
    print(f"\n检索器：关键词检索（临时实现，段落级）")
    print(f"命中片段：{len(hits)} 条")
    for hit in hits:
        print(f"  - {hit.doc_name} 第 {hit.paragraph_from} 段（score={hit.score}）{hit.heading or ''}")

    for level in range(1, 5):
        print("\n" + BAR)
        print(f"第 {level} 次点击「继续提示」 → 请求 Level {level}（当前 L{level - 1}）")
        print(BAR)
        response = engine.respond(
            TeachingRequest(
                question=QUESTION,
                mode=TeachingMode.guided,
                current_level=level - 1,
                target_level=level,
                retrieval=hits,
            )
        )
        show(response)

    print("\n" + BAR)
    print("边界验证：学生试图直接要 Level 4")
    print(BAR)
    skipped = engine.respond(
        TeachingRequest(question=QUESTION, mode=TeachingMode.guided, current_level=0, target_level=4, retrieval=hits)
    )
    print(f"请求 L{skipped.requested_level} → 实际返回 L{skipped.level}，clamped={skipped.clamped}")

    print("\n" + BAR)
    print("边界验证：知识库检索不到资料时")
    print(BAR)
    empty = engine.respond(
        TeachingRequest(question="量子计算机会取代经典计算机吗？", current_level=0, target_level=1, retrieval=[])
    )
    print(f"insufficient_evidence = {empty.insufficient_evidence}")
    for block in empty.blocks:
        if block.kind == "limit":
            print(f"  [{block.title}] {block.content}")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
