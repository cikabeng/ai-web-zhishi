"""分层教学引擎。

对外只有一个入口：`TeachingEngine.respond(request)`。
请求里必须显式带上：教学模式、当前层级、检索结果、用户提交内容——引擎不自己猜。
"""

from __future__ import annotations

from app.teaching import templates
from app.teaching.analysis import analyze
from app.teaching.classifier import classify
from app.teaching.examples import get_example
from app.teaching.guards import (
    MAX_SUBMISSION_CHARS,
    code_line_count,
    guard_blocks,
    sanitize_text,
)
from app.teaching.types import (
    CATEGORY_LABELS,
    LEVEL_INTENTS,
    LEVEL_NAMES,
    CheckQuestion,
    Citation,
    ClassificationResult,
    FeedbackBlock,
    HintBlock,
    HintLevel,
    ProblemCategory,
    RetrievedChunk,
    SubmissionFeedback,
    TeachingMode,
    TeachingRequest,
    TeachingResponse,
)

MAX_CITATIONS = 3
SNIPPET_LIMIT = 160
# 只有达到这个分数的片段才允许影响分类，避免"沾边资料"把问题带偏
TRUSTED_RETRIEVAL_SCORE = 0.30


def _trusted_text(chunks: list[RetrievedChunk]) -> str:
    return "\n".join(chunk.text for chunk in chunks if chunk.score >= TRUSTED_RETRIEVAL_SCORE)

# 每类问题在提交反馈里期待出现的关键词（用于判断"有没有抓住重点"）
_FEEDBACK_KEYWORDS: dict[ProblemCategory, list[str]] = {
    ProblemCategory.error: ["none", "return", "print", "type(", "repr(", "is none", "报错", "赋值", "返回"],
    ProblemCategory.sql: ["null", "where", "join", "on ", "group by", "having", "字段", "别名"],
    ProblemCategory.web: ["network", "console", "status", "响应", "请求", "字段", "cors", "跨域"],
    ProblemCategory.concept: ["定义", "区别", "例子", "因为", "所以", "作用"],
    ProblemCategory.experiment: ["环境", "依赖", "步骤", "命令", "目录", "版本"],
    ProblemCategory.assignment: ["输入", "输出", "边界", "步骤", "验证", "条件"],
}

_NEXT_QUESTIONS: dict[ProblemCategory, str] = {
    ProblemCategory.error: "你能指出报错行里，哪个变量最可能是 None 吗？它应该由哪一步给它赋值？",
    ProblemCategory.sql: "你先把这条查询的 WHERE 条件单独拿出来跑一次，结果符合预期吗？",
    ProblemCategory.web: "这次请求在 Network 里是成功还是失败？状态码是多少？",
    ProblemCategory.concept: "你能举一个「用了它」和「不用它」的对比例子吗？",
    ProblemCategory.experiment: "你现在执行到第几步？上一步的输出是什么？",
    ProblemCategory.assignment: "如果只实现最简单的一条分支，你会先写哪一步？",
}


def _clip(text: str, limit: int = SNIPPET_LIMIT) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _location(chunk: RetrievedChunk) -> str:
    """如实标注来源位置：有页码写页码，只有段落写段落，都没有就写未标注。"""
    if chunk.page_from is not None:
        if chunk.page_to is not None and chunk.page_to != chunk.page_from:
            return f"第 {chunk.page_from}–{chunk.page_to} 页"
        return f"第 {chunk.page_from} 页"
    if chunk.paragraph_from is not None:
        return f"第 {chunk.paragraph_from} 段"
    return "未标注位置"


def build_citations(chunks: list[RetrievedChunk], min_score: float) -> list[Citation]:
    """只保留达到分数阈值的块，按分数倒序，去重后取前 N 条。"""
    seen: set[str] = set()
    selected: list[RetrievedChunk] = []
    for chunk in sorted(chunks, key=lambda item: item.score, reverse=True):
        if chunk.score < min_score:
            continue
        if chunk.chunk_id in seen:
            continue
        seen.add(chunk.chunk_id)
        selected.append(chunk)
        if len(selected) >= MAX_CITATIONS:
            break

    return [
        Citation(
            index=index,
            chunk_id=chunk.chunk_id,
            doc_name=chunk.doc_name,
            location=_location(chunk),
            heading=chunk.heading,
            snippet=_clip(chunk.text),
            score=round(chunk.score, 4),
        )
        for index, chunk in enumerate(selected, start=1)
    ]


def _check_question(level: int, category: ProblemCategory, clues: dict[str, str]) -> CheckQuestion:
    if level == 1:
        if category == ProblemCategory.error:
            text = "报错行里被操作的那个变量，实际是什么值？"
            purpose = "确认你是否理解异常指向的对象，而不是急着改代码"
        else:
            text = f"用你自己的话说说：{clues['topic']} 是什么？它解决了什么问题？"
            purpose = "确认概念理解，避免直接进入解法"
    elif level == 2:
        text = "按上面的步骤，第一步你会先检查哪里？为什么先查它？"
        purpose = "确认你能排出检查顺序，而不是逐个试"
    elif level == 3:
        text = "把这个片段放进你的代码后，你预期会看到什么输出？如果不一样，说明什么？"
        purpose = "确认你能读懂片段，并把它当成验证手段而非答案"
    else:
        text = "在这道相似例题里，如果把条件换一下，结果会怎么变？"
        purpose = "确认你能迁移知识点，回到原题独立完成"
    return CheckQuestion(question=text, purpose=purpose)


class TeachingEngine:
    """无状态引擎：所有上下文都从请求里传入，便于测试与并发。

    `llm` 可选：配置了模型且未强制演示模式时，用它润色 L1–L3 的讲解；
    任何失败都回退到模板，并把状态写进响应，界面据此标注。
    """

    def __init__(self, llm=None) -> None:
        if llm is None:
            from app.llm.client import LLMClient

            llm = LLMClient()
        self.llm = llm

    def classify(
        self,
        question: str,
        retrieval: list[RetrievedChunk] | None = None,
        category: ProblemCategory | None = None,
    ) -> ClassificationResult:
        return classify(question, _trusted_text(retrieval or []), category)

    def respond(self, request: TeachingRequest) -> TeachingResponse:
        question = sanitize_text(request.question, 2000)
        classification = classify(question, _trusted_text(request.retrieval), request.category)

        # 核心约束：每次最多推进一级，客户端传更大的值也会被压回去
        ceiling = min(int(HintLevel.L4), request.current_level + 1)
        clamp_reason: str | None = None

        # 引导模式额外约束：进入 L3（局部示例）前必须先提交自己的尝试
        if (
            request.mode is TeachingMode.guided
            and request.submission is None
            and ceiling >= int(HintLevel.L3)
        ):
            ceiling = int(HintLevel.L2)
            clamp_reason = "guided_requires_attempt"

        level = min(request.target_level, ceiling)
        clamped = level != request.target_level
        if clamped and clamp_reason is None:
            clamp_reason = "max_one_level_per_step"

        citations = build_citations(request.retrieval, request.min_evidence_score)
        insufficient = not citations

        clues = analyze(question, classification.category)
        variant = request.variant + 1 if request.action == "rephrase" else request.variant

        example = get_example(classification.category, variant) if level == 4 else None
        blocks = templates.build_level(
            level=level,
            category=classification.category,
            clues=clues,
            citations=citations,
            variant=variant,
            mode=request.mode.value,
            insufficient=insufficient,
            example=example,
        )
        # 配置了模型时，用模型润色 L1–L3 的讲解；失败一律回退模板
        llm_status = "template"
        llm_model: str | None = None
        if self.llm is not None and getattr(self.llm, "available", False) and level in (1, 2, 3):
            llm_model = getattr(self.llm, "model_name", None)
            try:
                text = self.llm.compose_hint(
                    question=question,
                    level=level,
                    category_label=CATEGORY_LABELS[classification.category],
                    mode=request.mode.value,
                    chunks=request.retrieval,
                    attempt=request.submission.text if request.submission else None,
                )
                if self._apply_llm(blocks, level, text):
                    llm_status = "model"
                else:
                    llm_status = "fallback"
            except Exception:
                # 超时、限流、返回结构不符……都退回模板，保证演示不中断
                llm_status = "fallback"

        blocks, safety = guard_blocks(blocks)

        if clamp_reason == "guided_requires_attempt":
            blocks.insert(
                0,
                HintBlock(
                    kind="note",
                    title="需要先提交尝试",
                    content="引导模式下，进入 L3（局部示例）前请先在下方写下你的思路或代码片段。"
                    "这不是考核，而是为了让提示真正帮到你。",
                    meta={"reason": "guided_requires_attempt"},
                ),
            )

        allowed: list[str] = ["understood", "continue", "rephrase", "submit"]
        if level >= int(HintLevel.L4):
            allowed = ["understood", "rephrase", "submit"]

        safety.update(
            {
                "escalation": "max_one_level_per_step",
                "example_label": templates.AI_EXAMPLE_LABEL if level == 4 else "none",
                "mode": request.mode.value,
                "llm": llm_status,
            }
        )

        return TeachingResponse(
            question=question,
            mode=request.mode,
            category=classification.category,
            category_label=CATEGORY_LABELS[classification.category],
            category_source=classification.source,
            category_confidence=classification.confidence,
            category_options=classification.options,
            requested_level=request.target_level,
            level=level,
            level_name=LEVEL_NAMES[level],
            level_intent=LEVEL_INTENTS[level],
            clamped=clamped,
            clamp_reason=clamp_reason,  # type: ignore[arg-type]
            blocks=blocks,
            citations=citations,
            check_question=_check_question(level, classification.category, clues),
            allowed_actions=allowed,  # type: ignore[arg-type]
            next_level=level + 1 if level < int(HintLevel.L4) else None,
            insufficient_evidence=insufficient,
            example_generated=level == 4,
            llm_status=llm_status,  # type: ignore[arg-type]
            llm_model=llm_model,
            safety=safety,
        )

    @staticmethod
    def _apply_llm(blocks: list[HintBlock], level: int, text: str) -> bool:
        """把模型生成的讲解替换进对应块：L1/L3 换 explain，L2 换 steps。"""
        target = "steps" if level == 2 else "explain"
        for block in blocks:
            if block.kind == target:
                block.content = text
                block.meta["source"] = "llm"
                return True
        return False

    def feedback(self, request: TeachingRequest) -> SubmissionFeedback:
        """针对学生的代码/思路给出反馈。只做文本分析，绝不执行代码。"""
        if request.submission is None:
            raise ValueError("缺少 submission 内容")

        text = sanitize_text(request.submission.text, MAX_SUBMISSION_CHARS)
        truncated = len(request.submission.text) > MAX_SUBMISSION_CHARS
        retrieval_text = "\n".join(chunk.text for chunk in request.retrieval)
        classification = classify(request.question, retrieval_text, request.category)
        lowered = text.lower()

        keywords = _FEEDBACK_KEYWORDS[classification.category]
        hits = [keyword.strip() for keyword in keywords if keyword in lowered]
        is_code = request.submission.kind == "code"
        lines = code_line_count(text) if is_code else 0

        if len(hits) >= 2:
            verdict = "on_track"
            summary = "你抓住了关键线索，方向是对的。"
        elif hits:
            verdict = "partial"
            summary = "你抓到了一部分线索，但还差一点。"
        else:
            verdict = "off_track"
            summary = "目前还看不出你在检查关键位置，先回到报错本身。"

        blocks: list[FeedbackBlock] = []
        if hits:
            blocks.append(
                FeedbackBlock(kind="affirm", text=f"你提到了：{ '、'.join(hits[:3]) }，这些确实是判断依据。")
            )
        else:
            blocks.append(
                FeedbackBlock(
                    kind="question",
                    text="先别改代码：把报错行用到的那几个变量的真实值打印出来，再回来告诉我结果。",
                )
            )

        if is_code:
            if lines > 40:
                blocks.append(
                    FeedbackBlock(kind="warning", text=f"这段代码有 {lines} 行，建议缩小到能复现问题的最小片段。")
                )
            if classification.category == ProblemCategory.error and "print" not in lowered:
                blocks.append(
                    FeedbackBlock(
                        kind="question",
                        text="这段代码里没有看到任何打印或日志。你怎么确认那个变量是不是 None？",
                    )
                )
        elif len(text) < 15:
            blocks.append(
                FeedbackBlock(kind="warning", text="描述太短了。试着写清楚：你观察到了什么、你猜原因是什么。")
            )

        if truncated:
            blocks.append(FeedbackBlock(kind="warning", text="提交内容过长，已截断后分析。"))

        blocks.append(
            FeedbackBlock(kind="question", text=_NEXT_QUESTIONS[classification.category])
        )

        return SubmissionFeedback(
            verdict=verdict,
            summary=summary,
            blocks=blocks,
            next_question=_NEXT_QUESTIONS[classification.category],
            safety={
                "code_execution": "disabled",
                "analysis": "text_only",
                "truncated": "yes" if truncated else "no",
            },
        )
