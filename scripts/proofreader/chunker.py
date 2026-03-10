"""
chunker.py - Phase 1: Ask Claude to plan chunk groupings.

Sends the section list to Claude and asks it to group sections into
processing chunks of ~1000-4000 tokens each, keeping related subsections
together.
"""
from __future__ import annotations

import json
import re

from state import Chunk, SectionInfo


_SYSTEM_PROMPT = (
    "你是一个专业的文档分析专家，擅长制定翻译校对工作计划。\n"
    "你需要根据文档的章节结构，设计出最优的分批处理方案。\n\n"
    "目标：\n"
    "- 每个处理块的内容（原文+译文）在 1000–4000 tokens 之间最理想\n"
    "- 相关联的小节应合并为一个处理块，以便模型理解上下文\n"
    "- 过大的章节应拆分为若干子章节单独处理\n"
    "- 保持章节编号的逻辑连贯性\n"
)


def _build_user_message(guide: str, sections: list[SectionInfo]) -> str:
    lines = [
        f"# {guide} 风格指南章节结构分析",
        "",
        "请根据以下章节结构，制定校对处理计划。",
        "",
        "## 章节列表",
        "",
        "| 章节号 | 标题 | 层级 | 估算tokens | 有译文 |",
        "|--------|------|------|-----------|--------|",
    ]
    for s in sections:
        level_map = {2: "H2", 3: "H3", 4: "H4", 5: "H5", 6: "H6"}
        level_str = level_map.get(s.level, f"H{s.level}")
        has_trans = "是" if s.has_translation else "否"
        lines.append(
            f"| {s.section_num} | {s.title} | {level_str} | {s.token_estimate} | {has_trans} |"
        )

    lines += [
        "",
        "## 输出要求",
        "",
        '输出一个 JSON 数组，每个元素代表一个处理块：',
        "",
        "```json",
        "[",
        '  {"chunk_id": "chunk_01", "sections": ["1", "1.1", "1.2"], "reason": "这几个章节内容较少，合并处理效率更高"},',
        '  {"chunk_id": "chunk_02", "sections": ["2"], "reason": "此章节内容适中，单独处理"}',
        "]",
        "```",
        "",
        "要求：",
        "1. sections 必须是连续的章节号",
        "2. 所有章节必须被覆盖，不能遗漏",
        "3. 没有译文的章节（有译文=否）也要包含在计划中",
        "4. chunk_id 从 chunk_01 开始，按顺序编号",
        "5. reason 用中文简洁说明分组原因",
        "",
        "只输出 JSON 数组，不要有其他文字。",
    ]
    return "\n".join(lines)


def plan_chunks(
    sections: list[SectionInfo],
    guide: str,
    client,
    logger,
) -> list[Chunk]:
    """Call Claude to decide how to group sections into processing chunks."""
    from config import MODEL  # local import to avoid circular deps

    user_message = _build_user_message(guide, sections)

    request = {
        "model": MODEL,
        "max_tokens": 2048,
        "system": _SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_message}],
    }
    logger.write_planning_request(request)

    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw_text = response.content[0].text.strip()
    logger.write_planning_response(raw_text)

    # Extract JSON array (model might wrap it in ```json ... ```)
    json_match = re.search(r"\[.*\]", raw_text, re.DOTALL)
    if not json_match:
        raise ValueError(f"分块规划响应中未找到 JSON 数组：\n{raw_text[:200]}")

    chunk_data = json.loads(json_match.group(0))

    chunks: list[Chunk] = []
    for item in chunk_data:
        chunks.append(Chunk(
            chunk_id=item["chunk_id"],
            sections=item["sections"],
            reason=item.get("reason", ""),
        ))

    return chunks
