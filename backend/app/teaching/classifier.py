"""问题分类器：规则打分 + 检索文本加权。

为什么先用规则：
- 无 API Key 也能工作，测试可重复；
- 分类结果可解释（返回命中了哪些信号），前端能展示依据；
- 后续接入大模型时，只需在 `classify` 内部加一路，不改变对外契约。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.teaching.types import (
    CATEGORY_LABELS,
    CategoryOption,
    ClassificationResult,
    ProblemCategory,
)

# 平手时的优先级：越靠前越优先。报错是"最紧"的意图，不能被"作业"盖过。
CATEGORY_PRIORITY: list[ProblemCategory] = [
    ProblemCategory.error,
    ProblemCategory.sql,
    ProblemCategory.web,
    ProblemCategory.experiment,
    ProblemCategory.assignment,
    ProblemCategory.concept,
]

# (正则, 权重, 信号名)
_RULES: dict[ProblemCategory, list[tuple[str, float, str]]] = {
    ProblemCategory.error: [
        (r"traceback \(most recent call last\)", 5.0, "traceback"),
        (r"\b[a-z_]*\w*(?:error|exception)\b", 4.0, "异常类型"),
        (r"报错|异常|调用栈|堆栈|崩溃", 2.5, "报错关键词"),
        (r"\bline \d+\b|第\s*\d+\s*行", 2.0, "行号"),
        (r"none ?type|'nonetype'|undefined|null", 2.0, "空值类型"),
        (r"跑不起来|运行不了|执行失败|报错了", 2.0, "运行失败"),
    ],
    ProblemCategory.sql: [
        (r"\bsql\b", 4.0, "SQL"),
        (r"\b(select|insert|update|delete|join|group\s+by|order\s+by|having|where)\b", 3.0, "SQL 关键字"),
        (r"数据库|数据表|建表|索引|主键|外键|事务|mysql|sqlite|postgres|oracle", 3.0, "数据库术语"),
        (r"\bnull\b|is null|not null", 1.5, "NULL"),
    ],
    ProblemCategory.web: [
        (r"\b(html|css|javascript|js|typescript|vue|react|axios|fetch|flask|django|fastapi)\b", 3.0, "Web 技术栈"),
        (r"跨域|cors|接口|前端|后端|浏览器|dom|路由|组件", 2.0, "Web 术语"),
        (r"\b\w+ is not a function\b|cannot read propert", 2.5, "JS 报错"),
    ],
    ProblemCategory.experiment: [
        (r"实验|实训|上机|课设|课程设计", 3.0, "实验关键词"),
        (r"步骤|流程|怎么运行|环境配置|安装|部署|提交作业|报告", 2.0, "流程关键词"),
        (r"第一次|第二次|第\s*\d+\s*个实验", 1.5, "实验序号"),
    ],
    ProblemCategory.assignment: [
        (r"作业|题目|大作业|课设要求", 3.0, "作业关键词"),
        (r"帮我写|代写|完整代码|给个答案|要答案|实现一下", 3.5, "索取答案"),
        (r"要求|需求|功能点|怎么写|如何实现", 2.0, "需求描述"),
    ],
    ProblemCategory.concept: [
        (r"是什么|什么是|什么意思|原理|区别|为什么|怎么理解|概念|作用", 3.0, "概念问法"),
        (r"闭包|装饰器|递归|多态|继承|指针|范式|事务隔离|索引结构", 1.5, "领域概念"),
    ],
}

_COMPILED: dict[ProblemCategory, list[tuple[re.Pattern[str], float, str]]] = {
    category: [(re.compile(pattern, re.IGNORECASE), weight, signal) for pattern, weight, signal in rules]
    for category, rules in _RULES.items()
}

# 检索文本较弱：只用来打破平手，不能单独决定分类
RETRIEVAL_WEIGHT = 0.4


def _normalize(text: str) -> str:
    # 全角标点转半角，避免 "报错：" 与 "报错:" 命中不一致
    table = str.maketrans({"：": ":", "（": "(", "）": ")", "，": ",", "。": ".", "！": "!", "？": "?"})
    return text.translate(table)


@dataclass
class _Score:
    score: float = 0.0
    signals: list[str] = field(default_factory=list)

    def add(self, weight: float, signal: str) -> None:
        self.score += weight
        if signal not in self.signals:
            self.signals.append(signal)


def classify(question: str, retrieval_text: str = "", category: ProblemCategory | None = None) -> ClassificationResult:
    """返回分类结果。传入 category 时视为用户手动指定，直接采用。"""
    if category is not None:
        label = CATEGORY_LABELS[category]
        return ClassificationResult(
            category=category,
            label=label,
            confidence=1.0,
            options=[CategoryOption(category=category, label=label, confidence=1.0)],
            signals=["用户手动指定"],
            source="user",
        )

    text = _normalize(question)
    scores: dict[ProblemCategory, _Score] = {category: _Score() for category in ProblemCategory}

    for category, rules in _COMPILED.items():
        for pattern, weight, signal in rules:
            if pattern.search(text):
                scores[category].add(weight, signal)

    if retrieval_text:
        normalized_retrieval = _normalize(retrieval_text)
        for category, rules in _COMPILED.items():
            for pattern, weight, signal in rules:
                if pattern.search(normalized_retrieval):
                    # 检索文本只贡献很小的一部分，避免"资料里有 SQL 就把问题判成 SQL"
                    scores[category].add(weight * RETRIEVAL_WEIGHT, f"资料涉及{signal}")

    ranked = sorted(
        scores.items(),
        key=lambda item: (-item[1].score, CATEGORY_PRIORITY.index(item[0])),
    )
    top_category, top_score = ranked[0]
    total = sum(score.score for _, score in ranked) or 1.0

    # 无任何信号时给一个保守的默认值，并明确标注低置信度
    if top_score.score == 0:
        fallback = ProblemCategory.concept
        return ClassificationResult(
            category=fallback,
            label=CATEGORY_LABELS[fallback],
            confidence=0.2,
            options=[
                CategoryOption(category=fallback, label=CATEGORY_LABELS[fallback], confidence=0.2)
            ],
            signals=["未命中明显信号，按概念理解处理"],
            source="auto",
        )

    confidence = round(min(0.95, top_score.score / total + 0.15), 2)
    options = [
        CategoryOption(
            category=category,
            label=CATEGORY_LABELS[category],
            confidence=round(min(0.95, score.score / total), 2) if score.score else 0.0,
        )
        for category, score in ranked
        if score.score > 0
    ][:3]

    return ClassificationResult(
        category=top_category,
        label=CATEGORY_LABELS[top_category],
        confidence=confidence,
        options=options,
        signals=top_score.signals[:4],
        source="auto",
    )
