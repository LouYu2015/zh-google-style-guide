"""
reviewer.py - Core review logic: call Claude to proofread one chunk.

Workflow per chunk:
  1. Build system prompt (translation guidelines + glossary) with prompt caching
  2. Build user message (previous notes + all section originals + translations)
  3. Stream Claude's response (extended thinking enabled)
  4. Parse structured output: <correction section="X.X">...</correction>, <notes>, <issues>
  5. Return ChunkResult with corrections dict, notes, issues, full response
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import reader as reader_mod


# ──────────────────────────────────────────────
# System prompt
# ──────────────────────────────────────────────

_NOTES_PATH = Path(__file__).parent.parent.parent / "translation" / "NOTES.md"


def _load_translation_notes() -> str:
    if _NOTES_PATH.exists():
        return _NOTES_PATH.read_text(encoding="utf-8")
    return ""


_SYSTEM_PROMPT_TEMPLATE = """\
你是一位资深中文技术文档翻译校对专家，专门校对 Google 编程风格指南的中文译文。

## 翻译原则

{notes}

## 工作流程

对于每个处理块中的每个章节，你需要：

1. 对比原文和译文，检查完整性、术语一致性、流畅度和代码示例
2. 发现并记录所有问题（即使没有修改也要记录）
3. 输出修正后的完整章节内容

## 输出格式

**你必须严格按照以下格式输出，不得更改标签名称或格式：**

首先输出问题列表（即使没有问题也要输出空的 issues 标签）：

<issues>
- [章节号] 严重程度（high/medium/low）: 问题描述
- [章节号] 严重程度: 问题描述
</issues>

然后对每个章节输出修正后的译文（如果无需修改，也要完整输出原译文）：

<correction section="X.X">
修正后的完整 Markdown 内容（包含标题行）
</correction>

<correction section="X.Y">
...
</correction>

最后输出记忆笔记，供处理下一批章节时参考：

<notes>
本批次的关键发现：术语使用情况、格式规范、待注意的问题等
</notes>

如果有需要人工决策的内容，在 notes 中注明，格式为：
[人工审核] 章节号: 描述

## 校对要点

**完整性**：对比原文的标题和子标题，确认译文没有遗漏任何章节；检查示例、列表、表格是否完整保留。

**术语一致性**：相同英文术语在整篇文档中应使用相同中文翻译；参考术语表中的既定翻译。

**流畅度**：避免逐字翻译导致的生硬表达；句子结构应符合中文习惯，不要出现翻译腔。

**代码示例**：代码块内容保持原样；只翻译 `//`、`/* */` 内的注释；必要的字符串常量可翻译。

**格式一致性**：检查列表格式（有序/无序）是否与原文一致；表格结构是否完整。
"""


def _build_system(state) -> list[dict]:
    notes = _load_translation_notes()
    system_text = _SYSTEM_PROMPT_TEMPLATE.format(notes=notes.strip())
    glossary_text = "## 当前术语对照表\n\n" + state.glossary_as_markdown()
    return [
        {"type": "text", "text": system_text, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": glossary_text, "cache_control": {"type": "ephemeral"}},
    ]


# ──────────────────────────────────────────────
# User message builder
# ──────────────────────────────────────────────

def _build_user_message(chunk, state, sections_data: dict) -> str:
    """Build the user message with previous notes + all section content."""
    lines: list[str] = []

    sections_str = ", ".join(chunk.sections)
    lines.append(f"# 校对任务：{chunk.chunk_id}（章节 {sections_str}）")
    if chunk.reason:
        lines.append(f"分组原因：{chunk.reason}")
    lines.append("")

    if chunk.notes:
        lines.append("## 上一批次的记忆笔记")
        lines.append("")
        lines.append(chunk.notes)
        lines.append("")
        lines.append("---")
        lines.append("")

    for section_num in chunk.sections:
        original = sections_data.get(section_num, {}).get("original")
        translation = sections_data.get(section_num, {}).get("translation")

        lines.append(f"## 章节 {section_num}")
        lines.append("")
        lines.append("### 原文（英文）")
        lines.append("")
        if original:
            lines.append("```")
            lines.append(original)
            lines.append("```")
        else:
            lines.append("*（原文未找到）*")
        lines.append("")
        lines.append("### 译文（中文）")
        lines.append("")
        if translation:
            lines.append(translation)
        else:
            lines.append("*（译文暂缺，跳过此章节）*")
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append(
        "请立即开始校对。对**每个有译文的章节**都必须输出 `<correction>` 标签，"
        "即使没有修改也要完整输出原译文。"
    )

    return "\n".join(lines)


# ──────────────────────────────────────────────
# Output parser
# ──────────────────────────────────────────────

@dataclass
class ChunkResult:
    corrections: dict = field(default_factory=dict)   # section_num -> corrected_content
    notes: str = ""
    issues_text: str = ""
    human_review: str = ""
    full_response: str = ""
    thinking_text: str = ""


def _parse_output(text: str) -> ChunkResult:
    result = ChunkResult(full_response=text)

    # Extract corrections
    for section_num, content in re.findall(
        r'<correction\s+section="([^"]+)">(.*?)</correction>',
        text,
        re.DOTALL,
    ):
        result.corrections[section_num] = content.strip()

    # Extract notes
    m = re.search(r"<notes>(.*?)</notes>", text, re.DOTALL)
    if m:
        result.notes = m.group(1).strip()

    # Extract issues
    m = re.search(r"<issues>(.*?)</issues>", text, re.DOTALL)
    if m:
        result.issues_text = m.group(1).strip()

    # Extract human review items from notes
    review_items = re.findall(r"\[人工审核\][^\n]+", result.notes)
    result.human_review = "\n".join(review_items)

    return result


# ──────────────────────────────────────────────
# Main review function
# ──────────────────────────────────────────────

def review_chunk(chunk, state, client, display, logger) -> ChunkResult:
    """Stream Claude's review for one chunk and return parsed ChunkResult."""
    from config import MODEL

    # Load section content
    sections_data: dict = {}
    for section_num in chunk.sections:
        sections_data[section_num] = {
            "original": reader_mod.read_original_section(state.guide, section_num),
            "translation": reader_mod.read_translated_section(state.guide, section_num),
        }

    system = _build_system(state)
    user_message = _build_user_message(chunk, state, sections_data)

    request_log = {
        "model": MODEL,
        "max_tokens": 16000,
        "thinking": {"type": "enabled", "budget_tokens": 8000},
        "system": [{"type": s["type"], "text": s["text"][:200] + "..."} for s in system],
        "messages": [{"role": "user", "content": user_message[:500] + "..."}],
    }
    logger.write_chunk_request(chunk.chunk_id, request_log)

    full_response = ""
    thinking_text = ""
    in_thinking = False

    try:
        with client.messages.stream(
            model=MODEL,
            max_tokens=16000,
            thinking={"type": "enabled", "budget_tokens": 8000},
            system=system,
            messages=[{"role": "user", "content": user_message}],
        ) as stream:
            for event in stream:
                etype = getattr(event, "type", None)

                if etype == "content_block_start":
                    block = getattr(event, "content_block", None)
                    if block and getattr(block, "type", None) == "thinking":
                        in_thinking = True
                        display.show_thinking_start()
                    elif block and getattr(block, "type", None) == "text":
                        if in_thinking:
                            in_thinking = False
                            display.show_thinking_end()

                elif etype == "content_block_delta":
                    delta = getattr(event, "delta", None)
                    if delta is None:
                        continue
                    dtype = getattr(delta, "type", None)
                    if dtype == "thinking_delta":
                        thinking_text += getattr(delta, "thinking", "")
                    elif dtype == "text_delta":
                        chunk_text = getattr(delta, "text", "")
                        full_response += chunk_text
                        display.stream_text(chunk_text)

                elif etype == "content_block_stop":
                    if in_thinking:
                        in_thinking = False
                        display.show_thinking_end()

    except Exception as exc:
        display.show_error(f"API 调用失败：{exc}")
        raise

    logger.write_chunk_response(chunk.chunk_id, full_response, thinking_text)

    result = _parse_output(full_response)
    result.thinking_text = thinking_text

    logger.write_chunk_result(
        chunk.chunk_id,
        result.corrections,
        result.issues_text,
        result.notes,
        result.human_review,
    )

    return result
