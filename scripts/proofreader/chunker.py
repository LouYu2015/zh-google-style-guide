"""
chunker.py - 智能文档分块

第一阶段：调用 Claude 分析章节结构，生成最优的处理计划。
Claude 根据各章节的 token 估算，自主决定如何合并或拆分，
不依赖硬编码的 token 阈值。
"""

import json
from typing import Any

import anthropic

from .reader import SectionInfo
from .state import ProcessingUnit


_PLANNING_SYSTEM = """\
你是一个专业的文档分析专家，擅长制定翻译校对工作计划。
你需要根据文档的章节结构，设计出最优的分批处理方案。

目标：
- 每个处理单元的内容（原文+译文）在 1000–5000 tokens 之间最理想
- 相关联的小节应合并为一个处理单元，以便智能体理解上下文
- 过大的章节应拆分为若干子章节单独处理
- 保持章节编号的逻辑连贯性
"""


def build_planning_prompt(guide: str, sections: list[SectionInfo]) -> str:
    lines = [
        f"# {guide} 风格指南章节结构分析\n",
        "请根据以下章节结构，制定校对处理计划。\n",
        "## 章节列表\n",
        "| 章节号 | 标题 | 层级 | 估算tokens | 有译文 |",
        "|--------|------|------|-----------|--------|",
    ]
    for s in sections:
        translated = "是" if s.has_translation else "否"
        lines.append(f"| {s.num} | {s.title} | H{s.level} | {s.token_estimate} | {translated} |")

    lines.append("""
## 输出要求

输出一个 JSON 数组，每个元素代表一个处理单元：

```json
[
  {
    "unit_id": "unit_01",
    "sections": ["1", "1.1", "1.2"],
    "reason": "这几个章节内容较少，合并处理效率更高"
  },
  {
    "unit_id": "unit_02",
    "sections": ["2"],
    "reason": "此章节内容适中，单独处理"
  }
]
```

要求：
1. 每个处理单元的 sections 必须是连续的章节号
2. 所有章节必须被覆盖，不能遗漏
3. 没有译文的章节（有译文=否）也要包含在计划中（会标注为"待翻译"跳过）
4. unit_id 从 unit_01 开始，按顺序编号
5. reason 用中文简洁说明分组原因

只输出 JSON 数组，不要有其他文字。
""")
    return "\n".join(lines)


def plan_processing_units(
    guide: str,
    sections: list[SectionInfo],
    client: anthropic.Anthropic,
    model: str,
    logger: Any = None,
) -> list[ProcessingUnit]:
    """调用 Claude 分析章节结构，返回处理计划。"""
    prompt = build_planning_prompt(guide, sections)

    request_body = {
        "model": model,
        "max_tokens": 2048,
        "system": _PLANNING_SYSTEM,
        "messages": [{"role": "user", "content": prompt}],
    }

    if logger:
        logger.log_planning_request(request_body)

    response = client.messages.create(**request_body)
    raw = response.content[0].text.strip()

    if logger:
        logger.log_planning_response({"content": raw, "usage": response.usage.model_dump()})

    # 提取 JSON（允许被 markdown 代码块包裹）
    json_str = raw
    if "```" in raw:
        start = raw.find("```")
        end = raw.rfind("```")
        if start != end:
            block = raw[start:end]
            # 去掉第一行（```json）
            first_nl = block.find("\n")
            json_str = block[first_nl + 1:] if first_nl != -1 else block[3:]

    try:
        plan_data: list[dict] = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Claude 返回了无效的 JSON 分块计划：{e}\n原始内容：\n{raw}")

    units = []
    for item in plan_data:
        units.append(ProcessingUnit(
            unit_id=item["unit_id"],
            sections=item["sections"],
            reason=item.get("reason", ""),
        ))
    return units


def validate_plan(plan: list[ProcessingUnit], sections: list[SectionInfo]) -> list[str]:
    """验证处理计划是否覆盖了所有章节，返回警告信息列表。"""
    planned_nums = {num for unit in plan for num in unit.sections}
    all_nums = {s.num for s in sections}
    missing = all_nums - planned_nums
    extra = planned_nums - all_nums

    warnings = []
    if missing:
        warnings.append(f"以下章节未被纳入处理计划：{sorted(missing)}")
    if extra:
        warnings.append(f"处理计划包含不存在的章节：{sorted(extra)}")
    return warnings
