"""OCR 辅助函数测试（不加载模型，纯逻辑）。"""

from __future__ import annotations

from app.errors.ocr import group_lines, join_tokens, normalize_text


def _box(x: float, y: float, width: float = 60, height: float = 20) -> list[list[float]]:
    return [[x, y], [x + width, y], [x + width, y + height], [x, y + height]]


def test_normalize_fullwidth_punctuation() -> None:
    assert normalize_text("TypeError：（'NoneType'）") == "TypeError:('NoneType')"


def test_join_tokens_adds_space_between_words() -> None:
    assert join_tokens(["TypeError:", "'NoneType'", "object"]) == "TypeError: 'NoneType' object"


def test_join_tokens_no_space_before_punctuation() -> None:
    assert join_tokens(["print", "(", "x", ")", ";"]).startswith("print(")
    assert " ," not in join_tokens(["a", ",", "b"])


def test_group_lines_merges_same_row() -> None:
    items = [
        [_box(20, 20), "TypeError:", "0.9"],
        [_box(110, 20), "'NoneType'", "0.8"],
        [_box(20, 60), "print(info)", "0.7"],
    ]
    lines = group_lines(items)
    assert len(lines) == 2
    assert lines[0].text == "TypeError: 'NoneType'"
    assert abs((lines[0].confidence or 0) - 0.85) < 1e-6
    assert lines[1].text == "print(info)"


def test_group_lines_handles_empty_input() -> None:
    assert group_lines([]) == []
    assert group_lines(None) == []


def test_group_lines_skips_blank_tokens() -> None:
    lines = group_lines([[_box(10, 10), "   ", "0.9"]])
    assert lines == []


def test_group_lines_restores_indentation() -> None:
    items = [
        [_box(20, 20), "def f():", "0.9"],
        [_box(20, 50), "return f", "0.9"],
        [_box(90, 80), "print(1)", "0.9"],
    ]
    lines = group_lines(items)
    assert lines[0].text == "def f():"
    assert lines[1].text == "return f"
    assert lines[2].text.startswith(" "), "左侧留白较大的行应当还原缩进"
    assert lines[2].text.strip() == "print(1)"


def test_group_lines_keeps_module_brackets_readable() -> None:
    lines = group_lines([[_box(20, 20), "in", "0.9"], [_box(60, 20), "<module>", "0.9"]])
    assert lines[0].text == "in <module>"
