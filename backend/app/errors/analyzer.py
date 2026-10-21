"""截图报错分析编排。

复用现有链路，不另建问答系统：
    文本/OCR 结果 → 解析 → 分类 → 复用检索器（按分类路由）→ 复用教学引擎 L1/L2
"""

from __future__ import annotations

import re
from urllib.parse import quote

from app.errors.parser import parse_error
from app.errors.schema import ErrorAnalysis, GeneralKnowledge, OcrResult, ParsedError, TeachingEntry
from app.knowledge.general import GENERAL_LABEL, GeneralDiagnosis, diagnose_error
from app.retrieval.service import get_retriever
from app.teaching.classifier import classify
from app.teaching.engine import TeachingEngine
from app.teaching.types import Citation, TeachingMode, TeachingRequest, RetrievedChunk

_CAUSE_TABLE: list[tuple[tuple[str, ...], list[str]]] = [
    (
        ("typeerror", "nonetype"),
        [
            "函数在某个分支没有 return，隐式返回了 None",
            "字典取值（尤其是 get）得到 None，随后又对结果取下标",
            "变量在使用前被重新赋值为 None",
        ],
    ),
    (
        ("attributeerror", "nonetype"),
        [
            "对 None 调用属性或方法，例如 x.strip()",
            "对象初始化失败，但后续代码仍按初始化成功来写",
        ],
    ),
    (
        ("keyerror",),
        [
            "访问了字典中不存在的键",
            "键名拼写与数据实际键名不一致",
        ],
    ),
    (
        ("indexerror",),
        [
            "下标超出序列长度，常见于空列表或循环边界",
            "循环条件里的边界值多算或少算了一次",
        ],
    ),
    (
        ("modulenotfounderror", "importerror"),
        [
            "依赖没有安装，或装在了另一个 Python 环境里",
            "模块名拼写错误、文件名与模块名冲突",
        ],
    ),
    (
        ("nameerror", "unboundlocalerror"),
        [
            "变量在使用前没有赋值，或定义在另一个作用域",
            "函数内先使用后赋值，导致局部变量未初始化",
        ],
    ),
    (
        ("indentationerror", "taberror"),
        [
            "缩进混用了空格与制表符",
            "代码块缩进层级不一致",
        ],
    ),
    (
        ("syntaxerror",),
        [
            "括号、引号未闭合",
            "语句结构不完整，例如 if 缺少冒号",
        ],
    ),
    (
        ("zerodivisionerror",),
        [
            "除数为 0，通常来自输入数据或计算结果",
            "循环变量在边界情况下变成了 0",
        ],
    ),
    (
        ("referenceerror",),
        [
            "使用了未声明的变量，或变量在声明前被访问",
            "作用域不对：变量定义在另一个函数/模块里",
        ],
    ),
    (
        ("cannot read propert", "undefined"),
        [
            "对象还没加载完就渲染，数据是 undefined",
            "接口返回结构与前端取值路径不一致",
        ],
    ),
    (
        ("unknown column", "no such column"),
        [
            "字段名拼写错误，或字段不在当前表/别名下",
            "查询涉及多表时缺少表名前缀",
        ],
    ),
    (
        ("no such table", "unknown table"),
        [
            "数据库文件或连接串指向了错误的库",
            "表还没有创建，或建表语句没有执行",
        ],
    ),
]

_FALLBACK_CAUSES = [
    "异常类型与代码的预期不一致",
    "输入数据与函数假设不符",
]


def causes_for(parsed: ParsedError) -> list[str]:
    haystack = f"{parsed.exception_type or ''} {parsed.message or ''}".lower()
    if not haystack.strip():
        return _FALLBACK_CAUSES
    for keywords, causes in _CAUSE_TABLE:
        if all(keyword in haystack for keyword in keywords):
            return causes
    return _FALLBACK_CAUSES


def build_query(parsed: ParsedError, fallback: str) -> str:
    """检索用的查询串：优先异常类型 + 消息 + 代码片段，避免把整段堆栈塞进去。"""
    parts = [parsed.exception_type or "", parsed.message or "", parsed.code_snippet or ""]
    query = " ".join(part for part in parts if part).strip()
    return query or fallback[:300]


def _first_block(blocks, kind: str):
    return next((block for block in blocks if block.kind == kind), None)


def evidence_coverage(
    diagnosis: GeneralDiagnosis | None,
    chunks: list[RetrievedChunk],
    citations: list[Citation],
) -> str:
    """资料到底有没有讲这条报错：full / partial / none。

    只按分数判"有依据"是不够的：一条讲 NoneType 的资料对 int+str 也是"沾边"，
    但根本没覆盖具体报错，这时必须把结论降级为通用知识。
    """
    if not citations:
        return "none"
    if diagnosis is None:
        return "partial"
    cited_ids = {citation.chunk_id for citation in citations}
    haystack = " ".join(chunk.text for chunk in chunks if chunk.chunk_id in cited_ids).lower()
    return "full" if diagnosis.marker in haystack else "partial"


def build_general(diagnosis: GeneralDiagnosis) -> GeneralKnowledge:
    return GeneralKnowledge(
        label=GENERAL_LABEL,
        pattern=diagnosis.pattern,
        summary=diagnosis.summary,
        causes=diagnosis.causes,
        steps=diagnosis.steps,
    )


def _steps_from(blocks) -> list[str]:
    block = _first_block(blocks, "steps")
    if block is None:
        return []
    steps: list[str] = []
    for line in block.content.splitlines():
        match = re.match(r"^\s*\d+\.\s*(.+)$", line)
        if match:
            steps.append(match.group(1).strip())
    return steps


class ErrorAnalyzer:
    """无状态：所有输入显式传入，便于测试与替换。"""

    def __init__(self) -> None:
        self.engine = TeachingEngine()

    def analyze(
        self,
        text: str,
        source: str,
        ocr: OcrResult | None = None,
        edited: bool = False,
    ) -> ErrorAnalysis:
        parsed = parse_error(text, line_estimated=(source == "image"))
        classification = classify(text)
        query = build_query(parsed, text)
        chunks = get_retriever().search(query, top_k=4, category=classification.category)

        shared = {
            "question": query,
            "category": classification.category,
            "mode": TeachingMode.guided,
            "retrieval": chunks,
        }
        level1 = self.engine.respond(TeachingRequest(current_level=0, target_level=1, **shared))
        level2 = self.engine.respond(TeachingRequest(current_level=1, target_level=2, **shared))

        explain = _first_block(level1.blocks, "explain")
        explanation = explain.content if explain else ""
        steps = _steps_from(level2.blocks)

        diagnosis = diagnose_error(parsed.message or "", parsed.exception_type)
        coverage = evidence_coverage(diagnosis, chunks, level1.citations)
        general = build_general(diagnosis) if diagnosis and coverage != "full" else None

        warnings: list[str] = []
        if source == "image" and not edited:
            warnings.append("以下文字由截图识别得到，行号、变量名与缩进可能不准，请核对后再采信。")
        if ocr is not None and ocr.low_confidence:
            warnings.append("整体识别置信度偏低，建议重点核对异常类型与错误信息。")
        if parsed.missing:
            warnings.append("未能识别：" + "、".join(parsed.missing) + "。可以手动补充后再分析。")
        if level1.insufficient_evidence:
            if general is not None:
                warnings.append(
                    "知识库中没有直接相关的课程资料；下面的原因与步骤来自通用 Python 知识，不引用教材。"
                )
            else:
                warnings.append("知识库中没有检索到直接相关的课程资料，下面的解释属于通用知识。")
        elif coverage != "full" and general is not None:
            warnings.append(
                "课程资料没有直接覆盖这条具体报错；下面的「通用 Python 知识」部分不引用教材，请以课堂要求为准。"
            )
        elif coverage != "full":
            warnings.append("课程资料只覆盖了同类问题，这条具体报错的原因未能从资料中确认。")

        teaching_question = text.strip()[:500] or query
        teaching_entry = TeachingEntry(
            question=teaching_question,
            path=f"/teaching?question={quote(teaching_question, safe='')}",
            level=1,
        )

        # 原因优先用"按报错模式匹配到的具体原因"，而不是泛泛的兜底文案
        causes = diagnosis.causes if diagnosis else causes_for(parsed)
        # 步骤：资料没覆盖时用模式化的具体步骤；覆盖时优先用模型给的（更贴合上下文）
        if diagnosis and coverage != "full":
            resolved_steps = diagnosis.steps
        elif level2.llm_status == "model" and steps:
            resolved_steps = steps
        elif diagnosis and diagnosis.steps:
            resolved_steps = diagnosis.steps
        else:
            resolved_steps = steps

        return ErrorAnalysis(
            source="image" if source == "image" else "text",
            recognized_text=text,
            edited=edited,
            ocr=ocr,
            parsed=parsed,
            category=classification.category.value,
            category_label=classification.label,
            explanation=explanation,
            causes=causes,
            steps=resolved_steps,
            general_knowledge=general,
            evidence_coverage=coverage,
            citations=level1.citations,
            retrieval={
                "query": query,
                "hit_count": len(chunks),
                "sufficient": not level1.insufficient_evidence,
                "coverage": coverage,
                "retriever": "library-first",
            },
            teaching_entry=teaching_entry,
            warnings=warnings,
            safety={
                "code_execution": "disabled",
                "line_numbers": "recognized/uncertain" if source == "image" else "parsed",
                "ocr_labeled": "true" if ocr is not None else "not_applicable",
            },
        )

