"""报错解析测试：字段抽取、缺失字段、行号标记。"""

from __future__ import annotations

from app.errors.parser import parse_error

PY_TRACEBACK = """Traceback (most recent call last):
  File "demo.py", line 12, in <module>
    print(info['score'])
TypeError: 'NoneType' object is not subscriptable"""


def test_parse_python_traceback() -> None:
    parsed = parse_error(PY_TRACEBACK)
    assert parsed.language == "python"
    assert parsed.exception_type == "TypeError"
    assert parsed.message == "'NoneType' object is not subscriptable"
    assert parsed.file == "demo.py"
    assert parsed.line == 12
    assert parsed.code_snippet == "print(info['score'])"
    assert parsed.frames[0].function == "<module>"
    assert parsed.line_estimated is False
    assert parsed.missing == []


def test_image_source_marks_line_as_estimated() -> None:
    parsed = parse_error(PY_TRACEBACK, line_estimated=True)
    assert parsed.line_estimated is True


def test_missing_fields_are_reported() -> None:
    parsed = parse_error("TypeError: 'NoneType' object is not subscriptable")
    assert parsed.exception_type == "TypeError"
    assert parsed.message.startswith("'NoneType'")
    assert parsed.file is None
    assert parsed.line is None
    assert "文件名" in parsed.missing
    assert "行号" in parsed.missing
    assert "代码片段" in parsed.missing


def test_javascript_error() -> None:
    text = """Uncaught TypeError: Cannot read properties of undefined (reading 'map')
    at renderList (app.js:42:13)"""
    parsed = parse_error(text)
    assert parsed.language == "javascript"
    assert parsed.exception_type == "TypeError"
    assert "Cannot read properties" in (parsed.message or "")
    assert parsed.file == "app.js"
    assert parsed.line == 42


def test_sql_error() -> None:
    text = "ERROR 1054 (42S22): Unknown column 'class_id' in 'where clause'"
    parsed = parse_error(text)
    assert parsed.language == "sql"
    assert parsed.exception_type == "SQL Error 1054"
    assert "Unknown column" in (parsed.message or "")


def test_unknown_language_is_honest() -> None:
    parsed = parse_error("程序跑不起来，帮我看一下")
    assert parsed.language == "unknown"
    assert parsed.exception_type is None
    assert len(parsed.missing) >= 3


def test_fullwidth_punctuation_tolerated() -> None:
    text = """Traceback (most recent call last):
  File "demo.py"， line 12， in <module>
TypeError：'NoneType' object is not subscriptable"""
    parsed = parse_error(text.replace("，", ",").replace("：", ":"))
    assert parsed.exception_type == "TypeError"
    assert parsed.line == 12
