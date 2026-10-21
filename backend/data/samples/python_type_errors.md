# Python 类型错误专题（示例课程资料）

> 本文件是项目自制的示例教学资料，用于演示知识库检索与引用。

## 一、TypeError 的本质

`TypeError` 表示"这个类型不支持这个操作"，和"值不合法"（`ValueError`）不是一回事。

Python 是动态类型语言，但**不做隐式类型转换**：整数和字符串相加不会自动把字符串变成数字。

判断时先看两件事：操作符是什么、两边实际是什么类型。

## 二、unsupported operand type(s) for +: 'int' and 'str'

这条报错的含义是：你用 `+` 把 `int` 和 `str` 加在一起，而 Python 没有为这两种类型定义 `+`。

典型场景是函数参数没有统一类型：

```python
def add(a, b):
    return a + b

print(add(1, "2"))   # TypeError
```

字符串 `"2"` 看起来像数字，但它的类型仍然是 `str`。

处理方式有两种，取决于业务语义：

- 要算术运算：把字符串显式转成数字，`int(b)` 或 `float(b)`；
- 要文本拼接：把数字显式转成字符串，`str(a)`，或者用 f-string。

## 三、input() 的返回值

`input()` 永远返回字符串。即使输入的是 `2`，拿到的也是 `"2"`。

所以 `input() + 1` 一定会报 `TypeError`，需要先 `int(input())`。

转换时要考虑非法输入：`int("abc")` 会抛 `ValueError`，应配合 `try/except` 或先做校验。

## 四、can only concatenate str (not "int") to str

这是字符串拼接时的另一种表述：左边是字符串，右边不是。

同样需要显式转换，或者改用 f-string：

```python
name = "张三"
age = 18
print(name + age)          # TypeError
print(name + str(age))     # 正确
print(f"{name}{age}")      # 更推荐
```

## 五、排查顺序

1. 在运算前打印两边的类型：`print(type(a), type(b))`。
2. 确认数据来源：字面量、函数返回值，还是 `input()` / 接口。
3. 按业务语义选择转换方向，不要为了消错而随意转换。
4. 转换处处理非法输入，避免把 `TypeError` 变成 `ValueError`。
5. 如果是函数参数，考虑在函数入口统一类型，而不是在每个调用处修补。

## 六、和 NoneType 报错的区分

`'NoneType' object is not subscriptable` 是"对 None 取下标"，属于"对象是空值"；
`unsupported operand type(s)` 是"两种类型不能运算"，属于"类型不匹配"。

两者都可能出现在同一个函数里：先返回值丢了变成 None，再拿去做运算。
排查时先确认值是什么，再确认类型是什么。
