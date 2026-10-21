"""分层教学引擎的数据契约。

设计要点：
- 引擎**不依赖**检索实现，检索结果作为显式入参传入（P1 换成 Chroma 也不需要改这里）。
- 提示级别是受限的整数，服务端强制"每次只能 +1"，客户端无法跳级。
"""

from __future__ import annotations

from enum import Enum, IntEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ProblemCategory(str, Enum):
    """六类问题。"""

    concept = "concept"
    error = "error"
    experiment = "experiment"
    sql = "sql"
    web = "web"
    assignment = "assignment"


CATEGORY_LABELS: dict[ProblemCategory, str] = {
    ProblemCategory.concept: "概念理解",
    ProblemCategory.error: "编程报错",
    ProblemCategory.experiment: "实验步骤",
    ProblemCategory.sql: "数据库与 SQL",
    ProblemCategory.web: "Web 开发",
    ProblemCategory.assignment: "作业思路",
}

CATEGORY_DESCRIPTIONS: dict[ProblemCategory, str] = {
    ProblemCategory.concept: "解释定义、原理与概念之间的区别",
    ProblemCategory.error: "定位异常来源，给出排查路径",
    ProblemCategory.experiment: "实验流程、环境配置与操作顺序",
    ProblemCategory.sql: "查询写法、表结构问题与 SQL 报错",
    ProblemCategory.web: "前端页面、接口调用与跨域问题",
    ProblemCategory.assignment: "拆解题目要求，规划实现路径",
}


class HintLevel(IntEnum):
    """四级提示。数值即层级，便于做 +1 校验。"""

    L1 = 1
    L2 = 2
    L3 = 3
    L4 = 4


LEVEL_NAMES: dict[int, str] = {
    1: "知识点提示",
    2: "解题思路",
    3: "局部示例",
    4: "相似例题",
}

LEVEL_INTENTS: dict[int, str] = {
    1: "解释涉及的概念，并引用课程资料，不给解法",
    2: "给出分步骤的思考方法，指出先检查什么",
    3: "给出最小必要的代码片段，并解释关键语句",
    4: "给出知识点相同但条件不同的示例题",
}


class TeachingMode(str, Enum):
    study = "study"
    guided = "guided"


MODE_LABELS: dict[TeachingMode, str] = {
    TeachingMode.study: "学习模式",
    TeachingMode.guided: "引导模式",
}


class RetrievedChunk(BaseModel):
    """检索到的一个文本块。缺失的元数据保持 None，界面如实显示"未标注"。"""

    chunk_id: str
    doc_name: str
    text: str
    score: float = 0.0
    page_from: int | None = None
    page_to: int | None = None
    paragraph_from: int | None = None
    heading: str | None = None


class StudentSubmission(BaseModel):
    """学生提交的代码或思路。只做文本分析，绝不执行。"""

    kind: Literal["code", "thinking"] = "thinking"
    text: str = Field(min_length=1, max_length=4000)

    @field_validator("text")
    @classmethod
    def _clean(cls, value: str) -> str:
        cleaned = value.replace("\r\n", "\n").strip()
        if not cleaned:
            raise ValueError("提交内容不能为空")
        return cleaned


class TeachingRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    mode: TeachingMode = TeachingMode.guided
    category: ProblemCategory | None = Field(
        default=None, description="用户手动指定的分类；为空则由引擎自动分类"
    )
    current_level: int = Field(default=0, ge=0, le=4, description="学生当前所处层级，0 表示还没开始")
    target_level: int = Field(default=1, ge=1, le=4, description="希望获取的层级，服务端会做 +1 限制")
    variant: int = Field(default=0, ge=0, le=5, description="换一种解释时递增")
    action: Literal["open", "continue", "rephrase", "understood"] = "open"
    min_evidence_score: float = Field(default=0.15, ge=0.0, le=1.0)
    retrieval: list[RetrievedChunk] = Field(
        default_factory=list, description="检索结果由调用方显式传入，引擎不自己检索"
    )
    submission: StudentSubmission | None = None

    @field_validator("question")
    @classmethod
    def _clean_question(cls, value: str) -> str:
        cleaned = value.replace("\r\n", "\n").strip()
        if not cleaned:
            raise ValueError("问题不能为空")
        return cleaned


class Citation(BaseModel):
    index: int
    chunk_id: str
    doc_name: str
    location: str = Field(description="例如「第 3 页」「第 12 段」「未标注位置」")
    heading: str | None = None
    snippet: str
    score: float = 0.0


class HintBlock(BaseModel):
    kind: Literal["explain", "steps", "code", "example", "evidence", "limit", "note", "feedback"]
    title: str
    content: str = Field(description="Markdown 文本")
    citations: list[int] = Field(default_factory=list, description="本块引用的 citation 序号")
    meta: dict[str, str] = Field(default_factory=dict)


class CheckQuestion(BaseModel):
    question: str
    purpose: str


class CategoryOption(BaseModel):
    category: ProblemCategory
    label: str
    confidence: float


class ClassificationResult(BaseModel):
    category: ProblemCategory
    label: str
    confidence: float
    options: list[CategoryOption]
    signals: list[str]
    source: Literal["auto", "user"] = "auto"


class TeachingResponse(BaseModel):
    question: str
    mode: TeachingMode
    category: ProblemCategory
    category_label: str
    category_source: Literal["auto", "user"]
    category_confidence: float
    category_options: list[CategoryOption]

    requested_level: int
    level: int
    level_name: str
    level_intent: str
    clamped: bool = Field(description="请求层级被服务端限制时为 true")
    clamp_reason: Literal["max_one_level_per_step", "guided_requires_attempt"] | None = None

    blocks: list[HintBlock]
    citations: list[Citation]
    check_question: CheckQuestion
    allowed_actions: list[Literal["understood", "continue", "rephrase", "submit"]]
    next_level: int | None
    insufficient_evidence: bool
    example_generated: bool
    llm_status: Literal["model", "template", "fallback"] = "template"
    llm_model: str | None = None
    safety: dict[str, str]


class FeedbackBlock(BaseModel):
    kind: Literal["affirm", "question", "warning"]
    text: str


class SubmissionFeedback(BaseModel):
    verdict: Literal["on_track", "partial", "off_track"]
    summary: str
    blocks: list[FeedbackBlock]
    next_question: str
    safety: dict[str, str]
