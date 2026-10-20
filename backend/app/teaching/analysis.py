"""问题分析：抽取异常类型、标识符与关注点，供各级提示措辞使用。"""

from __future__ import annotations

import re

from app.teaching.types import ProblemCategory

_EXCEPTION_RE = re.compile(r"\b([A-Z][A-Za-z]*(?:Error|Exception))\b")
_MESSAGE_RE = re.compile(r"(?:Error|Exception)\s*:\s*(.+)", re.IGNORECASE)
_IDENTIFIER_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]{2,}\b")

_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "this",
    "that",
    "none",
    "true",
    "false",
    "object",
    "error",
    "type",
    "line",
    "file",
    "print",
}

EXCEPTION_MEANINGS: dict[str, str] = {
    "TypeError": "类型不匹配：对某个值做了它这个类型不支持的操作。",
    "ValueError": "取值不合法：类型是对的，但具体值超出了允许范围。",
    "NameError": "名字未定义：变量在使用前没有赋值，或者拼写与定义处不一致。",
    "IndexError": "下标越界：访问了序列里不存在的位置。",
    "KeyError": "键不存在：字典里没有这个键。",
    "AttributeError": "属性不存在：对象没有这个属性或方法。",
    "ModuleNotFoundError": "模块找不到：没有安装，或者运行环境不对。",
    "ImportError": "导入失败：模块存在，但要导入的名字不对。",
    "SyntaxError": "语法错误：括号、引号或缩进不符合语法规则。",
    "IndentationError": "缩进错误：Python 用缩进表达代码块。",
    "ZeroDivisionError": "除数为零：除数在某些输入下变成了 0。",
    "FileNotFoundError": "文件不存在：路径或工作目录不对。",
    "ReferenceError": "JS 引用了未声明的变量。",
    "UnboundLocalError": "局部变量在赋值前被使用。",
    "RecursionError": "递归没有正确终止。",
    "OverflowError": "数值超出可表示范围。",
}

# 每类问题的"关注点"，用于 L1 的措辞与检查问题
CONCEPT_FOCUS: dict[ProblemCategory, str] = {
    ProblemCategory.concept: "这个概念的定义、适用场景与它要解决的问题",
    ProblemCategory.error: "报错类型、出错的那一行、以及出问题的那个值的来源",
    ProblemCategory.experiment: "实验目标、环境前提与操作顺序",
    ProblemCategory.sql: "查询条件、表连接方式与 NULL 的处理",
    ProblemCategory.web: "报错发生在浏览器、网络还是后端",
    ProblemCategory.assignment: "题目要求、输入输出与边界情况",
}


def extract_identifiers(text: str, limit: int = 4) -> list[str]:
    """抽取可能相关的英文标识符（变量名、函数名、类名）。"""
    found: list[str] = []
    for match in _IDENTIFIER_RE.finditer(text):
        token = match.group(0)
        if token.lower() in _STOPWORDS:
            continue
        if token not in found:
            found.append(token)
        if len(found) >= limit:
            break
    return found


def analyze(question: str, category: ProblemCategory) -> dict[str, str]:
    """返回用于措辞的结构化线索。"""
    exception_match = _EXCEPTION_RE.search(question)
    exception_type = exception_match.group(1) if exception_match else ""

    message_match = _MESSAGE_RE.search(question)
    message = message_match.group(1).strip().strip("。.") if message_match else ""

    identifiers = extract_identifiers(question)

    if exception_type:
        focus = f"`{exception_type}` 这个异常"
    elif category == ProblemCategory.error:
        focus = "这段报错"
    else:
        focus = CONCEPT_FOCUS[category]

    meaning = EXCEPTION_MEANINGS.get(exception_type, "")

    # 没有异常类型时，用第一句作为主题短语
    topic = exception_type or (identifiers[0] if identifiers else "")
    if not topic:
        first_line = question.strip().splitlines()[0]
        topic = first_line[:24]

    return {
        "exception_type": exception_type,
        "message": message,
        "identifiers": "、".join(identifiers) if identifiers else "",
        "focus": focus,
        "meaning": meaning,
        "topic": topic,
    }
