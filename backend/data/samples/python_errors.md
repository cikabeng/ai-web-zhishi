# Python 常见报错排查笔记（示例课程资料）

> 本文件是项目自制的示例教学资料，用于演示知识库检索与引用，不涉及任何版权内容。

## 一、None 到底是什么

`None` 是 Python 里表示"什么都没有"的唯一值，类型是 `NoneType`。

它和 `0`、`""`、`[]`、`False` 都不一样：`0` 是数字，`""` 是空字符串，`[]` 是空列表，而 `None` 表示"没有值"。

判断一个值是不是 `None`，要用 `is None` 或 `is not None`，不要用 `== None`。虽然 `== None` 通常也能得到正确结果，但 `is` 比较的是身份，语义更准确，也不容易被自定义的 `__eq__` 干扰。

## 二、函数没有 return 时会发生什么

Python 的函数如果执行完所有语句都没有遇到 `return`，会隐式返回 `None`。

这意味着下面几种情况都会得到 `None`：

- 函数体里只有 `print`，没有 `return`；
- `return` 写在 `if` 分支里，另一条分支没有写；
- 提前 `return` 了但拼写错误，比如写成了 `retrun`；
- 异常被 `try/except` 吞掉，函数走到了末尾。

这是初学者最常见的 `None` 来源之一：以为函数返回了查询结果，实际上某个分支没有返回。

## 三、TypeError 与 NoneType 的关系

`TypeError: 'NoneType' object is not subscriptable` 的含义是：对一个 `None` 使用了方括号取值，例如 `value[0]`、`value["name"]`、`value[key]`。

方括号这种操作要求对象是"可下标访问"的容器，例如列表、元组、字典、字符串。`None` 不是容器，所以解释器直接抛出 `TypeError`。

同类错误还有：

- `AttributeError: 'NoneType' object has no attribute 'xxx'`：对 `None` 取属性，例如 `value.name`、`value.strip()`；
- `TypeError: 'NoneType' object is not iterable`：对 `None` 做 `for` 循环；
- `TypeError: 'NoneType' object is not callable`：把 `None` 当函数调用。

这三种错误的共同点是：**某个变量在运行时是 `None`，而不是你以为的对象**。

## 四、常见触发场景

场景一：函数在"查不到"的分支没有返回值。

场景二：字典取值用了 `dict.get(key)`，键不存在时返回 `None`，随后直接对结果取下标。

场景三：链式调用中间某一步返回了 `None`，例如先查询再取值。

场景四：变量被重新赋值为 `None`，例如在循环里被覆盖。

场景五：读取配置文件或接口返回的字段不存在，取值得到 `None`。

## 五、排查清单

1. 读报错的最后一行，确认异常类型与"操作对象"。
2. 找到 traceback 中第一处属于自己代码的行号。
3. 确认该行用方括号访问的变量，它的值从哪里来。
4. 在该行之前打印 `type(...)` 和 `repr(...)`，确认它到底是什么。
5. 顺着来源往回查：函数是否所有分支都有 `return`；字典取值是否可能缺失；上游是否可能返回空。
6. 确认是"数据缺失"还是"逻辑缺失"：前者要处理缺失，后者要补返回。

## 六、修复方向

不要急着改报错的那一行，先确定 `None` 的来源。

如果来源是"查不到"，就让函数在查不到时返回一个明确的空容器（例如空字典）或在调用处先判断。

如果来源是"分支遗漏"，就补齐缺失分支的返回值。

如果是"外部数据缺失"，要在取值前做存在性判断，并给出可读的提示信息。

## 七、和 AttributeError 的区别

`AttributeError` 是"对象存在但没有这个属性"，`TypeError` 是"对象的类型不支持这个操作"。

同样是 `None`，取属性会报 `AttributeError`，取下标会报 `TypeError`。判断时先看异常类型，再看操作符，就能快速缩小范围。
