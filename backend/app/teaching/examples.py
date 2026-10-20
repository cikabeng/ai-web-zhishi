"""相似例题库（Level 4）。

每一道都是**系统生成**的示例题，不是教材原文，因此：
- 输出时强制带「AI 生成示例」标记；
- 不参与教材引用，避免与检索资料混淆。
"""

from __future__ import annotations

from app.teaching.types import ProblemCategory

SIMILAR_EXAMPLES: dict[ProblemCategory, list[dict[str, str]]] = {
    ProblemCategory.error: [
        {
            "scenario": "一个按学号查学生的函数，查不到时直接走到了函数末尾，没有写任何 return。",
            "problem": "调用 `find_student(999)` 之后紧接着取 `['name']`，程序抛出 "
            "`TypeError: 'NoneType' object is not subscriptable`。请判断：这个 `None` 是从哪一步产生的？",
            "difference": "你的问题是字典取值可能得到 None；这道例题是函数漏了返回值，但两者都属于「对 None 取下标」。",
            "thinking": "如果要消除这个报错，你会改「函数的返回」还是「调用处的取值」？两种改法分别会带来什么副作用？",
        },
        {
            "scenario": "一个读取配置的函数，在配置文件缺少某个字段时提前返回，但外层代码仍按「一定存在」来写。",
            "problem": "运行到 `config['database']['host']` 时报 `TypeError: 'NoneType' object is not subscriptable`。"
            "请先回答：`config['database']` 和 `config` 哪一个可能是 None？",
            "difference": "你的代码里缺失来自数据；这道例题里缺失来自分支控制，但排查方法完全一致。",
            "thinking": "如果只允许你加一行诊断输出，你会打印哪个变量、用什么方式打印？",
        },
    ],
    ProblemCategory.sql: [
        {
            "scenario": "一张学生表里，`class_id` 允许为空，表示「尚未分班」。",
            "problem": "有人写了 `WHERE class_id = NULL`，结果一行都没查出来。请说明：为什么这条条件不会匹配任何行？",
            "difference": "你的问题出在查询写法的细节；这道例题专门考 NULL 的比较语义。",
            "thinking": "如果要查出所有未分班的学生，条件应该怎么写？为什么 `IS NULL` 可以而 `= NULL` 不行？",
        },
        {
            "scenario": "两张表用 LEFT JOIN 关联，右表用来补充班级名称。",
            "problem": "把右表的过滤条件写进 WHERE 之后，左表中没有班级的学生全部消失了。请解释原因。",
            "difference": "你的问题可能与字段名有关；这道例题考的是「条件写在哪里」导致的结果差异。",
            "thinking": "同样一个过滤条件，写在 ON 里和写在 WHERE 里，LEFT JOIN 的结果分别会怎样？",
        },
    ],
    ProblemCategory.web: [
        {
            "scenario": "前端向 `/api/students` 发请求，浏览器控制台出现 CORS 拦截提示，但 Network 面板里请求返回 200。",
            "problem": "既然请求已经成功返回，为什么页面仍然拿不到数据？应当从哪一侧排查？",
            "difference": "你的问题可能出在字段取值；这道例题考的是「请求成功但被浏览器拦截」的典型现象。",
            "thinking": "如果打开 Network 看响应头，你会重点看哪一个响应头？它的值应该包含什么？",
        },
        {
            "scenario": "一个列表页在数据为空时渲染报错：`Cannot read properties of undefined (reading 'map')`。",
            "problem": "请判断：是接口没返回数据，还是组件在数据到达之前就渲染了？你会用哪种方式区分这两种可能？",
            "difference": "你的问题可能出在字段名；这道例题考的是「渲染时机」与「空值保护」。",
            "thinking": "在模板里加一个什么判断，就能区分「还没加载」和「真的为空」？",
        },
    ],
    ProblemCategory.concept: [
        {
            "scenario": "同样一段逻辑，一份代码写成了函数，另一份写成循环里的重复语句。",
            "problem": "请比较：把逻辑封装成函数之后，除了代码变短，还带来了哪些可维护性上的变化？",
            "difference": "你的问题关注某个具体概念的定义；这道例题把概念放进了对比场景。",
            "thinking": "如果这段逻辑以后要改三处，函数版和重复版分别需要改几次？",
        },
        {
            "scenario": "两个变量指向同一个列表，其中一个做了追加操作。",
            "problem": "为什么两个变量打印出来都变了？这和「赋值」与「引用」的区别有什么关系？",
            "difference": "你的问题在问概念本身；这道例题用可观察的现象反推概念。",
            "thinking": "如果希望两个变量互不影响，应该在什么时候创建新的列表？",
        },
    ],
    ProblemCategory.experiment: [
        {
            "scenario": "实验要求在虚拟环境中运行程序，但有人直接在系统环境里执行了。",
            "problem": "程序能跑，但依赖版本与实验要求不一致。请说明：为什么「能跑」不等于「环境正确」？",
            "difference": "你的问题卡在某一步操作；这道例题考的是对实验环境要求的理解。",
            "thinking": "如果要证明当前用的确实是虚拟环境，你会执行什么命令、看什么输出？",
        },
        {
            "scenario": "实验报告要求附上运行截图，但截图里只有程序输出，没有命令行提示符。",
            "problem": "这样的截图为什么可能不被认可？一份可复现的运行记录应该包含哪些信息？",
            "difference": "你的问题在操作步骤；这道例题考的是实验记录规范。",
            "thinking": "如果要让别人照着你的记录复现结果，至少需要写清楚哪三项信息？",
        },
    ],
    ProblemCategory.assignment: [
        {
            "scenario": "题目要求实现一个「学生成绩统计」功能，输入是一组姓名与分数。",
            "problem": "请先把题目拆成 3 个可以单独验证的小步骤，并说明每一步的输入与输出分别是什么。",
            "difference": "你的问题在实现细节；这道例题训练的是「先拆解再编码」的习惯。",
            "thinking": "三个步骤里，哪一步最适合先写出来验证？为什么？",
        },
        {
            "scenario": "题目要求「支持按姓名查询，查不到时给出提示」。",
            "problem": "这句话里藏了几个需要处理的边界情况？请至少列出两个，并说明各自的处理方式。",
            "difference": "你的问题在功能实现；这道例题训练的是需求中的边界分析。",
            "thinking": "如果用户输入了空字符串，你的程序应该走哪条分支？",
        },
    ],
}


def get_example(category: ProblemCategory, variant: int = 0) -> dict[str, str]:
    """按分类取一道相似例题；variant 用于「换一种解释」。"""
    bank = SIMILAR_EXAMPLES[category]
    return bank[variant % len(bank)]
