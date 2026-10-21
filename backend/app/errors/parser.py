"""从报错文本中提取结构化信息。

只做正则解析，不做任何推断：
- 识别不到的字段留空，并记入 `missing`；
- 行号永远标记为「可能不准」（截图来源时尤其如此），前端不得当作事实展示。
"""

from __future__ import annotations

import re

from app.errors.schema import ParsedError, ParsedFrame

_PY_FRAME = re.compile(r'File\s+"([^"]+)"\s*,\s*line\s+(\d+)(?:\s*,\s*in\s+(\S+))?')
_PY_LINE_ONLY = re.compile(r"^\s*line\s+(\d+)\s*$")
_PY_EXC = re.compile(r"^([A-Za-z_][\w.]*(?:Error|Exception|Warning))(?:\s*:\s*(.*))?$")

_JS_UNCAUGHT = re.compile(r"^(?:Uncaught\s+)?([A-Za-z]*Error)\s*:\s*(.+)$")
_JS_FRAME = re.compile(r"at\s+(?:[\w$.<>]+\s+)?\(?([^\s()]+?):(\d+):(\d+)\)?")

_SQL_ERROR = re.compile(r"ERROR\s+(\d{3,5})\s*(?:\(([^)]+)\))?\s*:\s*(.+)", re.IGNORECASE)
_SQL_COLUMN = re.compile(r"(unknown column|no such column|unknown table|no such table)", re.IGNORECASE)

_FRAME_NOISE = re.compile(r"^(Traceback|During handling|The above exception|\[Previous line repeated)")


def _clean_line(line: str) -> str:
    return line.strip("\u00a0 ").rstrip()


_JS_HINTS = ("cannot read propert", "is not a function", "undefined is not", "uncaught")


def _detect_language(
    text: str,
    lines: list[str],
    py_frames: list[ParsedFrame],
    js_frames: list[ParsedFrame],
) -> str:
    lowered = text.lower()
    if "traceback (most recent call last)" in lowered or py_frames:
        return "python"
    if js_frames or "uncaught" in lowered or any(hint in lowered for hint in _JS_HINTS[1:]):
        return "javascript"
    if _SQL_ERROR.search(text) or _SQL_COLUMN.search(text):
        return "sql"
    # 没有堆栈也能识别：单行 "TypeError: xxx" 按 Python 异常处理
    if any(_PY_EXC.match(line) for line in lines):
        return "python"
    return "unknown"


def _pick_python_exception(lines: list[str]) -> tuple[str | None, str | None]:
    for line in reversed(lines):
        candidate = _clean_line(line)
        if not candidate or candidate.startswith("File "):
            continue
        if _PY_FRAME.search(candidate) or _FRAME_NOISE.search(candidate):
            continue
        if candidate.startswith("^") or candidate.startswith("~"):
            continue
        match = _PY_EXC.match(candidate)
        if match:
            return match.group(1), (match.group(2) or "").strip() or None
    return None, None


def parse_error(text: str, line_estimated: bool = False) -> ParsedError:
    """把报错文本解析成结构化字段。line_estimated=True 表示内容来自截图识别。"""
    raw_lines = text.replace("\r\n", "\n").splitlines()
    stripped = [_clean_line(line) for line in raw_lines if line.strip()]

    py_frames: list[ParsedFrame] = []
    for index, line in enumerate(stripped):
        match = _PY_FRAME.search(line)
        if not match:
            continue
        code: str | None = None
        if index + 1 < len(stripped):
            following = stripped[index + 1]
            if not _PY_FRAME.search(following) and not _PY_EXC.match(following):
                code = _clean_line(following).strip()
        py_frames.append(
            ParsedFrame(file=match.group(1), line=int(match.group(2)), function=match.group(3), code=code)
        )

    js_frames: list[ParsedFrame] = []
    for line in stripped:
        match = _JS_FRAME.search(line)
        if match:
            js_frames.append(
                ParsedFrame(file=match.group(1), line=int(match.group(2)), function=None, code=None)
            )

    language = _detect_language(text, stripped, py_frames, js_frames)

    exception_type: str | None = None
    message: str | None = None
    frames: list[ParsedFrame] = []

    if language == "python":
        frames = py_frames
        exception_type, message = _pick_python_exception(stripped)
    elif language == "javascript":
        frames = js_frames
        for line in reversed(stripped):
            match = _JS_UNCAUGHT.match(_clean_line(line))
            if match:
                exception_type, message = match.group(1), match.group(2).strip()
                break
    elif language == "sql":
        match = _SQL_ERROR.search(text)
        if match:
            exception_type = f"SQL Error {match.group(1)}"
            message = match.group(3).strip()

    # Python 的 line-only 片段（例如 "  line 12" 单独一行）兜底
    if language == "python" and not frames:
        for line in stripped:
            match = _PY_LINE_ONLY.match(line)
            if match:
                frames = [ParsedFrame(file=None, line=int(match.group(1)), function=None, code=None)]
                break

    file_name = frames[-1].file if frames else None
    line_number = frames[-1].line if frames else None
    code_snippet = frames[-1].code if frames else None

    missing = [
        label
        for label, value in (
            ("异常类型", exception_type),
            ("错误信息", message),
            ("文件名", file_name),
            ("行号", line_number),
            ("代码片段", code_snippet),
        )
        if not value
    ]

    return ParsedError(
        exception_type=exception_type,
        message=message,
        file=file_name,
        line=line_number,
        line_estimated=bool(line_number is not None and line_estimated),
        frames=frames,
        code_snippet=code_snippet,
        language=language,
        missing=missing,
    )
