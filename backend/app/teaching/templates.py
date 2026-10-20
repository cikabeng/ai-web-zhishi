"""四级提示的内容构造。

设计约束（每一条都有对应测试）：
- L1 只有概念解释与引用，**不出现代码块**；
- L2 只有步骤，**不出现代码块**；
- L3 有代码块，但有效行数 ≤ 6，且不构成完整实现；
- L4 是系统生成的相似例题，**必须带「AI 生成示例」标记**，且不冒充教材。
"""

from __future__ import annotations

from app.teaching.types import HintBlock, ProblemCategory

AI_EXAMPLE_LABEL = "AI 生成示例"

# ---------------------------------------------------------------- 文案素材

_STEP_TEMPLATES: dict[ProblemCategory, list[str]] = {
    ProblemCategory.error: [
        "从 traceback 的最后一行读起，先确认异常类型和出错的那个操作。",
        "在 traceback 里找到第一处属于你自己代码的行号，报错通常就发生在那里。",
        "确认这一行用到的变量从哪里来：函数返回值、字典取值，还是外部数据？",
        "在出错行之前打印它的类型与真实值，验证你的猜测，而不是凭感觉改。",
        "回到来源处检查：是不是有分支没有返回？取不到值时有没有兜底？",
        "改完重新运行，确认报错消失，并且结果符合预期。",
    ],
    ProblemCategory.sql: [
        "先把最内层的子查询单独跑一遍，确认它返回的数据形态。",
        "核对字段名与表名，确认没有拼写错误、也没有漏掉别名前缀。",
        "检查 NULL 相关条件：是否写成了 `= NULL`，应该用 `IS NULL`。",
        "检查过滤条件放在 `ON` 还是 `WHERE`，这会改变 LEFT JOIN 的结果。",
        "再逐步加上 JOIN，每加一步观察行数是否按预期变化。",
    ],
    ProblemCategory.web: [
        "打开开发者工具的 Console，读第一条红色错误，后面的常是连锁反应。",
        "打开 Network，找到对应请求，依次看状态码、响应头和响应体。",
        "对照接口文档检查 URL、请求方法、字段名与字段类型。",
        "用最小请求验证接口本身是否正常，排除前端拼参数的问题。",
        "区分三种情况：请求没发出、请求失败、还是数据到了但渲染出错。",
    ],
    ProblemCategory.concept: [
        "先用一句话写下你现在的理解，哪怕是错的。",
        "找出这个概念解决什么问题，以及什么场景下不该用它。",
        "对照资料里的表述，看看你的理解差在哪一句。",
        "用一个最小例子复述它，例子越具体越好。",
        "再想一个「如果不用它会怎样」的对比场景。",
    ],
    ProblemCategory.experiment: [
        "先明确这次实验要交付什么：代码、结果，还是报告。",
        "确认环境前提：解释器版本、依赖是否安装、工作目录是否正确。",
        "按资料顺序执行，每一步都确认输出，不要跳步。",
        "把命令和输出记录下来，方便自己复现，也方便别人复现。",
        "报错时回到上一个成功的步骤，从那里重新开始。",
    ],
    ProblemCategory.assignment: [
        "把题目拆成输入、处理、输出三部分，分别写清楚。",
        "列出边界情况：空输入、重复数据、非法值，各自应该怎么处理。",
        "先写一个能验证的最小步骤，跑通再往下写。",
        "每完成一步就运行一次，不要全部写完再调试。",
        "最后再考虑代码结构与命名，先保证逻辑正确。",
    ],
}

_SNIPPETS: dict[ProblemCategory, tuple[str, list[str]]] = {
    ProblemCategory.error: (
        "value = info          # 换成你怀疑是 None 的那个变量\n"
        "print(type(value), repr(value))",
        [
            "`type()` 告诉你它是哪种类型，`repr()` 显示原始值，`None` 会直接显示为 `None`。",
            "把这一行放在报错行之前，就能确认「是不是它」。",
        ],
    ),
    ProblemCategory.sql: (
        "SELECT id, name, class_id\n"
        "FROM students\n"
        "WHERE name = '李四';",
        [
            "先只查关键字段，确认数据本身长什么样。",
            "把结果与你的预期逐列对照，再决定问题在条件还是数据。",
        ],
    ),
    ProblemCategory.web: (
        "const res = await fetch('/api/students')\n"
        "console.log('status', res.status)\n"
        "console.log('body', await res.text())",
        [
            "`status` 用来区分请求是否成功。",
            "`text()` 打印原始响应，能看清后端返回的错误信息。",
        ],
    ),
    ProblemCategory.concept: (
        "x = []\n"
        "y = x\n"
        "y.append(1)\n"
        "print(x)   # 先写下你的预期",
        [
            "先预测输出，再运行，差异就是理解偏差所在。",
            "把 `y = x` 换成 `y = list(x)` 再对比一次。",
        ],
    ),
    ProblemCategory.experiment: (
        "python -m venv .venv\n"
        ".venv\\Scripts\\python.exe -m pip list",
        [
            "第一行创建独立环境，第二行确认依赖装在了这个环境里。",
            "如果提示找不到解释器，先检查当前目录与路径拼写。",
        ],
    ),
    ProblemCategory.assignment: (
        "# 先把输入输出写成注释，再写实现\n"
        "# 输入：\n"
        "# 输出：",
        [
            "写清输入输出，能避免「写完了才发现理解错了题目」。",
            "注释里留空的地方，就是你需要先想清楚的部分。",
        ],
    ),
}


# ---------------------------------------------------------------- 小工具


def _quote(citation) -> str:
    return f"《{citation.doc_name}》{citation.location}：『{citation.snippet}』[{citation.index}]"


def _evidence_block(citations, title: str = "课程资料依据") -> HintBlock:
    lines = [f"- {_quote(citation)}" for citation in citations]
    return HintBlock(
        kind="evidence",
        title=title,
        content="\n".join(lines),
        citations=[citation.index for citation in citations],
    )


# ---------------------------------------------------------------- Level 1


def level1(
    *,
    category: ProblemCategory,
    clues: dict[str, str],
    citations,
    variant: int,
    mode: str,
    insufficient: bool,
) -> list[HintBlock]:
    topic = clues["topic"]
    meaning = clues["meaning"]
    focus = clues["focus"]

    if category == ProblemCategory.error:
        if variant % 2 == 0:
            body = "这道题的关键不在「怎么写」，而在「那一刻变量到底是什么」。"
            if meaning:
                body += f"\n\n{meaning}"
            body += "\n\n先不要改代码：找到报错行，确认被方括号访问的那个变量，它到底是不是 `None`。"
        else:
            body = (
                "换一个角度：把报错想成「程序运行到这一步时，手里拿到的东西和你想的不一样」。"
            )
            if meaning:
                body += f"\n\n{meaning}"
            body += "\n\n你要确认的是那个变量的真实值，而不是急着换一种写法。"
    elif variant % 2 == 0:
        body = f"这道题的关键在 **{focus}**。"
        if meaning:
            body += f"\n\n{meaning}"
        body += (
            f"\n\n先不要改代码。你要判断的是：`{topic}` 出现的位置，"
            f"和你以为的那个对象是不是同一个。"
        )
    else:
        body = (
            f"换一个说法：把 **{topic}** 想成「程序运行到这一步时，手里实际拿到的东西」。\n\n"
            f"你现在要确认的不是「代码应该怎么写」，而是「那一刻它到底是什么」。"
        )
        if meaning:
            body += f"\n\n{meaning}"

    blocks = [HintBlock(kind="explain", title=f"知识点：{topic}", content=body)]

    if citations:
        blocks.append(_evidence_block(citations[:2]))
    else:
        blocks.append(
            HintBlock(
                kind="limit",
                title="资料范围提示",
                content="知识库里没有检索到与这道题直接相关的课程资料，下面的解释属于通用知识，**不是**你的课程材料。",
            )
        )

    if insufficient:
        blocks.append(
            HintBlock(
                kind="limit",
                title="检索不足",
                content="当前依据不足：建议补充相关教材或实验指导后再提问，或把报错上下文补全。",
            )
        )

    note = "这一级只解释概念，不提供解法。"
    if mode == "guided":
        note += "先回答下面的小问题，再决定要不要继续。"
    blocks.append(HintBlock(kind="note", title="说明", content=note, meta={"level": "1"}))
    return blocks


# ---------------------------------------------------------------- Level 2


def level2(
    *,
    category: ProblemCategory,
    clues: dict[str, str],
    citations,
    variant: int,
    mode: str,
    insufficient: bool,
) -> list[HintBlock]:
    steps = _STEP_TEMPLATES[category]
    if variant % 2 == 1:
        steps = list(reversed(steps))

    lines = [f"{index}. {step}" for index, step in enumerate(steps, start=1)]
    intro = "按顺序做，每一步都可以停下来验证，不要一次改很多地方。"
    if mode == "guided":
        intro = "先别急着写代码。按下面的顺序检查，每做完一步就停下来确认一次。"

    blocks = [
        HintBlock(
            kind="steps",
            title="分步排查思路",
            content=intro + "\n\n" + "\n".join(lines),
        )
    ]

    if citations:
        refs = "、".join(f"[{citation.index}]" for citation in citations[:3])
        blocks.append(
            HintBlock(
                kind="note",
                title="对照资料",
                content=f"上面每一步如果想不起具体做法，可以回看课程资料 {refs}。",
                citations=[citation.index for citation in citations[:3]],
            )
        )

    if insufficient:
        blocks.append(
            HintBlock(
                kind="limit",
                title="检索不足",
                content="本级的步骤是通用排查方法，没有对应的课程资料支撑，请结合课堂内容核对。",
            )
        )

    blocks.append(
        HintBlock(kind="note", title="说明", content="这一级只给思路，不给代码。", meta={"level": "2"})
    )
    return blocks


# ---------------------------------------------------------------- Level 3


def level3(
    *,
    category: ProblemCategory,
    clues: dict[str, str],
    citations,
    variant: int,
    mode: str,
    insufficient: bool,
) -> list[HintBlock]:
    code, explanations = _SNIPPETS[category]
    if variant % 2 == 1:
        explanations = list(reversed(explanations))

    blocks = [
        HintBlock(
            kind="code",
            title="最小验证片段",
            content=code,
            meta={"language": "sql" if category == ProblemCategory.sql else "python" if category == ProblemCategory.error else "text"},
        ),
        HintBlock(
            kind="explain",
            title="关键语句说明",
            content="\n".join(f"- {item}" for item in explanations),
        ),
    ]

    if citations:
        blocks.append(
            HintBlock(
                kind="evidence",
                title="对应知识点",
                content=_quote(citations[0]),
                citations=[citations[0].index],
            )
        )

    if insufficient:
        blocks.append(
            HintBlock(
                kind="limit",
                title="检索不足",
                content="这个片段是通用诊断写法，不是从你的课程资料里摘出来的。",
            )
        )

    blocks.append(
        HintBlock(
            kind="note",
            title="使用边界",
            content="这是用于验证猜想的诊断片段，**不是这道题的答案**；把它拼进作业不会得分。",
            meta={"level": "3"},
        )
    )
    return blocks


# ---------------------------------------------------------------- Level 4


def level4(
    *,
    category: ProblemCategory,
    clues: dict[str, str],
    citations,
    variant: int,
    mode: str,
    insufficient: bool,
    example: dict[str, str],
) -> list[HintBlock]:
    content = (
        f"**场景**：{example['scenario']}\n\n"
        f"**示例问题**：{example['problem']}\n\n"
        f"**和你的问题相比**：{example['difference']}\n\n"
        f"**先想一想**：{example['thinking']}"
    )

    blocks = [
        HintBlock(
            kind="example",
            title=f"相似例题（{AI_EXAMPLE_LABEL} · 非教材原文）",
            content=content,
            meta={"generated_by_ai": "true", "source": "system", "label": AI_EXAMPLE_LABEL},
        )
    ]

    if citations:
        blocks.append(
            HintBlock(
                kind="evidence",
                title="知识点出处",
                content=f"例题本身由系统生成，但涉及的知识点可以参考 {_quote(citations[0])}",
                citations=[citations[0].index],
            )
        )

    if insufficient:
        blocks.append(
            HintBlock(
                kind="limit",
                title="检索不足",
                content="当前没有可引用的课程资料，这道例题仅用于练习，不代表课程要求。",
            )
        )

    blocks.append(
        HintBlock(
            kind="note",
            title="标记说明",
            content=f"这道题由系统生成（{AI_EXAMPLE_LABEL}），不是教材原文，也不作为作业答案。做完它，再回到原题独立完成。",
            meta={"level": "4"},
        )
    )
    return blocks


def build_level(
    *,
    level: int,
    category: ProblemCategory,
    clues: dict[str, str],
    citations,
    variant: int,
    mode: str,
    insufficient: bool,
    example: dict[str, str] | None = None,
) -> list[HintBlock]:
    common = {
        "category": category,
        "clues": clues,
        "citations": citations,
        "variant": variant,
        "mode": mode,
        "insufficient": insufficient,
    }
    if level == 1:
        return level1(**common)
    if level == 2:
        return level2(**common)
    if level == 3:
        return level3(**common)
    return level4(**common, example=example or {})
