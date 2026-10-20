"""安全护栏测试：输入清洗、代码收敛、禁止执行。"""

from __future__ import annotations

from pathlib import Path

from app.teaching import guards
from app.teaching.types import HintBlock


def test_sanitize_removes_control_chars_and_trims() -> None:
    dirty = "报错\x00信息\x07\n\n\n\n第二段"
    cleaned = guards.sanitize_text(dirty, max_chars=100)
    assert "\x00" not in cleaned and "\x07" not in cleaned
    assert "\n\n\n" not in cleaned
    assert cleaned.startswith("报错信息")


def test_sanitize_truncates_long_input() -> None:
    assert len(guards.sanitize_text("a" * 5000, max_chars=100)) == 100


def test_code_line_count_ignores_blank_and_comments() -> None:
    code = "```python\n# 注释\nx = 1\n\nprint(x)\n```"
    assert guards.code_line_count(code) == 2


def test_trim_code_keeps_limit_and_explains() -> None:
    code = "\n".join(f"value_{index} = {index}" for index in range(12))
    trimmed, did_trim = guards.trim_code(code)
    assert did_trim is True
    assert guards.code_line_count(trimmed) <= guards.MAX_CODE_LINES
    assert "省略" in trimmed


def test_short_code_is_untouched() -> None:
    code = "x = 1\nprint(x)"
    trimmed, did_trim = guards.trim_code(code)
    assert did_trim is False
    assert trimmed == code


def test_detect_complete_implementation() -> None:
    full = "def solve():\n    a = 1\n    b = 2\n    c = a + b\n    return c"
    assert guards.detect_complete_implementation(full) is True

    skeleton = "def solve():\n    # TODO\n    ..."
    assert guards.detect_complete_implementation(skeleton) is False


def test_guard_blocks_trims_long_code() -> None:
    block = HintBlock(kind="code", title="示例", content="\n".join(f"line_{i} = {i}" for i in range(15)))
    blocks, safety = guards.guard_blocks([block])
    assert safety["leak_guard"] == "trimmed"
    assert "省略" in blocks[0].content


def test_guard_blocks_replaces_leak_phrase() -> None:
    block = HintBlock(kind="explain", title="说明", content="以下是完整答案，直接复制即可提交。")
    blocks, safety = guards.guard_blocks([block])
    assert "完整答案" not in blocks[0].content
    assert safety["leak_guard"] == "trimmed"


def test_guard_blocks_passes_clean_text() -> None:
    block = HintBlock(kind="explain", title="说明", content="先确认变量的类型。")
    _, safety = guards.guard_blocks([block])
    assert safety["leak_guard"] == "passed"
    assert safety["code_execution"] == "disabled"


def test_module_never_executes_code() -> None:
    source = Path(guards.__file__).read_text(encoding="utf-8")
    assert "import subprocess" not in source
    assert "exec(" not in source
    assert "eval(" not in source
