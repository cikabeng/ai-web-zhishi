"""分层教学引擎的 HTTP 接口。

这里只做协议转换与默认检索的补齐，教学逻辑全部在 `app.teaching` 里，
方便单独测试，也方便以后换成大模型生成而不用改接口。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.retrieval.service import get_retriever
from app.teaching.engine import TeachingEngine
from app.teaching.types import (
    CATEGORY_DESCRIPTIONS,
    CATEGORY_LABELS,
    LEVEL_INTENTS,
    LEVEL_NAMES,
    MODE_LABELS,
    ClassificationResult,
    ProblemCategory,
    RetrievedChunk,
    SubmissionFeedback,
    TeachingMode,
    TeachingRequest,
    TeachingResponse,
)

router = APIRouter(prefix="/teaching", tags=["teaching"])
engine = TeachingEngine()

DEMO_QUESTION = (
    "运行 Python 时报错：TypeError: 'NoneType' object is not subscriptable。"
    "代码里先执行 info = get_student('李四')，然后 print(info['score'])，"
    "get_student 在查不到时会走到函数末尾。这种情况怎么排查？"
)


class ClassifyRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    retrieval: list[RetrievedChunk] = Field(default_factory=list)


def _retrieve(question: str, category: ProblemCategory | None = None) -> list[RetrievedChunk]:
    """先分类，再按分类路由到对应课程文档检索。

    这是 P1 用 Chroma 做元数据过滤的雏形；分类来自真实分类器，不是写死的。
    """
    resolved = category or engine.classify(question).category
    return get_retriever().search(question, top_k=4, category=resolved)


@router.get("/categories", summary="六类问题及其说明")
def list_categories() -> list[dict[str, str]]:
    return [
        {
            "value": category.value,
            "label": CATEGORY_LABELS[category],
            "description": CATEGORY_DESCRIPTIONS[category],
        }
        for category in ProblemCategory
    ]


@router.get("/levels", summary="四级提示的定义")
def list_levels() -> list[dict[str, str | int]]:
    return [
        {"level": level, "name": LEVEL_NAMES[level], "intent": LEVEL_INTENTS[level]}
        for level in sorted(LEVEL_NAMES)
    ]


@router.get("/modes", summary="两种教学模式")
def list_modes() -> list[dict[str, str]]:
    return [{"value": mode.value, "label": MODE_LABELS[mode]} for mode in TeachingMode]


@router.post("/classify", response_model=ClassificationResult, summary="问题分类（可被用户覆盖）")
def classify_question(payload: ClassifyRequest) -> ClassificationResult:
    retrieval = payload.retrieval or _retrieve(payload.question)
    return engine.classify(payload.question, retrieval)


@router.post("/hint", response_model=TeachingResponse, summary="获取某一层提示")
def get_hint(payload: TeachingRequest) -> TeachingResponse:
    if not payload.retrieval:
        # 客户端没带检索结果时，用当前可用的检索器补齐，保证引用是真实检索出来的
        payload = payload.model_copy(update={"retrieval": _retrieve(payload.question, payload.category)})
    return engine.respond(payload)


@router.post("/feedback", response_model=SubmissionFeedback, summary="对学生提交的代码或思路给出反馈")
def get_feedback(payload: TeachingRequest) -> SubmissionFeedback:
    if payload.submission is None:
        raise HTTPException(status_code=400, detail="请求缺少 submission 字段")
    if not payload.retrieval:
        payload = payload.model_copy(update={"retrieval": _retrieve(payload.question, payload.category)})
    return engine.feedback(payload)


@router.get("/demo-case", summary="演示用问题与真实检索结果")
def demo_case() -> dict[str, object]:
    retrieval = _retrieve(DEMO_QUESTION)
    return {
        "question": DEMO_QUESTION,
        "retrieval": [chunk.model_dump() for chunk in retrieval],
        "retriever": "keyword（临时：字面匹配，P1 换 Chroma 向量检索）",
    }

