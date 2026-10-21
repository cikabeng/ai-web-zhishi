"""通用 Python 错误诊断（不引用教材，输出必须带标注）。

为什么需要这一层：
课程资料永远覆盖不全。如果只允许"有资料才回答"，学生遇到常见报错（比如
`unsupported operand type(s) for +: 'int' and 'str'`）就会被拒答。
这一层给出**明确的通用知识**，并且：
- 不产生任何 [n] 引用，避免冒充教材来源；
- 调用方必须把 label 展示出来，不能悄悄混进"课程结论"。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

GENERAL_LABEL = "通用 Python 知识（非课程资料）"


@dataclass(frozen=True)
class GeneralDiagnosis:
    pattern: str
    marker: str
    summary: str
    causes: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)


_OPERAND = re.compile(r"unsupported operand type\(s\) for (\S+?):\s*'([^']+)' and '([^']+)'", re.I)
_CONCAT = re.compile(r'can only concatenate str \(not "([^"]+)"\) to str', re.I)
_NOT_SUB = re.compile(r"'([\w.]+)' object is not subscriptable", re.I)
_NOT_CALLABLE = re.compile(r"'([\w.]+)' object is not callable", re.I)
_NOT_ITERABLE = re.compile(r"'([\w.]+)' object is not iterable", re.I)
_NO_ATTR = re.compile(r"'([\w.]+)' object has no attribute '(\w+)'", re.I)
_INDEX_RANGE = re.compile(r"(?:list|tuple|string) index out of range", re.I)
_INT_LITERAL = re.compile(r"invalid literal for int\(\) with base 10: '([^']*)'", re.I)
_INDENT = re.compile(r"(unexpected indent|expected an indented block|unindent does not match)", re.I)
_ARGS = re.compile(r"takes (\d+) positional arguments? but (\d+) (?:was|were) given", re.I)
_ZERO_DIV = re.compile(r"(division by zero|float division by zero|integer division or modulo by zero)", re.I)
_MODULE_MISSING = re.compile(r"No module named '([^']+)'", re.I)
_NAME_ERROR = re.compile(r"name '([^']+)' is not defined", re.I)
_KEY_ERROR = re.compile(r"KeyError:\s*'?([^'\n]+)'?", re.I)

# 这些短语出现在资料里，才说明资料真的讲到了这类报错
MARKERS: dict[str, str] = {
    "operand_type": "unsupported operand",
    "concat": "concatenate str",
    "not_subscriptable": "not subscriptable",
    "not_callable": "not callable",
    "not_iterable": "not iterable",
    "no_attribute": "has no attribute",
    "index_range": "index out of range",
    "int_literal": "invalid literal for int",
    "indent": "indent",
    "args": "positional argument",
    "zero_division": "division by zero",
    "module_missing": "no module named",
    "name_error": "is not defined",
    "key_error": "keyerror",
}

_TYPE_NAMES = {
    "int": "整数",
    "float": "浮点数",
    "str": "字符串",
    "list": "列表",
    "dict": "字典",
    "NoneType": "None（空值）",
    "bool": "布尔值",
}


def _type_name(value: str) -> str:
    return _TYPE_NAMES.get(value, value)


def diagnose_error(message: str, exception_type: str | None = None) -> GeneralDiagnosis | None:
    """按报错文本匹配常见模式；匹配不到返回 None，不做臆测。"""
    text = (message or "").strip()
    if not text:
        return None

    match = _OPERAND.search(text)
    if match:
        operator, left, right = match.group(1), match.group(2), match.group(3)
        return GeneralDiagnosis(
            pattern="operand_type",
            marker=MARKERS["operand_type"],
            summary=(
                f"你把 {left}（{_type_name(left)}）和 {right}（{_type_name(right)}）用 `{operator}` 运算了。"
                "Python 不会自动做类型转换：字符串 `\"2\"` 不会变成数字 2，数字也不会自动变成字符串。"
            ),
            causes=[
                f"参与 `{operator}` 的两边类型不同：一边是 {left}，一边是 {right}",
                "数据来自 input() 或接口时，拿到的其实是字符串",
                "函数参数没有做类型统一，调用方传什么就用什么",
            ],
            steps=[
                "在运算前打印 `type(a)`、`type(b)`，确认两边真实类型",
                "按业务语义显式转换：要算术就用 `int(b)`，要拼接就用 `str(a)`",
                "记住 `input()` 一律返回字符串，即使输入的是数字",
                "转换处要处理非法输入（`int('abc')` 会抛 ValueError）",
            ],
        )

    match = _CONCAT.search(text)
    if match:
        other = match.group(1)
        return GeneralDiagnosis(
            pattern="concat",
            marker=MARKERS["concat"],
            summary=f"你在用 `+` 拼接字符串，但另一边是 {_type_name(other)}；字符串只能和字符串直接相加。",
            causes=[f"拼接时混入了 {_type_name(other)} 类型的值", "拼接前没有把非字符串转成字符串"],
            steps=["用 `str(x)` 显式转换后再拼接", "或者改用 f-string：`f\"{x}\"`", "确认要的是拼接还是数值相加"],
        )

    match = _NOT_CALLABLE.search(text)
    if match:
        type_name = match.group(1)
        return GeneralDiagnosis(
            pattern="not_callable",
            marker=MARKERS["not_callable"],
            summary=f"你把一个 `{type_name}` 当函数调用了，但它不是函数（例如变量名和函数名重名、或忘了写括号）。",
            causes=["变量被同名值覆盖，调用时已经不是函数", "函数名拼写被解析成变量", "把属性当成了方法但少了括号"],
            steps=["打印这个变量看看它是什么（`print(x, type(x))`）", "检查是否用同名变量覆盖了函数", "检查调用处是否漏了括号"],
        )

    match = _NOT_ITERABLE.search(text)
    if match:
        type_name = match.group(1)
        return GeneralDiagnosis(
            pattern="not_iterable",
            marker=MARKERS["not_iterable"],
            summary=f"你对一个 `{type_name}` 做了迭代（for 循环或解包），但它不是可迭代对象。",
            causes=["变量是 None 或数字，却被放进 for 循环", "函数返回值和预期不一致"],
            steps=["打印变量确认真实类型", "检查循环对象的来源", "必要时先判空再遍历"],
        )

    match = _NOT_SUB.search(text)
    if match:
        type_name = match.group(1)
        return GeneralDiagnosis(
            pattern="not_subscriptable",
            marker=MARKERS["not_subscriptable"],
            summary=f"你对一个 `{type_name}` 用了方括号取值，但它不支持下标（None 不是容器）。",
            causes=["变量在运行时是 None", "函数在某个分支没有返回值", "字典取值得到 None 后又继续取下标"],
            steps=["打印变量确认是否为 None", "检查来源函数是否所有分支都有 return", "取值前判空"],
        )

    match = _NO_ATTR.search(text)
    if match:
        type_name, attr = match.group(1), match.group(2)
        return GeneralDiagnosis(
            pattern="no_attribute",
            marker=MARKERS["no_attribute"],
            summary=f"`{type_name}` 类型没有 `{attr}` 这个属性或方法；常见于对象是 None，或者拼写不一致。",
            causes=["对象是 None，却调用了它的属性", "属性名拼写错误", "对象类型和预期不一致"],
            steps=["打印对象和类型", "核对属性名拼写", "确认来源函数返回值"],
        )

    if _INDEX_RANGE.search(text):
        return GeneralDiagnosis(
            pattern="index_range",
            marker=MARKERS["index_range"],
            summary="下标超出了序列长度：你访问的位置在列表/元组里不存在。",
            causes=["列表为空或长度小于预期", "循环边界多算了一次", "下标从 0 开始，最后一项是 len-1"],
            steps=["打印 `len(序列)` 和实际下标", "检查循环的 range 边界", "访问前判断长度"],
        )

    match = _INT_LITERAL.search(text)
    if match:
        value = match.group(1)
        return GeneralDiagnosis(
            pattern="int_literal",
            marker=MARKERS["int_literal"],
            summary=f"你想把 `'{value}'` 转成整数，但它不是合法数字。",
            causes=["输入里混入了空格、单位或中文", "空字符串被直接转 int", "小数点字符串需要转 float 而不是 int"],
            steps=["打印原始字符串并检查首尾空格", "转换前先 `strip()`", "用 try/except 处理非法输入"],
        )

    match = _INDENT.search(text)
    if match:
        return GeneralDiagnosis(
            pattern="indent",
            marker=MARKERS["indent"],
            summary="缩进不一致：Python 用缩进表示代码块，同一层级的缩进必须完全一致。",
            causes=["混用了空格和 Tab", "代码块缩进层级不对", "复制粘贴带来的不可见字符"],
            steps=["把编辑器设置为显示空格", "统一用 4 个空格", "检查报错行上一行的缩进"],
        )

    match = _ARGS.search(text)
    if match:
        expected, given = match.group(1), match.group(2)
        return GeneralDiagnosis(
            pattern="args",
            marker=MARKERS["args"],
            summary=f"函数需要 {expected} 个位置参数，你传了 {given} 个。",
            causes=["调用时漏传或多传参数", "把 self 也算进了参数个数", "参数顺序与定义不一致"],
            steps=["对照函数定义逐个核对参数", "检查是否漏了默认参数", "打印函数签名确认"],
        )

    if _ZERO_DIV.search(text):
        return GeneralDiagnosis(
            pattern="zero_division",
            marker=MARKERS["zero_division"],
            summary="除数是 0：除法在运行到这一步时，除数变成了 0。",
            causes=[
                "除数来自用户输入或计算结果，边界情况下为 0",
                "循环里的计数器从 0 开始，被当成了除数",
                "前面某一步计算失败，导致除数是默认值 0",
            ],
            steps=[
                "在除法前打印除数，确认它在什么输入下变成 0",
                "除法前加判断：除数为 0 时给出明确提示或跳过",
                "检查分母的来源与循环边界",
            ],
        )

    match = _MODULE_MISSING.search(text)
    if match:
        module = match.group(1)
        return GeneralDiagnosis(
            pattern="module_missing",
            marker=MARKERS["module_missing"],
            summary=f"找不到模块 `{module}`：要么没安装，要么装在了另一个 Python 环境里。",
            causes=[f"依赖 `{module}` 没有安装", "装在了全局环境，但运行时用的是虚拟环境", "模块名拼写错误，或文件名与模块名冲突"],
            steps=[
                "确认当前解释器：`import sys; print(sys.executable)`",
                "用同一个解释器安装：`python -m pip install <包名>`",
                "核对包名与导入名是否一致（例如 pillow 对应 PIL）",
            ],
        )

    match = _NAME_ERROR.search(text)
    if match:
        name = match.group(1)
        return GeneralDiagnosis(
            pattern="name_error",
            marker=MARKERS["name_error"],
            summary=f"名字 `{name}` 在当前位置没有定义。",
            causes=["变量在使用前没有赋值", "变量定义在另一个函数或作用域里", "拼写与定义处不一致"],
            steps=["检查是否在使用前赋值", "确认作用域（函数内的变量外面看不到）", "核对拼写"],
        )

    match = _KEY_ERROR.search(text)
    if match and "keyerror" in text.lower():
        key = match.group(1).strip()
        return GeneralDiagnosis(
            pattern="key_error",
            marker=MARKERS["key_error"],
            summary=f"字典里没有键 `{key}`。",
            causes=["键名拼写与数据里的实际键名不一致", "数据里确实缺少这个键", "把列表下标当成了字典键"],
            steps=["打印字典的所有键：`print(data.keys())`", "用 `data.get(key, 默认值)` 代替直接取值", "核对数据来源与键名"],
        )

    return None
