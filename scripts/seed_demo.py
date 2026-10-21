"""把示例课程资料导入知识库（走真实上传/解析/索引链路）。

运行：
    .venv\\Scripts\\python.exe scripts\\seed_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.library.store import get_store  # noqa: E402

SAMPLES_DIR = PROJECT_ROOT / "backend" / "data" / "samples"


def main() -> int:
    store = get_store()
    files = sorted(SAMPLES_DIR.glob("*.md"))
    if not files:
        print(f"没有找到示例资料：{SAMPLES_DIR}")
        return 1

    print(f"知识库目录：{store.root}")
    for path in files:
        record, duplicate = store.add_document(path.name, path.read_bytes())
        flag = "已存在" if duplicate else record["status"]
        print(f"  {path.name:<22} {flag:<8} chunks={record['chunks']} chars={record['chars']}")
        if record["status"] == "failed":
            print(f"    失败原因：{record['error']}")

    stats = store.stats()
    print(
        f"\n合计：文档 {stats['documents']} 篇，已索引 {stats['indexed']} 篇，"
        f"片段 {stats['chunks']} 个，字符 {stats['chars']}"
    )
    return 0 if stats["indexed"] else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
