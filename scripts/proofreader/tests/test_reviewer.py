"""
tests/test_reviewer.py - Unit tests for reviewer.py output parsing.

No API calls are made; only the parsing logic is tested.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from reviewer import _parse_output, ChunkResult


# ──────────────────────────────────────────────
# _parse_output tests
# ──────────────────────────────────────────────

_FULL_RESPONSE = """\
<issues>
- [1.1] low: 列表格式与原文不一致，原文为无序列表
- [1.2] medium: 最后一句翻译不够流畅
</issues>

<correction section="1.1">
### 1.1 术语说明

在本文档中，除非另有说明：

- *类*（class）一词泛指普通类。
- *成员*（member）一词泛指嵌套类。
</correction>

<correction section="1.2">
### 1.2 指南说明

示例代码均为**非规范性**内容。
</correction>

<notes>
本批次关键发现：
- 1.1 节的列表格式已从有序改为无序，与原文一致
- 术语"non-normative"统一译为"非规范性"
- 下一批次注意：section 2 包含代码示例，保持注释翻译即可
</notes>
"""


def test_parse_corrections():
    result = _parse_output(_FULL_RESPONSE)
    assert "1.1" in result.corrections
    assert "1.2" in result.corrections
    assert "### 1.1 术语说明" in result.corrections["1.1"]
    assert "### 1.2 指南说明" in result.corrections["1.2"]


def test_parse_notes():
    result = _parse_output(_FULL_RESPONSE)
    assert "列表格式" in result.notes
    assert "下一批次" in result.notes


def test_parse_issues():
    result = _parse_output(_FULL_RESPONSE)
    assert "列表格式" in result.issues_text
    assert "流畅" in result.issues_text


def test_parse_full_response_preserved():
    result = _parse_output(_FULL_RESPONSE)
    assert result.full_response == _FULL_RESPONSE


def test_parse_empty_issues():
    response = """\
<issues>
</issues>

<correction section="2.1">
### 2.1 文件名

文件名全部小写。
</correction>

<notes>
无问题发现。
</notes>
"""
    result = _parse_output(response)
    assert "2.1" in result.corrections
    assert "文件名" in result.corrections["2.1"]
    assert result.notes == "无问题发现。"


def test_parse_no_corrections():
    response = "<issues>\n- [1] low: 小问题\n</issues>\n\n<notes>\n备注\n</notes>"
    result = _parse_output(response)
    assert result.corrections == {}
    assert result.notes == "备注"


def test_parse_correction_with_code():
    """Correction content can contain < and > without breaking the parser."""
    response = """\
<issues>
</issues>

<correction section="4.1">
### 4.1 泛型

使用 `List<String>` 时注意类型安全。

```java
List<String> list = new ArrayList<>();
```
</correction>

<notes>
发现泛型相关术语。
</notes>
"""
    result = _parse_output(response)
    assert "4.1" in result.corrections
    assert "List<String>" in result.corrections["4.1"]
    assert "ArrayList<>" in result.corrections["4.1"]


def test_parse_human_review_extracted():
    response = """\
<issues>
</issues>

<correction section="3.1">
### 3.1 版权信息

版权声明内容。
</correction>

<notes>
本批次发现：格式规范。
[人工审核] 3.1: 原文提到多种许可证形式，译文选择了其中一种，需确认是否合适
</notes>
"""
    result = _parse_output(response)
    assert "[人工审核]" in result.human_review
    assert "3.1" in result.human_review


def test_parse_multiple_corrections_order():
    """Corrections should be parsed in order they appear."""
    response = """\
<issues></issues>
<correction section="5.1">内容A</correction>
<correction section="5.2">内容B</correction>
<correction section="5.3">内容C</correction>
<notes>三节都好</notes>
"""
    result = _parse_output(response)
    assert list(result.corrections.keys()) == ["5.1", "5.2", "5.3"]
    assert result.corrections["5.1"] == "内容A"
    assert result.corrections["5.3"] == "内容C"
