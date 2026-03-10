---
title: Java 风格指南
description: Google Java Style Guide 中文翻译
---

# Google Java 风格指南

## 1 简介

本文档是 Google 针对 Java™ 编程语言源代码的**完整**编码规范。当且仅当一个 Java 源文件遵循本文档中的所有规则时，我们才称其*符合 Google 风格*。

与其他编程风格指南一样，本文档涵盖的内容不仅限于格式美观问题，还包括各类惯例与编码规范。然而，本文档侧重于那些我们普遍遵守的**硬性规定**，而刻意回避那些无法通过人工或工具明确执行的*建议*。

### 1.1 术语说明

在本文档中，除非另有说明：

1. *类*（class）一词泛指普通类、记录类（record class）、枚举类（enum class）、接口（interface）或注解类型（`@interface`）。
2. 类的*成员*（member）一词泛指嵌套类、字段、方法*或构造器*，即类的所有顶层内容（初始化器除外）。
3. *注释*（comment）一词始终指*实现注释*。本文档不使用"文档注释"这一说法，而统一使用通用术语"Javadoc"。

本文档中偶尔还会出现其他"术语说明"。
### 1.2 指南说明

本文档中的示例代码均为**非规范性**内容。也就是说，这些示例虽符合 Google 风格，但并不代表呈现代码的*唯一*符合风格规范的方式。示例中可选的格式选择不应被当作强制规则。
## 2 源文件基础

### 2.1 文件名

对于含有类的源文件，文件名由顶层类名（[只能有一个](#s3.4.1-one-top-level-class)）加上 `.java` 扩展名组成，且大小写需与类名完全一致。
### 2.2 文件编码：UTF-8

源文件采用 **UTF-8** 编码。
### 2.3 特殊字符

#### 2.3.1 空白字符

除换行符外，源文件中出现的唯一空白字符是 **ASCII 水平空格**（**0x20**）。这意味着：

1. 在 `char`、字符串字面量以及文本块中，其他所有空白字符均需转义。
2. **禁止**使用制表符（Tab）进行缩进。
#### 2.3.2 特殊转义序列

对于具有[特殊转义序列](http://docs.oracle.com/javase/tutorial/java/data/characters.html)的字符（`\b`、`\t`、`\n`、`\f`、`\r`、`\s`、`\"`、`\'` 和 `\\`），应直接使用对应的转义序列，而不是使用八进制（如 `\012`）或 Unicode 转义（如 `\u000a`）。
#### 2.3.3 非 ASCII 字符

对于其余的非 ASCII 字符，可以使用实际的 Unicode 字符（如 `∞`），也可以使用等价的 Unicode 转义（如 `\u221e`）。选择仅取决于哪种写法**更易于阅读和理解**，但强烈不建议在字符串字面量和注释之外使用 Unicode 转义。

> **提示：** 无论是使用 Unicode 转义，还是偶尔直接使用实际的 Unicode 字符，添加一条解释性注释往往都会有所帮助。

示例：

| 示例 | 说明 |
|------|------|
| `String unitAbbrev = "μs";` | 最佳：无需注释就一目了然。 |
| `String unitAbbrev = "\u03bcs"; // "μs"` | 允许，但没有必要这么做。 |
| `String unitAbbrev = "\u03bcs"; // 希腊字母 mu，"s"` | 允许，但写法别扭，容易出错。 |
| `String unitAbbrev = "\u03bcs";` | 差：读者完全不知道这是什么。 |
| `return '\ufeff' + content; // 字节顺序标记` | 好：对不可打印字符使用转义，必要时加注释。 |

> **提示：** 不要因为担心某些程序无法正确处理非 ASCII 字符，就降低代码的可读性。如果确实出现了问题，那是那些程序的**错误**，应该去**修复**它们。
## 3 源文件结构 {#s3-source-file-structure}

一个普通的源文件**按顺序**包含以下各节：

1. 许可证或版权信息（如有）
2. `package` 声明
3. `import` 语句
4. 有且仅有一个顶层类声明

各个存在的节之间**有且仅有一个空行**分隔。

`package-info.java` 文件结构相同，但没有类声明。

`module-info.java` 文件不含 `package` 声明，且用模块声明替代类声明，其他结构相同。

### 3.1 许可证或版权信息（如有）

如果文件中包含许可证或版权信息，应放在此处。
### 3.2 `package` 声明 {#s3.2-package-declaration}

`package` 声明**不换行**。列宽限制（第 4.4 节，[列宽限制：100](#s4.4-column-limit)）不适用于 `package` 声明。
### 3.3 `import` 语句 {#s3.3-import-statements}

#### 3.3.1 禁止使用通配符导入

**通配符导入**（即"按需导入"，无论是静态的还是非静态的），**一律禁止使用**。
#### 3.3.2 禁止换行

`import` 语句**不换行**。列宽限制（第 4.4 节，[列宽限制：100](#s4.4-column-limit)）不适用于 `import` 语句。
#### 3.3.3 排序与间距

`import` 语句按以下顺序排列：

1. 所有静态导入放在一组。
2. 所有非静态导入放在一组。

如果同时存在静态导入和非静态导入，则两组之间用一个空行分隔。其他 `import` 语句之间没有空行。

每组内，导入的名称按 ASCII 码顺序排列。（**注意：** 这不是按照 `import` *行* 本身的 ASCII 码排序，因为 `.` 的 ASCII 码小于 `;`。）
#### 3.3.4 禁止对类使用静态导入

禁止对静态嵌套类使用静态导入，应使用普通导入语句导入。
### 3.4 类声明

#### 3.4.1 有且仅有一个顶层类声明 {#s3.4.1-one-top-level-class}

每个顶层类独占一个源文件。
#### 3.4.2 类内容的排序

类的成员和初始化器的排列顺序对代码的可读性影响重大。然而，排列方式没有正确答案，不同的类可以采用不同的顺序。

重要的是，每个类都应遵循**某种合乎逻辑的顺序**，让维护者在需要时能够解释清楚。例如，不应仅仅出于习惯就把新方法追加到类的末尾 —— 那样只会产生"按添加时间排序"的结果，毫无逻辑性可言。

##### 3.4.2.1 重载：不拆散

同名方法必须紧挨着排列，中间不插入其他成员。多个构造器也适用同样的规则。即使方法或构造器的修饰符（如 `static` 或 `private`）有所不同，此规则依然适用。
### 3.5 模块声明

#### 3.5.1 模块指令的排序与间距

模块指令按以下顺序排列：

1. 所有 `requires` 指令放在一块。
2. 所有 `exports` 指令放在一块。
3. 所有 `opens` 指令放在一块。
4. 所有 `uses` 指令放在一块。
5. 所有 `provides` 指令放在一块。

相邻指令块之间以一个空行分隔。
## 4 格式化

> **术语说明：** *块状结构*（block-like construct）是指类、方法、构造器或 `switch` 的主体。根据第 4.8.3.1 节关于[数组初始化器](#s4.8.3.1-array-initializers)的规定，任何数组初始化器都*可以*视为块状结构。

### 4.1 花括号 {#braces}

#### 4.1.1 可选花括号的使用 {#s4.1.1-braces-always-used}

`if`、`else`、`for`、`do` 和 `while` 语句必须使用花括号，即便语句体为空或只有一条语句也不例外。

其他场合中原本可选的花括号（例如 lambda 表达式中的花括号）不受此规则影响，仍然是可选的。
#### 4.1.2 非空块：K&R 风格 {#s4.1.2-blocks-k-r-style}

对于*非空*块和块状结构，花括号遵循 Kernighan & Ritchie 风格：

- 开花括号前不换行（以下另有说明的情况除外）。
- 开花括号后换行。
- 闭花括号前换行。
- 闭花括号后换行，但*仅限于*该花括号终结一条语句、或终结方法体、构造器体或*具名*类体的情况。例如，如果闭花括号后跟 `else` 或逗号，则*不*换行。

例外：在允许出现以分号（`;`）结尾的单条语句的地方，也可以出现一个语句块，此时语句块的开花括号前需要换行。这类块通常用于限制局部变量的作用域。

示例：

```java
return () -> {
  while (condition()) {
    method();
  }
};

return new MyClass() {
  @Override public void method() {
    if (condition()) {
      try {
        something();
      } catch (ProblemException e) {
        recover();
      }
    } else if (otherCondition()) {
      somethingElse();
    } else {
      lastThing();
    }
    {
      int x = foo();
      frob(x);
    }
  }
};
```

枚举类的一些例外情况见第 4.8.1 节，[枚举类](#s4.8.1-enum-classes)。
#### 4.1.3 空块：可以简写 {#s4.1.3-braces-empty-blocks}

空块或块状结构可以采用 K&R 风格（如第 4.1.2 节所述）。此外，也可以在开花括号后立即关闭，中间不插入任何字符或换行（`{}`），**但前提是**该空块不属于*多重块语句*的一部分（即直接包含多个块的语句：`if/else` 或 `try/catch/finally`）。

示例：

```java
// 可以
void doNothing() {}

// 同样可以
void doNothingElse() {
}
```

```java
// 不可以：多重块语句中不能使用简写的空块
try {
  doSomething();
} catch (Exception e) {}
```
### 4.2 块缩进：+2 个空格 {#s4.2-block-indentation}

每打开一个新的块或块状结构，缩进增加两个空格。块结束时，缩进恢复到上一层级。缩进级别同时适用于块内的代码和注释。（参见第 4.1.2 节，[非空块：K&R 风格](#s4.1.2-blocks-k-r-style)中的示例。）
### 4.3 每行只写一条语句 {#s4.3-one-statement-per-line}

每条语句后都要换行。
### 4.4 列宽限制：100 {#s4.4-column-limit}

Java 代码的列宽限制为 100 个字符。"字符"是指任意一个 Unicode 码位。除以下情况外，所有超出此限制的行都必须折行，具体规则见第 4.5 节，[折行](#s4.5-line-wrapping)。

> **提示：** 每个 Unicode 码位算作一个字符，无论其显示宽度如何。例如，使用[全角字符](https://en.wikipedia.org/wiki/Halfwidth_and_fullwidth_forms)时，可以选择在本规则要求的位置之前提前折行。

**例外情况：**

1. 无法遵守列宽限制的行（例如 Javadoc 中的长 URL，或较长的 JSNI 方法引用）。
2. `package` 声明和 `import` 语句（见第 3.2 节，[package 声明](#s3.2-package-statement)，以及第 3.3 节，[import 语句](#s3.3-import-statements)）。
3. [文本块](#s4.8.9-text-blocks)中的内容。
4. 注释中可能被复制粘贴到 shell 中执行的命令行。
5. 极少数情况下需要使用非常长的标识符时，允许超出列宽限制。此时，周围代码的合理折行方式以 [google-java-format](https://github.com/google/google-java-format) 的输出为准。
### 4.5 折行 {#s4.5-line-wrapping}

> **术语说明：** 将原本可以写在一行的代码分成多行，称为*折行*（line-wrapping）。

没有一套全面、确定的公式能精确说明所有情况下该如何折行。同一段代码往往有多种有效的折行方式。

> **注意：** 折行的典型原因是避免超出列宽限制，但即使代码实际上不会超出列宽，作者也*可以*根据自己的判断选择折行。

> **提示：** 提取方法或局部变量，有时无需折行就能解决问题。

#### 4.5.1 在哪里断行 {#s4.5.1-line-wrapping-where-to-break}

折行的首要原则是：优先在**较高的语法层级**处断行。此外：

1. 当在*非赋值*运算符处断行时，断点位于符号*之前*。（注意：这与 Google 风格在 C++ 和 JavaScript 等其他语言中的做法不同。）以下"类运算符"符号同样适用此规则：
    - 点分隔符（`.`）
    - 方法引用的双冒号（`::`）
    - 类型界限中的 `&`（`<T extends Foo & Bar>`）
    - `catch` 块中的管道符（`catch (FooException | BarException e)`）

2. 当在*赋值*运算符处断行时，断点通常位于符号*之后*，但两种方式均可接受。以下符号同样适用此规则：
    - 增强型 `for`（"foreach"）语句中的冒号（`:`）

3. 方法名、构造器名或记录类名与其后紧跟的开圆括号（`(`）不分离。

4. 逗号（`,`）与其前面的符号不分离。

5. 在 lambda 或 `switch` 规则的箭头旁不断行，但如果箭头后只有单个无括号表达式，则可以紧接在箭头后断行。示例：

```java
MyLambda<String, Long, Object> lambda =
    (String label, Long value, Object obj) -> {
      ...
    };

Predicate<String> predicate = str ->
    longExpressionInvolving(str);

switch (x) {
  case ColorPoint(Color color, Point(int x, int y)) ->
      handleColorPoint(color, x, y);
  ...
}
```

> **注意：** 折行的首要目标是使代码清晰易读，而*不一定*是尽可能压缩行数。
#### 4.5.2 续行缩进：至少 +4 个空格 {#s4.5.2-line-wrapping-indent}

折行后，第一行之后的每一行（即*续行*）相对于原始行至少缩进 +4 个空格。

当有多条续行时，缩进量可以根据需要在 +4 的基础上进一步增加。一般来说，当且仅当两条续行以语法上并列的元素开头时，它们使用相同的缩进级别。

关于使用可变数量空格来对齐特定符号这一不推荐做法，详见第 4.6.3 节，[水平对齐](#s4.6.3-horizontal-alignment)。
### 4.6 空白

#### 4.6.1 垂直空白（空行）{#s4.6.1-vertical-whitespace}

以下情况*必须*出现一个空行：

1. 类中相邻成员或初始化器之间：字段、构造器、方法、嵌套类、静态初始化器和实例初始化器之间。
    - **例外：** 两个相邻字段之间（中间没有其他代码）的空行是可选的，可根据需要添加以形成字段的*逻辑分组*。
    - **例外：** 枚举常量之间的空行规则见[第 4.8.1 节](#s4.8.1-enum-classes)。

2. 本文档其他章节要求之处（如第 3 节，[源文件结构](#s3-source-file-structure)，以及第 3.3 节，[import 语句](#s3.3-import-statements)）。

此外，在任何有助于提高可读性的地方，也可以加入一个空行，例如在语句之间加入空行以将代码划分为若干逻辑小节。不鼓励也不反对在类的第一个成员或初始化器之前、或最后一个成员或初始化器之后添加空行。

*多个*连续空行是允许的，但从不要求（也不鼓励）。
#### 4.6.2 水平空白 {#s4.6.2-horizontal-whitespace}

在字面量、注释和 Javadoc 的内部之外，除语言或其他风格规则明确要求的情形外，ASCII 空格**仅**出现在以下位置：

1. 关键字（如 `if`、`for`、`catch`）与其后跟的开圆括号（`(`）之间。
2. 关键字（如 `else`、`catch`）与其前面的闭花括号（`}`）之间。
3. 所有开花括号（`{`）之前，但有两种例外：
    - `@SomeAnnotation({a, b})`（不加空格）
    - `String[][] x = {{"foo"}};`（根据下方第 9 条规则，`{{` 之间不需要空格）
4. 所有二元或三元运算符的两侧。以下"类运算符"符号同样适用此规则：
    - 分隔多个类型界限的 `&`：`<T extends Foo & Bar>`
    - 处理多个异常的 `catch` 块中的管道符：`catch (FooException | BarException e)`
    - 增强型 `for`（"foreach"）语句中的冒号（`:`）
    - lambda 表达式中的箭头：`(String str) -> str.length()`，或 `switch` 规则中的箭头：`case "FOO" -> bar();`

    但**不包括**：
    - 方法引用的双冒号（`::`），写法如 `Object::toString`
    - 点分隔符（`.`），写法如 `object.toString()`
5. `,:;` 之后，或强制类型转换的闭圆括号（`)`）之后。
6. 任意内容与以 `//` 开头的注释之间；允许多个空格。
7. 以 `//` 开头的注释与注释文本之间；允许多个空格。
8. 声明中类型与标识符之间：`List<String> list`。
9. 数组初始化器两侧花括号内，*可选地*加空格：`new int[] {5, 6}` 和 `new int[] { 5, 6 }` 均有效。
10. 类型注解与 `[]` 或 `...` 之间。

本规则不要求也不禁止行首或行尾的额外空格，只规定行*内部*的空格。
#### 4.6.3 水平对齐：不作要求 {#s4.6.3-horizontal-alignment}

> **术语说明：** *水平对齐*是指在代码中添加可变数量的额外空格，使某些符号恰好对齐到上一行中特定符号的正下方。

这种做法是允许的，但 Google 风格**从不要求**。甚至在已经使用了水平对齐的地方，也不要求*保持*对齐。

以下是未对齐与已对齐的示例：

```java
private int x; // 可以
private Color color; // 同样可以

private int   x;      // 允许，但以后修改时
private Color color;  // 可能会破坏对齐
```

> **提示：** 对齐有助于提高可读性，但为了维持对齐而刻意为之，会给将来埋下隐患。假设某次修改只涉及一行，如果该修改破坏了原有的对齐，就**不应**仅仅为了重新对齐而去改动附近无关的行。对无需修改的行引入格式化变更，会污染版本历史、拖慢代码审查速度，并加剧合并冲突。这些实际问题的优先级高于对齐本身。
### 4.7 分组括号：推荐使用 {#s4.7-grouping-parentheses}

只有当作者和审查者都认为省略括号不会引起误解、也不会影响可读性时，才可以省略可选的分组括号。*不*能假设每位读者都将整个 Java 运算符优先级表烂熟于心。
### 4.8 特定结构 {#s4.8-specific-constructs}

#### 4.8.1 枚举类 {#s4.8.1-enum-classes}

枚举常量后的逗号之后，可以选择换行，也允许添加额外的空行（通常只有一行）。以下是一种写法：

```java
private enum Answer {
  YES {
    @Override public String toString() {
      return "yes";
    }
  },

  NO,
  MAYBE
}
```

没有方法、且常量上没有文档注释的枚举类，可以选择格式化为类似数组初始化器的形式（见第 4.8.3.1 节，[数组初始化器](#s4.8.3.1-array-initializers)）：

```java
private enum Suit { CLUBS, HEARTS, SPADES, DIAMONDS }
```

由于枚举类*就是*类，所有关于类格式化的规则均适用。
#### 4.8.2 变量声明 {#s4.8.2-variable-declarations}

##### 4.8.2.1 每次只声明一个变量 {#s4.8.2.1-variables-per-declaration}

每条变量声明（字段或局部变量）只声明一个变量：不使用 `int a, b;` 这样的声明方式。

**例外：** `for` 循环头部允许使用多个变量声明。
##### 4.8.2.2 按需声明，就近声明 {#s4.8.2.2-variables-limited-scope}

局部变量**不应**在包含它们的块或块状结构的开头就统一声明。应将局部变量的声明尽量靠近其首次使用的位置（在合理范围内），以缩小其作用域。局部变量声明时通常带有初始化器，或在声明后立即初始化。
#### 4.8.3 数组 {#s4.8.3-arrays}

##### 4.8.3.1 数组初始化器：可以写成块状形式 {#s4.8.3.1-array-initializers}

任何数组初始化器都*可以*选择写成"块状结构"的形式。例如，以下写法均有效（**并非**详尽列举）：

```java
new int[] {           new int[] {
  0, 1, 2, 3            0,
}                       1,
                        2,
new int[] {             3,
  0, 1,               }
  2, 3
}                     new int[]
                          {0, 1, 2, 3}
```
##### 4.8.3.2 不使用 C 风格的数组声明 {#s4.8.3.2-array-declarations}

方括号是*类型*的一部分，而不是变量的一部分：应写 `String[] args`，而不是 `String args[]`。
#### 4.8.4 `switch` 语句与表达式 {#s4.8.4-switch}

由于历史原因，Java 语言对 `switch` 有两种截然不同的语法，我们分别称之为*旧式风格*和*新式风格*。新式 switch 在 switch 标签后使用箭头（`->`），而旧式 switch 使用冒号（`:`）。

> **术语说明：** 在 *switch 块*的花括号内，要么是一条或多条 *switch 规则*（新式），要么是一条或多条*语句组*（旧式）。*switch 规则*由一个 *switch 标签*（`case ...` 或 `default`）加上 `->` 以及一个表达式、块或 `throw` 语句组成。语句组由一条或多条 switch 标签（各自后跟冒号），再加上一条或多条语句组成；对于*最后一个*语句组，则可以是零条或多条语句。（以上定义与 Java 语言规范 [§14.11](https://docs.oracle.com/javase/specs/jls/se21/html/jls-14.html#jls-14.11) 一致。）

##### 4.8.4.1 缩进 {#s4.8.4.1-switch-indentation}

与其他块相同，switch 块的内容缩进 +2。每个 switch 标签的缩进也是 +2。

在新式 switch 中，如果一条 switch 规则符合 Google 风格的其他要求（不超出列宽限制，且如果包含非空块则需在 `{` 后换行），则可以写在同一行。第 4.5 节的折行规则同样适用，包括续行的 +4 缩进。对于箭头后跟非空块的 switch 规则，规则与其他地方的块相同：`{` 与 `}` 之间的行相对于含有 switch 标签的那行再缩进 +2。

```java
switch (number) {
  case 0, 1 -> handleZeroOrOne();
  case 2 ->
      handleTwoWithAnExtremelyLongMethodCallThatWouldNotFitOnTheSameLine();
  default -> {
    logger.atInfo().log("Surprising number %s", number);
    handleSurprisingNumber(number);
  }
}
```

在旧式 switch 中，每个 switch 标签的冒号后需要换行，语句组内的语句再缩进 +2。

<a id="fallthrough"></a>
##### 4.8.4.2 贯穿（fall-through）：需加注释 {#s4.8.4.2-switch-fall-through}

在旧式 switch 块中，每个语句组要么异常终止（以 `break`、`continue`、`return` 或抛出异常结束），要么加上注释表明执行会（或*可能会*）继续到下一个语句组。任何能传达贯穿意图的注释均可（通常写 `// fall through`）。switch 块的最后一个语句组不需要加此注释。示例：

```java
switch (input) {
  case 1:
  case 2:
    prepareOneOrTwo();
  // fall through
  case 3:
    handleOneTwoOrThree();
    break;
  default:
    handleLargeNumber(input);
}
```

注意，`case 1:` 之后不需要注释，只需在语句组末尾加注释即可。

新式 switch 中不存在贯穿问题。
##### 4.8.4.3 穷举性与 `default` 标签 {#s4.8.4.3-switch-default}

Java 语言要求 switch 表达式以及多种 switch 语句必须是*穷举的*，即所有可能的值都能被某个 switch 标签匹配。具有 `default` 标签的 switch 是穷举的；对于枚举类型，若每个枚举值都有对应的 switch 标签，也满足穷举要求。Google 风格要求*每个* switch 都是穷举的，即便语言本身不作要求。这可能需要添加 `default` 标签，即使其中没有任何代码。
##### 4.8.4.4 switch 表达式 {#s4.8.4.4-switch-expressions}

switch 表达式必须使用新式风格：

```java
  return switch (list.size()) {
    case 0 -> "";
    case 1 -> list.getFirst();
    default -> String.join(", ", list);
  };
```

<a id="annotations"></a>
#### 4.8.5 注解 {#s4.8.5-annotations}

##### 4.8.5.1 类型使用注解 {#s4.8.5.1-type-use-annotation-style}

类型使用注解（type-use annotation）紧接在被注解的类型之前。若一个注解被 `@Target(ElementType.TYPE_USE)` 元注解标注，则它就是类型使用注解。示例：

```java
final @Nullable String name;

public @Nullable Person getPersonByName(String name);
```
##### 4.8.5.2 类、包和模块注解 {#s4.8.5.2-class-annotation-style}

应用于类、包或模块声明的注解紧跟在文档块之后，每个注解各占一行（即每行一个注解）。这些换行不构成折行（第 4.5 节，[折行](#s4.5-line-wrapping)），因此缩进级别不增加。示例：

```java
/** 这是一个类。 */
@Deprecated
@CheckReturnValue
public final class Frozzler { ... }
```

```java
/** 这是一个包。 */
@Deprecated
@CheckReturnValue
package com.example.frozzler;
```

```java
/** 这是一个模块。 */
@Deprecated
@SuppressWarnings("CheckReturnValue")
module com.example.frozzler { ... }
```
##### 4.8.5.3 方法和构造器注解 {#s4.8.5.3-method-annotation-style}

方法和构造器声明上的注解规则与[上一节](#s4.8.5.2-class-annotation-style)相同。示例：

```java
@Deprecated
@Override
public String getNameIfPresent() { ... }
```

**例外：** *单个*无参数的注解*可以*与签名的第一行写在同一行，例如：

```java
@Override public int hashCode() { ... }
```
##### 4.8.5.4 字段注解 {#s4.8.5.4-field-annotation-style}

应用于字段的注解同样紧跟在文档块之后，但此时*多个*注解（可能带有参数）可以写在同一行，例如：

```java
@Partial @Mock DataLoader loader;
```
##### 4.8.5.5 参数和局部变量注解 {#s4.8.5.5-local-parameter-annotation-style}

对于参数或局部变量上的注解，没有特殊的格式规则（当然，类型使用注解除外）。

<a id="comments"></a>
#### 4.8.6 注释 {#s4.8.6-comments}

本节讨论*实现注释*。Javadoc 见第 7 节，[Javadoc](#s7-javadoc)。

在任意换行符之前，都可以添加任意空白字符，再跟一条实现注释，从而使该行成为非空行。

##### 4.8.6.1 块注释风格 {#s4.8.6.1-block-comment-style}

块注释与其所在的代码保持相同的缩进级别。可以使用 `/* ... */` 风格，也可以使用 `// ...` 风格。对于多行的 `/* ... */` 注释，后续行必须以 `*` 开头，且与上一行的 `*` 对齐。

```java
/*
 * 这样          // 这样也      /* 或者这样
 * 可以。        // 可以。       * 也行。 */
 */
```

注释不要用星号或其他字符画出边框。

> **提示：** 在编写多行注释时，如果希望自动代码格式化工具能够在必要时重新折行（段落风格），请使用 `/* ... */` 风格。大多数格式化工具不会重新折行 `// ...` 风格的注释块。

<a id="todo"></a>
<a id="todo"></a>

##### 4.8.6.2 TODO 注释 {#s4.8.6.2-todo-comments}

对于临时代码、短期解决方案，或功能够用但还不完美的代码，使用 `TODO` 注释。

`TODO` 注释以全大写的 `TODO` 开头，后跟冒号，再跟一个包含背景信息的资源链接，最好是 bug 引用链接（因为 bug 会被跟踪，也有后续讨论）。在该背景信息之后，用连字符 `-` 引出解释性说明。

这样做的目的是统一 `TODO` 格式，方便通过搜索查找更多详情。

```java
// TODO: crbug.com/12345678 - 在 2047q4 兼容性窗口结束后移除此代码。
```

避免将个人或团队作为背景信息写入 TODO：

```java
// TODO: @yourusername - 提个 issue，用 '*' 表示重复。
```

如果 TODO 是"在未来某个时间做某事"这种形式，务必包含非常具体的日期（如"Fix by November 2005"）或非常具体的事件（如"Remove this code when all clients can handle XML responses."）。

<a id="modifiers"></a>
<a id="modifiers"></a>

#### 4.8.7 修饰符 {#s4.8.7-modifiers}

类和成员的修饰符（如有）按 Java 语言规范推荐的顺序排列：

```
public protected private abstract default static final sealed non-sealed
  transient volatile synchronized native strictfp
```

`requires` 模块指令的修饰符（如有）按以下顺序排列：

```
transitive static
```
#### 4.8.8 数值字面量 {#s4.8.8-numeric-literals}

`long` 类型整数字面量使用大写 `L` 后缀，而不是小写（以避免与数字 `1` 混淆）。例如，应写 `3000000000L` 而不是 `3000000000l`。
#### 4.8.9 文本块 {#s4.8.9-text-blocks}

文本块的开始 `"""` 必须另起一行。这一行可以遵循与其他结构相同的缩进规则，也可以完全不缩进（即从最左侧开始）。结束 `"""` 另起一行，缩进与开始 `"""` 相同，且其后可以在同一行继续编写代码。文本块中每一行的缩进至少与开始和结束的 `"""` 相同。（如果某行缩进更多，则文本块所定义的字符串字面量中，该行开头会有对应数量的空格。）

文本块的内容可以超过[列宽限制](#columnlimit)。

<a id="naming"></a>
## 5 命名 {#s5-naming}

### 5.1 所有标识符通用规则 {#s5.1-identifier-names}

标识符只使用 ASCII 字母和数字，以及在下文少数特别说明的情况下使用下划线。因此，每个合法的标识符名称都能被正则表达式 `\w+` 匹配。

Google 风格**不使用**特殊的前缀或后缀。例如，以下命名不符合 Google 风格：`name_`、`mName`、`s_name`、`kName`。
### 5.2 各类标识符的命名规则 {#s5.2-specific-identifier-names}

#### 5.2.1 包名和模块名 {#s5.2.1-package-names}

包名和模块名只使用小写字母和数字（不使用下划线），各单词直接拼接。例如，应写 `com.example.deepspace`，而不是 `com.example.deepSpace` 或 `com.example.deep_space`。
#### 5.2.2 类名 {#s5.2.2-class-names}

类名使用 [**大驼峰命名法**（UpperCamelCase）](#s5.3-camel-case)。

类名通常是名词或名词短语，例如 `Character` 或 `ImmutableList`。接口名也可以是名词或名词短语（例如 `List`），但有时也可以是形容词或形容词短语（例如 `Readable`）。

注解类型的命名没有特定规则，也没有公认的惯例。

*测试*类的名称以 `Test` 结尾，例如 `HashIntegrationTest`。如果它只覆盖单个类，则命名为该类名加上 `Test`，例如 `HashImplTest`。
#### 5.2.3 方法名 {#s5.2.3-method-names}

方法名使用[**小驼峰命名法**（lowerCamelCase）](#s5.3-camel-case)。

方法名通常是动词或动词短语，例如 `sendMessage` 或 `stop`。

JUnit *测试*方法名可以用下划线分隔逻辑组成部分，每个部分各自采用小驼峰命名法，例如 `transferMoney_deductsFromSource`。测试方法命名没有唯一正确的方式。

<a id="constants"></a>
<a id="constants"></a>
#### 5.2.4 常量名 {#s5.2.4-constant-names}

常量名使用 `UPPER_SNAKE_CASE`：全大写字母，单词之间用下划线分隔。那么，究竟什么是常量呢？

常量是静态 final 字段，其内容是深度不可变的，且其方法没有可观察到的副作用。基本类型值、字符串、不可变的值类，以及赋值为 `null` 的任何内容，都属于常量。如果实例的任何可观察状态可以改变，它就不是常量。仅仅*打算*永不修改对象还不够。示例：

```java
// 常量
static final int NUMBER = 5;
static final ImmutableList<String> NAMES = ImmutableList.of("Ed", "Ann");
static final Map<String, Integer> AGES = ImmutableMap.of("Ed", 35, "Ann", 32);
static final Joiner COMMA_JOINER = Joiner.on(','); // 因为 Joiner 是不可变的
static final SomeMutableType[] EMPTY_ARRAY = {};

// 非常量
static String nonFinal = "non-final";
final String nonStatic = "non-static";
static final Set<String> mutableCollection = new HashSet<String>();
static final ImmutableSet<SomeMutableType> mutableElements = ImmutableSet.of(mutable);
static final ImmutableMap<String, SomeMutableType> mutableValues =
    ImmutableMap.of("Ed", mutableInstance, "Ann", mutableInstance2);
static final Logger logger = Logger.getLogger(MyClass.getName());
static final String[] nonEmptyArray = {"these", "can", "change"};
```

常量名通常是名词或名词短语。
#### 5.2.5 非常量字段名 {#s5.2.5-non-constant-field-names}

非常量字段名（无论是否静态）使用[小驼峰命名法](#s5.3-camel-case)。

这些名称通常是名词或名词短语，例如 `computedValues` 或 `index`。
#### 5.2.6 参数名 {#s5.2.6-parameter-names}

参数名使用[小驼峰命名法](#s5.3-camel-case)。

应避免在公共方法中使用单字符参数名。
#### 5.2.7 局部变量名 {#s5.2.7-local-variable-names}

局部变量名使用[小驼峰命名法](#s5.3-camel-case)。

即便局部变量是 final 且不可变的，也不视为常量，不应按常量风格命名。
#### 5.2.8 类型变量名 {#s5.2.8-type-variable-names}

类型变量的命名方式有两种：

- 单个大写字母，后面可选跟一个数字（如 `E`、`T`、`X`、`T2`）。
- 类名形式（见第 5.2.2 节，[类名](#s5.2.2-class-names)），后面加大写字母 `T`（例如 `RequestT`、`FooBarT`）。

<a id="acronyms"></a>
<a id="camelcase"></a>
<a id="acronyms"></a>
<a id="camelcase"></a>

### 5.3 驼峰命名法的定义 {#s5.3-camel-case}

有时，将一个英文短语转换为驼峰命名法有不止一种合理的方式，例如当出现缩略词或"IPv6""iOS"这样特殊结构时。为了提高可预测性，Google 风格规定了以下（近乎确定的）转换方案。

从名称的自然语言形式开始：

1. 将短语转换为纯 ASCII，并去掉所有撇号。例如，"Müller's algorithm"可能变为"Muellers algorithm"。
2. 将结果按空格和剩余标点符号（通常是连字符）分割为单词。
    - *建议：* 如果某个单词在常见用法中已经有约定俗成的驼峰拼写，则将其拆分为各组成部分（例如，"AdWords"变为"ad words"）。注意，"iOS"这类词本身并不是驼峰拼写，它不遵循*任何*惯例，因此本建议不适用。
3. 将所有字母全部转为小写（包括缩略词），然后将以下字母改为大写：
    - 每个单词的首字母 → 得到*大驼峰命名法*，或
    - 除第一个单词外，每个单词的首字母 → 得到*小驼峰命名法*
4. 最后，将所有单词拼接成一个标识符。注意，原始单词的大小写几乎完全被忽略。

极少数情况下（例如多部分版本号），由于数字没有大小写之分，可能需要用下划线分隔相邻的数字。

示例：

| 自然语言形式 | 正确 | 错误 |
|---|---|---|
| "XML HTTP request" | `XmlHttpRequest` | `XMLHTTPRequest` |
| "new customer ID" | `newCustomerId` | `newCustomerID` |
| "inner stopwatch" | `innerStopwatch` | `innerStopWatch` |
| "supports IPv6 on iOS?" | `supportsIpv6OnIos` | `supportsIPv6OnIOS` |
| "YouTube importer" | `YouTubeImporter`、`YoutubeImporter`* | |
| "Turn on 2SV" | `turnOn2sv` | `turnOn2Sv` |
| "Guava 33.4.6" | `guava33_4_6` | `guava3346` |

\*可以接受，但不推荐。

> **注意：** 英语中有些词的连字符用法存在分歧：例如"nonempty"和"non-empty"都是正确的，因此方法名 `checkNonempty` 和 `checkNonEmpty` 同样都是正确的。
## 6 编程实践 {#s6-programming-practices}

### 6.1 `@Override`：始终使用 {#s6.1-override-annotation}

凡是合法的地方，都应在方法上标注 `@Override` 注解。这包括：子类方法重写父类方法、类方法实现接口方法、接口方法重新声明父接口中的方法，以及为记录类组件（record component）显式声明的访问器方法。

**例外：** 当父类方法标注了 `@Deprecated` 时，可以省略 `@Override`。
<a id="caughtexceptions"></a>
### 6.2 捕获的异常：不忽略 {#s6.2-caught-exceptions}

对捕获到的异常不作任何处理，几乎在任何情况下都是错误的做法。（常见的处理方式包括：记录日志，或者在确信该异常"不可能发生"时，将其作为 `AssertionError` 重新抛出。）

当 `catch` 块中确实不需要任何处理时，必须在注释中解释这样做的理由。

```java
try {
  int i = Integer.parseInt(response);
  return handleNumericResponse(i);
} catch (NumberFormatException ok) {
  // 不是数字格式；这是正常情况，继续执行即可
}
return handleTextResponse(response);
```
### 6.3 静态成员：通过类名限定 {#s6.3-static-members}

在引用静态类成员时，必须通过类名来限定，而不是通过该类的引用或表达式。

```java
Foo aFoo = ...;
Foo.aStaticMethod(); // 好
aFoo.aStaticMethod(); // 不好
somethingThatYieldsAFoo().aStaticMethod(); // 非常不好
```
<a id="finalizers"></a>
### 6.4 Finalizer：不使用 {#s6.4-finalizers}

不要重写 `Object.finalize`。Java 的终结机制（Finalization）已[计划移除](https://openjdk.org/jeps/421)。
<a id="javadoc"></a>

## 7 Javadoc {#s7-javadoc}

### 7.1 格式化 {#s7.1-javadoc-formatting}

#### 7.1.1 通用形式 {#s7.1.1-javadoc-multi-line}

Javadoc 块的基本格式如以下示例所示：

```java
/**
 * 此处编写 Javadoc 的多行文本，
 * 正常换行……
 */
public int method(String p1) { ... }
```

……或是以下单行形式：

```java
/** 简短的 Javadoc 内容。 */
```

基本形式始终可以使用。当整个 Javadoc 块（包括注释标记）能放在单行时，可以用单行形式替代。注意，只有在没有 `@param` 等块标签时，才适用单行形式。
#### 7.1.2 段落 {#s7.1.2-javadoc-paragraphs}

各段之间须有一个空行——即一行仅含对齐前导星号（`*`）；如有块标签组，其前也须有一个空行。除第一段外，每段的第一个单词前紧接 `<p>` 标签，`<p>` 后不加空格。其他块级 HTML 元素（如 `<ul>` 或 `<table>`）前*不*加 `<p>`。

<a id="s7.1.3-javadoc-at-clauses"></a>
<a id="s7.1.3-javadoc-at-clauses"></a>

#### 7.1.3 块标签 {#s7.1.3-javadoc-block-tags}

所用的标准"块标签"按以下顺序出现：`@param`、`@return`、`@throws`、`@deprecated`，且这四种标签的描述不能为空。当块标签在单行内放不下时，续行从 `@` 的位置向右缩进四个（或更多）空格。
### 7.2 摘要片段 {#s7.2-summary-fragment}

每个 Javadoc 块都以一段简短的**摘要片段**开头。这个片段非常重要：在类和方法索引等特定上下文中，它是唯一会显示的文本内容。

这是一个片段——名词短语或动词短语，而非完整句子。它**不**以 `A {@code Foo} is a…` 或 `This method returns…` 开头，也不构成 `Save the record.` 这样完整的祈使句。但这个片段的首字母应大写，并像完整句子一样使用标点符号。

> **提示：** 常见错误是将简单的 Javadoc 写成 `/** @return the customer ID */` 这种形式。这是不正确的，应改为 `/** Returns the customer ID. */` 或 `/** {@return the customer ID} */`。

<a id="s7.3.3-javadoc-optional"></a>
### 7.3 Javadoc 的使用范围 {#s7.3-javadoc-where-required}

至少，每个*可见的*类、成员或记录类组件都需要有 Javadoc，但有以下例外。顶层类若为 `public`，则是可见的；成员若为 `public` 或 `protected`，且其所在类可见，则该成员是可见的；记录类组件若其所在记录类可见，则该组件是可见的。

如第 7.3.4 节[非必需 Javadoc](#s7.3.4-javadoc-non-required) 所述，也可以根据需要编写额外的 Javadoc 内容。

#### 7.3.1 例外：含义不言自明的成员 {#s7.3.1-javadoc-exception-self-explanatory}

对于"简单、显而易见"的成员和记录类组件，例如 `getFoo()` 方法，*如果*确实没有什么值得说的，只是"返回 foo 的值"，则 Javadoc 是可选的。

> **重要：** 不能以此例外为由省略普通读者可能需要了解的相关信息。例如，对于名为 `canonicalName` 的记录类组件，如果普通读者可能不知道"canonical name"（规范名称）是什么意思，就不应省略其文档（即便文档内容可能只是 `@param canonicalName the canonical name`）。
#### 7.3.2 例外：重写方法 {#s7.3.2-javadoc-exception-overrides}

重写父类型方法的方法，并不总是需要 Javadoc。
#### 7.3.4 非必需 Javadoc {#s7.3.4-javadoc-non-required}

其他类、成员和记录类组件可以根据需要或意愿编写 Javadoc。

每当需要用实现注释来描述一个类或成员的整体目的或行为时，应将该注释改写为 Javadoc 形式（使用 `/**`）。

非必需的 Javadoc 不强制遵守第 7.1.1、7.1.2、7.1.3 和 7.2 节的格式规则，但当然推荐遵守。
