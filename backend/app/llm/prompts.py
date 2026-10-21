"""提示词：把检索片段编号后交给模型，并强制"只用资料、必须标引用、不给完整实现"。"""

from __future__ import annotations

from app.teaching.types import RetrievedChunk

SYSTEM_PROMPT = """你是「知实 AI」的课程助教，面向高校软件工程实训（Python / Web / 数据库）。

必须遵守的规则：
1. 只能依据【资料】里给出的内容作答。资料没有写到的，直接说「资料中没有提到」，不要编造。
2. 每个关键结论后面用 [n] 标注来源编号；n 只能取【资料】里出现过的编号，不要新造编号。
3. 不要给出可以直接提交的完整实现：最多给片段或伪代码，并说明这是示意，不是作业答案。
4. 不执行、不假设执行用户代码；需要验证时，提示学生自己去运行。
5. 用简体中文，语气像助教，简洁、具体，不说空话。
"""

LEVEL_INSTRUCTIONS: dict[int, str] = {
    1: "只做概念解释：说明这个报错/概念是什么、该关注什么。不要给步骤，不要给代码。",
    2: "只给排查思路：输出 4–6 条编号步骤，讲清楚先检查什么、后检查什么。不要给代码。",
    3: "只解释下面这段诊断代码的关键语句，说明它为什么能验证猜想。不要重写它，也不要给完整函数。",
}

LEVEL_TITLES = {
    1: "知识点提示",
    2: "解题思路",
    3: "局部示例",
}


def _format_chunks(chunks: list[RetrievedChunk], limit: int = 3, max_chars: int = 500) -> str:
    lines: list[str] = []
    for index, chunk in enumerate(chunks[:limit], start=1):
        location = (
            f"第 {chunk.page_from} 页"
            if chunk.page_from
            else (f"第 {chunk.paragraph_from} 段" if chunk.paragraph_from else "位置未标注")
        )
        text = " ".join(chunk.text.split())
        if len(text) > max_chars:
            text = text[: max_chars - 1] + "…"
        lines.append(f"[{index}] 《{chunk.doc_name}》{location}：{text}")
    return "\n".join(lines) if lines else "（本次没有检索到资料）"


def build_messages(
    *,
    question: str,
    level: int,
    category_label: str,
    mode: str,
    chunks: list[RetrievedChunk],
    attempt: str | None,
    previous: str | None = None,
) -> list[dict[str, str]]:
    mode_label = "引导模式（多提问、少给结论）" if mode == "guided" else "学习模式（可以讲得更完整）"
    parts = [
        f"【问题】{question}",
        f"【问题类型】{category_label}",
        f"【当前层级】L{level} {LEVEL_TITLES.get(level, '')}",
        f"【模式】{mode_label}",
        f"【学生已提交的尝试】{attempt.strip() if attempt else '（无）'}",
        "【资料】",
        _format_chunks(chunks),
        "",
        f"请执行：{LEVEL_INSTRUCTIONS.get(level, '按层级要求作答。')}",
        "如果资料不足以支撑结论，请直说资料不足，不要编。",
    ]
    if previous:
        parts.insert(0, f"【上一轮内容（供参考，避免重复）】{previous[:300]}")

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(parts)},
    ]
