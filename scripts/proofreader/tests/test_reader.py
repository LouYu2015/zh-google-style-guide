"""
tests/test_reader.py - Unit tests for reader.py

Tests cover:
- HTML section extraction (returns raw HTML)
- Markdown section extraction
- apply_correction in-place replacement
- list_all_sections (with mock files)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import reader as reader_mod


# ──────────────────────────────────────────────
# HTML extraction tests (raw HTML returned)
# ──────────────────────────────────────────────

_SAMPLE_HTML = """\
<html>
<body>
<h2>1 Introduction</h2>
<p>This is the introduction.</p>
<h3>1.1 Terminology</h3>
<p>Some terms are defined here.</p>
<ol><li>term A</li><li>term B</li></ol>
<h3>1.2 Guide notes</h3>
<p>Example code is <strong>non-normative</strong>.</p>
<pre>
int x = 1;
</pre>
<h2>2 Source file basics</h2>
<p>Files are UTF-8.</p>
</body>
</html>
"""


def test_extract_html_top_level():
    text, title = reader_mod._extract_from_html(_SAMPLE_HTML, "1")
    assert text is not None
    assert "Introduction" in title
    assert "introduction" in text.lower()
    # Should not include section 2
    assert "UTF-8" not in text


def test_extract_html_subsection():
    text, title = reader_mod._extract_from_html(_SAMPLE_HTML, "1.1")
    assert text is not None
    assert "Terminology" in title
    # Raw HTML: list markup preserved
    assert "<ol>" in text
    assert "<li>term A</li>" in text
    # Should not include 1.2 content
    assert "non-normative" not in text


def test_extract_html_with_code():
    text, title = reader_mod._extract_from_html(_SAMPLE_HTML, "1.2")
    assert text is not None
    # Raw HTML: pre block preserved
    assert "<pre>" in text
    assert "int x = 1" in text
    assert "non-normative" in text


def test_extract_html_not_found():
    text, title = reader_mod._extract_from_html(_SAMPLE_HTML, "99")
    assert text is None
    assert title is None


def test_extract_html_ol_preserved():
    """<ol> vs <ul> markup is preserved verbatim for Claude to interpret."""
    html = (
        "<h2>3 Rules</h2>"
        "<p>Ordered:</p>"
        "<ol><li>First rule</li><li>Second rule</li></ol>"
        "<p>Unordered:</p>"
        "<ul><li>note A</li><li>note B</li></ul>"
        "<h2>4 Next</h2><p>other</p>"
    )
    text, _ = reader_mod._extract_from_html(html, "3")
    assert "<ol>" in text
    assert "<ul>" in text
    assert "<li>First rule</li>" in text
    assert "<li>note A</li>" in text
    # Section 4 excluded
    assert "other" not in text


def test_extract_html_nested_lists_preserved():
    """Nested list structure is passed through unchanged."""
    html = (
        "<h2>5 Nesting</h2>"
        "<ol>"
        "  <li>outer one"
        "    <ul><li>inner A</li><li>inner B</li></ul>"
        "  </li>"
        "  <li>outer two</li>"
        "</ol>"
        "<h2>6 Next</h2>"
    )
    text, _ = reader_mod._extract_from_html(html, "5")
    assert "<ol>" in text
    assert "<ul>" in text
    assert "inner A" in text
    assert "outer two" in text
    assert "6 Next" not in text


def test_extract_html_section_boundary():
    """Extraction stops at the next same-level heading."""
    text, _ = reader_mod._extract_from_html(_SAMPLE_HTML, "1")
    # 1.1 and 1.2 content is included (they're subsections)
    assert "Terminology" in text
    assert "non-normative" in text
    # Section 2 is excluded
    assert "UTF-8" not in text


def test_extract_html_subsection_boundary():
    """Subsection extraction stops before the next subsection."""
    text, _ = reader_mod._extract_from_html(_SAMPLE_HTML, "1.1")
    assert "term A" in text
    assert "non-normative" not in text  # 1.2 content excluded


def test_real_java_section_html_raw():
    """Regression: section 1.1 from javaguide.html returns raw HTML with <ol>."""
    text = reader_mod.read_original_section("java", "1.1")
    assert text is not None, "Section 1.1 not found in javaguide.html"
    # The original uses <ol> — must be present in raw output
    assert "<ol>" in text, "Expected <ol> tag in raw HTML for section 1.1"
    assert "<li>" in text


# ──────────────────────────────────────────────
# Markdown extraction tests
# ──────────────────────────────────────────────

_SAMPLE_MD = """\
---
title: Test Guide
---

# Google Test Style Guide

## 1 Introduction

This is the introduction.

### 1.1 Terminology notes

Some terms:
- Class
- Member

### 1.2 Guide notes

Example code is **non-normative**.

```python
x = 1
```

## 2 Source file basics

Files are UTF-8.
"""


def test_extract_md_top_level():
    text, title = reader_mod._extract_from_md(_SAMPLE_MD, "1")
    assert text is not None
    assert "Introduction" in title
    assert "introduction" in text.lower()
    assert "UTF-8" not in text


def test_extract_md_subsection():
    text, title = reader_mod._extract_from_md(_SAMPLE_MD, "1.1")
    assert text is not None
    assert "Terminology" in title
    assert "Class" in text
    assert "non-normative" not in text


def test_extract_md_with_code():
    text, title = reader_mod._extract_from_md(_SAMPLE_MD, "1.2")
    assert text is not None
    assert "non-normative" in text
    assert "x = 1" in text


def test_extract_md_not_found():
    text, title = reader_mod._extract_from_md(_SAMPLE_MD, "99")
    assert text is None
    assert title is None


def test_extract_md_no_frontmatter():
    content = "## 3 Formatting\n\nUse spaces.\n\n### 3.1 Indentation\n\nTwo spaces.\n\n## 4 Naming\n\nNames matter.\n"
    text, title = reader_mod._extract_from_md(content, "3")
    assert text is not None
    assert "Formatting" in title
    assert "Use spaces" in text
    # Subsections are included when extracting a parent section
    assert "Two spaces" in text
    # Next top-level section is excluded
    assert "Names matter" not in text


# ──────────────────────────────────────────────
# apply_correction tests
# ──────────────────────────────────────────────

_TRANSLATION_MD = """\
---
title: Java 风格指南
---

# Google Java 风格指南

## 1 简介

这是原始简介内容。

### 1.1 术语说明

这是原始术语说明内容。

### 1.2 指南说明

这是原始指南说明内容。

## 2 源文件基础

这是源文件基础内容。
"""


def test_apply_correction_subsection(monkeypatch, tmp_path):
    guide_file = tmp_path / "java.md"
    guide_file.write_text(_TRANSLATION_MD, encoding="utf-8")

    monkeypatch.setattr(reader_mod, "REPO_ROOT", tmp_path.parent)
    monkeypatch.setitem(reader_mod.TRANSLATION_GUIDES, "_test_", str(guide_file.relative_to(tmp_path.parent)))

    corrected = "### 1.1 术语说明\n\n这是**修正后**的术语说明内容。\n"
    result = reader_mod.apply_correction("_test_", "1.1", corrected)

    content = guide_file.read_text(encoding="utf-8")
    assert result is True
    assert "修正后" in content
    assert "原始术语说明" not in content
    # Other sections preserved
    assert "原始简介内容" in content
    assert "原始指南说明" in content
    assert "源文件基础" in content


def test_apply_correction_top_level(monkeypatch, tmp_path):
    guide_file = tmp_path / "java.md"
    guide_file.write_text(_TRANSLATION_MD, encoding="utf-8")

    monkeypatch.setattr(reader_mod, "REPO_ROOT", tmp_path.parent)
    monkeypatch.setitem(reader_mod.TRANSLATION_GUIDES, "_test_", str(guide_file.relative_to(tmp_path.parent)))

    corrected = "## 1 简介\n\n**修正**的简介内容。\n"
    result = reader_mod.apply_correction("_test_", "1", corrected)

    content = guide_file.read_text(encoding="utf-8")
    assert result is True
    assert "修正" in content
    assert "原始简介内容" not in content
    # Section 2 still present
    assert "源文件基础" in content


def test_apply_correction_not_found(monkeypatch, tmp_path):
    guide_file = tmp_path / "java.md"
    guide_file.write_text(_TRANSLATION_MD, encoding="utf-8")

    monkeypatch.setattr(reader_mod, "REPO_ROOT", tmp_path.parent)
    monkeypatch.setitem(reader_mod.TRANSLATION_GUIDES, "_test_", str(guide_file.relative_to(tmp_path.parent)))

    result = reader_mod.apply_correction("_test_", "99.99", "corrected content")
    assert result is False
    assert guide_file.read_text(encoding="utf-8") == _TRANSLATION_MD


# ──────────────────────────────────────────────
# list sections tests
# ──────────────────────────────────────────────

def test_list_sections_html():
    sections = reader_mod._list_sections_html(_SAMPLE_HTML)
    nums = [s["section_num"] for s in sections]
    assert "1" in nums
    assert "1.1" in nums
    assert "1.2" in nums
    assert "2" in nums


def test_list_sections_md():
    sections = reader_mod._list_sections_md(_SAMPLE_MD)
    nums = [s["section_num"] for s in sections]
    assert "1" in nums
    assert "1.1" in nums
    assert "1.2" in nums
    assert "2" in nums
    for s in sections:
        assert s["token_estimate"] > 0


def test_list_sections_level():
    sections = reader_mod._list_sections_html(_SAMPLE_HTML)
    by_num = {s["section_num"]: s for s in sections}
    assert by_num["1"]["level"] == 2
    assert by_num["1.1"]["level"] == 3
    assert by_num["2"]["level"] == 2
