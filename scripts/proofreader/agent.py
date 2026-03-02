"""
agent.py - ReAct 智能体循环

核心设计：
- 每个处理单元启动一次带工具调用的 Claude 会话
- 使用 tool_choice="any" 强制 Claude 必须调用工具，不允许纯文本回应
- 循环终止条件：mark_unit_done 被调用（而非 stop_reason）
- 不跨单元传递对话历史（避免 context 膨胀）
- 跨单元一致性通过 AgentState 实现

缓存策略（Anthropic 按 tools → system → messages 顺序构建前缀缓存）：
  1. tools（最后一个工具带 cache_control）→ 工具定义整体被缓存
  2. system[0] 静态角色/原则（cache_control）→ 不变，一直命中
  3. system[1] 术语表（cache_control）→ 术语更新时失效，其余命中
"""

import json
from pathlib import Path

import anthropic

from .config import MODEL
from .display import ProofreadingDisplay
from .logger import SessionLogger
from .reader import read_original_section, read_translated_section
from .state import AgentState, ProcessingUnit
from .tools import TOOL_SCHEMAS, ToolExecutor

# 每个单元最多允许的 ReAct 轮次，防止无限循环
MAX_TOOL_ROUNDS = 40

# Claude 连续多少轮没有调用工具后放弃
MAX_NUDGE_ROUNDS = 3

# ─────────────────────────────────────────────────────────
# 系统提示
# ─────────────────────────────────────────────────────────

_SYSTEM_STATIC = """\
你是一位资深中文技术文档翻译校对专家，专门校对 Google 编程风格指南的中文译文。

## 翻译原则

1. **忠实原文**：保持与原文语义的一致性，不擅自增减内容。表格和图示等内容尽量保持和原文格式一致。
2. **技术术语**：不常用的术语首次出现时保留英文原文，格式为 `中文（English）`，并加粗。有多种中文翻译或可能引起歧义的术语也要加粗。其他时候，不要加粗，除非原文如此。
3. **代码示例**：代码块内容保持原文不变，仅翻译注释和必要的字符串常量。
4. **语气风格**：使用正式、简洁、本土化的中文技术文档风格，保证信达雅。可以调整语序来保证语言流畅。不要出现翻译腔。不要使用互联网黑话，除非是为了匹配原文风格。
5. **用户画像**：读者是对编程有一定了解、在中文语言环境下长期生活的技术人员。

## 工作流程

你**必须通过工具调用**完成所有工作，不能仅用文字描述打算做什么。对于每个处理单元：

1. 逐章节对比原文和译文，检查完整性、术语、流畅度和代码示例
2. 调用 `check_term_consistency` 验证关键术语是否与术语表一致
3. 调用 `report_issue` 记录所有发现的问题（不管是否修改，都要记录）
4. 调用 `update_glossary` 新增或修正术语条目
5. 需要修改译文时，调用 `apply_section_correction` 提供完整修正后内容
6. 对有歧义、需要人工决策的内容，调用 `flag_for_human_review`
7. 所有章节处理完毕后，调用 `mark_unit_done` 结束本单元

## 校对要点

**完整性**：对比原文章节标题和子标题，确认译文没有遗漏任何章节；检查示例、列表、表格是否完整保留。

**术语一致性**：相同英文术语在整篇文档中应使用相同中文翻译；先用 `check_term_consistency` 查询已知翻译再做判断。

**流畅度**：避免逐字翻译导致的生硬表达；句子结构应符合中文习惯，不要出现翻译腔。

**代码示例**：代码本身保持原样；只翻译 `//`、`/* */` 内的注释；必要的字符串常量可翻译。
"""


def _build_system_prompt(state: AgentState) -> list[dict]:
    """构建带 Prompt Caching 的系统提示。

    缓存层次（从稳定到易变）：
    - system[0]：角色 + 原则 + 工作流程（永不变化，长期命中缓存）
    - system[1]：术语表（新增术语时失效，其余情况命中缓存）
    """
    glossary_md = state.get_glossary_markdown()
    glossary_section = f"## 当前术语对照表\n\n{glossary_md}"

    return [
        {
            "type": "text",
            "text": _SYSTEM_STATIC,
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": glossary_section,
            "cache_control": {"type": "ephemeral"},
        },
    ]


def _build_user_prompt(guide: str, unit: ProcessingUnit, state: AgentState) -> str:
    """构建处理单元的用户提示，直接内嵌原文和译文。"""
    parts = [
        f"# 校对任务：{unit.unit_id}（章节 {', '.join(unit.sections)}）\n",
        f"分组原因：{unit.reason}\n",
    ]

    # 将近期术语一致性问题带入上下文
    recent_term_issues = [
        i for i in state.issues[-10:] if i.issue_type == "terminology"
    ]
    if recent_term_issues:
        parts.append("\n## 注意：近期发现的术语一致性问题\n")
        for issue in recent_term_issues[-3:]:
            parts.append(f"- §{issue.section_num}: {issue.description[:120]}\n")

    # 直接内嵌各章节的原文和译文
    for section_num in unit.sections:
        original = read_original_section(guide, section_num)
        translated = read_translated_section(guide, section_num)

        parts.append(f"\n---\n\n## 章节 {section_num}\n")

        if original:
            parts.append(f"\n### 原文（英文）\n\n```\n{original}\n```\n")
        else:
            parts.append("\n### 原文（英文）\n\n（未找到原文，请跳过此章节）\n")

        if translated:
            parts.append(f"\n### 译文（中文）\n\n{translated}\n")
        else:
            parts.append('\n### 译文（中文）\n\n（暂无译文，请跳过校对，仅用 report_issue 标注"缺失翻译"）\n')

    parts.append(f"""
---

请立即开始通过工具调用进行校对。你必须调用工具，不能只用文字描述。
完成所有章节后调用 mark_unit_done（unit_id: "{unit.unit_id}"）。
""")

    return "".join(parts)


# ─────────────────────────────────────────────────────────
# 单元校对（ReAct 循环）
# ─────────────────────────────────────────────────────────

def proofread_unit(
    guide: str,
    unit: ProcessingUnit,
    state: AgentState,
    client: anthropic.Anthropic,
    executor: ToolExecutor,
    display: ProofreadingDisplay,
    logger: SessionLogger,
    unit_dir: Path,
    stream: bool = True,
) -> None:
    """对一个处理单元执行完整的 ReAct 校对循环。

    退出条件（优先级从高到低）：
    1. mark_unit_done 被调用后执行工具结果 → 立即退出
    2. 达到 MAX_TOOL_ROUNDS 轮次上限
    3. 连续 MAX_NUDGE_ROUNDS 轮无工具调用（异常情况，已多次催促）
    """
    system = _build_system_prompt(state)
    user_content = _build_user_prompt(guide, unit, state)
    messages: list[dict] = [{"role": "user", "content": user_content}]

    request_body: dict = {
        "model": MODEL,
        "max_tokens": 8192,
        "system": system,
        "tools": TOOL_SCHEMAS,
        "tool_choice": {"type": "any"},  # 强制必须调用工具
        "messages": messages,
    }
    logger.log_unit_request(unit_dir, messages, system, TOOL_SCHEMAS)

    nudge_count = 0  # 连续无工具调用的轮次计数

    for round_num in range(MAX_TOOL_ROUNDS):
        # ── API 调用 ──────────────────────────────────────
        if stream:
            response_text, tool_uses, stop_reason, usage = _stream_response(
                client, request_body, display
            )
        else:
            response_text, tool_uses, stop_reason, usage = _blocking_response(
                client, request_body
            )

        # 记录响应（含实际文本内容）
        logger.log_unit_response(unit_dir, {
            "round": round_num,
            "stop_reason": stop_reason,
            "text": response_text,          # 完整响应文本
            "text_length": len(response_text),
            "tool_uses": len(tool_uses),
            "tool_names": [tu["name"] for tu in tool_uses],
            "usage": usage,
        })

        # ── 构建 assistant 消息 ────────────────────────────
        assistant_content: list[dict] = []
        if response_text:
            assistant_content.append({"type": "text", "text": response_text})
        for tu in tool_uses:
            assistant_content.append({
                "type": "tool_use",
                "id": tu["id"],
                "name": tu["name"],
                "input": tu["input"],
            })
        messages.append({"role": "assistant", "content": assistant_content})

        # ── 处理无工具调用的情况 ───────────────────────────
        if not tool_uses:
            # 如果单元已完成（正常情况：mark_unit_done 在上轮被调用）
            if unit.unit_id in state.units_done:
                break

            nudge_count += 1
            if nudge_count >= MAX_NUDGE_ROUNDS:
                # 多次催促后仍未使用工具，放弃本单元
                logger.log_unit_response(unit_dir, {
                    "round": round_num,
                    "warning": f"连续 {nudge_count} 轮无工具调用，放弃本单元",
                })
                break

            # 催促 Claude 使用工具
            nudge_msg = (
                "你必须通过工具调用完成校对，不能仅用文字描述。"
                f"请立即调用工具处理章节 {', '.join(unit.sections)}，"
                f"完成后调用 mark_unit_done（unit_id: \"{unit.unit_id}\"）。"
            )
            messages.append({"role": "user", "content": nudge_msg})
            request_body["messages"] = messages
            # 保持 tool_choice="any" 继续强制
            continue

        nudge_count = 0  # 有工具调用，重置催促计数

        # ── 执行工具调用 ───────────────────────────────────
        tool_results = []
        tool_call_logs = []

        for tu in tool_uses:
            tool_name = tu["name"]
            tool_input = tu["input"]
            display.update_tool_call(tool_name, tool_input)

            result = executor.execute(tool_name, tool_input)

            if tool_name == "update_glossary" and "error" not in result:
                logger.log_glossary_update(
                    tool_input.get("term_en", ""),
                    tool_input.get("term_zh", ""),
                    tool_input.get("note", ""),
                    result,
                )

            result_str = json.dumps(result, ensure_ascii=False)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tu["id"],
                "content": result_str,
            })
            tool_call_logs.append({
                "round": round_num,
                "tool": tool_name,
                "input": tool_input,
                "output": result,
            })

        logger.log_tool_calls(unit_dir, tool_call_logs)
        display.update_stats(
            state.total_issues,
            state.total_corrections,
            state.total_human_reviews,
        )

        # 添加工具结果，进入下一轮
        messages.append({"role": "user", "content": tool_results})
        request_body["messages"] = messages

        # mark_unit_done 已调用 → 退出循环（无需再发起 API 请求）
        if unit.unit_id in state.units_done:
            break


# ─────────────────────────────────────────────────────────
# API 调用实现
# ─────────────────────────────────────────────────────────

def _stream_response(
    client: anthropic.Anthropic,
    request_body: dict,
    display: ProofreadingDisplay,
) -> tuple[str, list[dict], str, dict]:
    """流式 API 调用，实时更新终端显示。

    使用 event.type 字段（如 "content_block_start"）而非 type(event).__name__，
    避免因 SDK 版本差异（RawContentBlockStopEvent vs ParsedContentBlockStopEvent）
    导致事件无法匹配的问题。
    """
    text_parts: list[str] = []
    tool_uses: list[dict] = []
    stop_reason = "end_turn"
    usage: dict = {}

    current_tool: dict | None = None
    current_tool_input_str = ""

    with client.messages.stream(**request_body) as stream_ctx:
        for event in stream_ctx:
            etype = getattr(event, "type", None)

            if etype == "content_block_start":
                block = event.content_block
                if block.type == "tool_use":
                    current_tool = {"id": block.id, "name": block.name, "input": {}}
                    current_tool_input_str = ""

            elif etype == "content_block_delta":
                delta = event.delta
                if delta.type == "text_delta":
                    text_parts.append(delta.text)
                    display.stream_token(delta.text)
                elif delta.type == "input_json_delta" and current_tool is not None:
                    current_tool_input_str += delta.partial_json

            elif etype == "content_block_stop":
                if current_tool is not None:
                    try:
                        current_tool["input"] = (
                            json.loads(current_tool_input_str)
                            if current_tool_input_str else {}
                        )
                    except json.JSONDecodeError:
                        current_tool["input"] = {}
                    tool_uses.append(current_tool)
                    current_tool = None
                    current_tool_input_str = ""

            elif etype == "message_stop":
                # ParsedMessageStopEvent 有 message 属性，RawMessageStopEvent 也有
                msg = getattr(event, "message", None)
                if msg:
                    stop_reason = msg.stop_reason or "end_turn"

            elif etype == "message_delta":
                if hasattr(event, "usage") and event.usage:
                    usage = {"output_tokens": event.usage.output_tokens}

    return "".join(text_parts), tool_uses, stop_reason, usage


def _blocking_response(
    client: anthropic.Anthropic,
    request_body: dict,
) -> tuple[str, list[dict], str, dict]:
    """非流式 API 调用（--no-stream 模式）。"""
    response = client.messages.create(**request_body)
    text_parts = []
    tool_uses = []

    for block in response.content:
        if block.type == "text":
            text_parts.append(block.text)
        elif block.type == "tool_use":
            tool_uses.append({
                "id": block.id,
                "name": block.name,
                "input": block.input,
            })

    usage = response.usage.model_dump() if response.usage else {}
    return "".join(text_parts), tool_uses, response.stop_reason or "end_turn", usage
