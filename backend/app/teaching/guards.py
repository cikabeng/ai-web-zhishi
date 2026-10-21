"""教学引擎的安全护栏。

三条底线：
1. 永不执行用户提交的代码——本模块只有字符串处理，没有 exec/eval/subprocess。
2. 代码片段有长度上限，避免一层提示里出现"整份作业"。
3. 任何文本命中"完整答案"类话术时收敛，而不是原样返回。
"""

from __future__ import annotations

import re

from app.teaching.types import HintBlock

MAX_CODE_LINES = 6
MAX_QUESTION_CHARS = 2000
MAX_SUBMISSION_CHARS = 4000

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_MULTI_BLANK = re.compile(r"\n{3,}")
_FENCE = re.compile(r"^\s*```[a-zA-Z0-9_+-]*\s*$", re.MULTILINE)
_COMPLETE_FUNCTION = re.compile(
    r"^\s*def\s+\w+\s*\([^)]*\)\s*:\s*\n(?:[ \t]+\S.*\n?){4,}", re.MULTILINE
)

LEAK_PHRASES = (
    "完整代码",
    "完整实现",
    "完整答案",
    "直接复制",
    "复制即可运行",
    "以下是完整",
    "答案如下",
)
LEAK_REPLACEMENT = "（此处已收敛，避免直接给出答案）"

_CITATION_MARK = re.compile(r"\[(\d+)\]")


def sanitize_citations(text: str, allowed: int) -> tuple[str, bool]:
    """把模型编出来的引用编号剔掉：只允许 [1..allowed]。

    模型常见毛病是引用一个不在资料列表里的编号（比如资料只给了两条却写 [3]）。
    这种"看起来有出处"的假引用比没有引用更糟，必须清掉。
    """
    removed = False

    def replace(match: re.Match[str]) -> str:
        nonlocal removed
        index = int(match.group(1))
        if 1 <= index <= allowed:
            return match.group(0)
        removed = True
        return ""

    cleaned = _CITATION_MARK.sub(replace, text)
    if removed:
        cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned, removed


def sanitize_text(text: str, max_chars: int) -> str:
    """去控制字符、压缩空行、截断超长输入。"""
    cleaned = _CONTROL_CHARS.sub("", text.replace("\r\n", "\n"))
    cleaned = _MULTI_BLANK.sub("\n\n", cleaned)
    return cleaned.strip()[:max_chars]


def strip_fences(code: str) -> str:
    """去掉 markdown 代码围栏，只保留代码本体。"""
    return _FENCE.sub("", code).strip("\n")


def code_line_count(code: str) -> int:
    """有效代码行数（忽略空行与纯注释行）。"""
    lines = [line.strip() for line in strip_fences(code).splitlines()]
    return len([line for line in lines if line and not line.startswith("#") and not line.startswith("//")])


def trim_code(code: str, max_lines: int = MAX_CODE_LINES) -> tuple[str, bool]:
    """超长代码只保留前 N 行，并显式说明被省略。返回 (代码, 是否截断)。"""
    body = strip_fences(code)
    lines = body.splitlines()
    if code_line_count(body) <= max_lines:
        return body, False

    kept: list[str] = []
    counted = 0
    for line in lines:
        stripped = line.strip()
        is_code = stripped and not stripped.startswith("#") and not stripped.startswith("//")
        if is_code:
            if counted >= max_lines:
                break
            counted += 1
        kept.append(line)

    kept.append("# …（后续行已省略，避免一层提示里出现完整实现）")
    return "\n".join(kept), True


def detect_complete_implementation(text: str) -> bool:
    """检测是否出现"函数体完整的实现"，这是最常见的作业泄露形态。"""
    return bool(_COMPLETE_FUNCTION.search(strip_fences(text)))


def _redact_leak_phrases(text: str) -> tuple[str, bool]:
    hit = False
    for phrase in LEAK_PHRASES:
        if phrase in text:
            text = text.replace(phrase, LEAK_REPLACEMENT)
            hit = True
    return text, hit


def guard_blocks(blocks: list[HintBlock]) -> tuple[list[HintBlock], dict[str, str]]:
    """对生成的提示块做统一收敛，返回 (处理后块, 安全标记)。"""
    trimmed = False
    redacted = False
    blocked = False

    for block in blocks:
        if block.kind == "code":
            guarded, did_trim = trim_code(block.content)
            if did_trim:
                trimmed = True
            if detect_complete_implementation(guarded):
                guarded = (
                    "# 已检测到完整实现，已替换为骨架，请自行补全\n"
                    "def your_function(...):\n"
                    "    # TODO: 根据上面的思路补全\n"
                    "    ..."
                )
                blocked = True
            block.content = guarded

        new_content, hit = _redact_leak_phrases(block.content)
        if hit:
            redacted = True
            block.content = new_content

    if blocked:
        status = "blocked"
    elif trimmed or redacted:
        status = "trimmed"
    else:
        status = "passed"

    safety = {
        "leak_guard": status,
        "max_code_lines": str(MAX_CODE_LINES),
        "code_execution": "disabled",
        "citation_whitelist": "enforced",
    }
    return blocks, safety
