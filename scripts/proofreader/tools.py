"""
tools.py - Claude 工具定义与执行

定义两部分：
1. TOOL_SCHEMAS：发送给 Claude 的 JSON schema（tool definitions）
2. ToolExecutor：执行工具调用的 Python 实现
"""

import json
from dataclasses import asdict
from typing import Any

from .reader import (
    read_original_section,
    read_translated_section,
    write_section,
    estimate_tokens,
)
from .state import AgentState


# ─────────────────────────────────────────────────────────
# Tool Schemas（Claude 工具定义）
# ─────────────────────────────────────────────────────────

TOOL_SCHEMAS = [
    {
        "name": "get_glossary",
        "description": "获取当前完整的术语对照表（Markdown 格式）。",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "update_glossary",
        "description": (
            "添加或更新术语对照表中的条目。"
            "当发现新术语、发现现有术语翻译不一致、或需要更新注释时调用。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "term_en": {
                    "type": "string",
                    "description": "英文术语",
                },
                "term_zh": {
                    "type": "string",
                    "description": "中文翻译",
                },
                "note": {
                    "type": "string",
                    "description": "使用说明或注释（可选）",
                },
                "source_section": {
                    "type": "string",
                    "description": "首次出现的章节号（可选）",
                },
            },
            "required": ["term_en", "term_zh"],
        },
    },
    {
        "name": "check_term_consistency",
        "description": "检查某个英文术语在术语表中是否有已知翻译，以确保一致性。",
        "input_schema": {
            "type": "object",
            "properties": {
                "term_en": {
                    "type": "string",
                    "description": "要检查的英文术语",
                }
            },
            "required": ["term_en"],
        },
    },
    {
        "name": "report_issue",
        "description": (
            "报告在译文中发现的问题。"
            "问题类型：omission（遗漏）、fluency（流畅度）、"
            "terminology（术语）、code_example（代码示例）、other（其他）。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "section_num": {
                    "type": "string",
                    "description": "问题所在章节号",
                },
                "issue_type": {
                    "type": "string",
                    "enum": ["omission", "fluency", "terminology", "code_example", "other"],
                    "description": "问题类型",
                },
                "description": {
                    "type": "string",
                    "description": "问题的详细描述，包括原文内容和存在的问题",
                },
                "severity": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                    "description": "严重程度：low=轻微，medium=中等，high=严重",
                },
            },
            "required": ["section_num", "issue_type", "description", "severity"],
        },
    },
    {
        "name": "flag_for_human_review",
        "description": (
            "标记需要人工决策的情况。"
            "当存在多种可能的翻译方案、文化差异需要人工判断、"
            "或原文意图不明确时使用。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "section_num": {
                    "type": "string",
                    "description": "相关章节号",
                },
                "question": {
                    "type": "string",
                    "description": "需要人工回答的具体问题",
                },
                "context": {
                    "type": "string",
                    "description": "相关的原文和译文片段，提供足够的上下文",
                },
                "options": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "可能的选项列表（如果有）",
                },
            },
            "required": ["section_num", "question", "context"],
        },
    },
    {
        "name": "apply_section_correction",
        "description": (
            "将修正后的完整章节内容写回译文文件。"
            "只有在已经完成该章节的完整审阅并确定所有修改后才调用此工具。"
            "提供该章节完整的修正后 Markdown 内容（包含标题行）。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "section_num": {
                    "type": "string",
                    "description": "要修正的章节号",
                },
                "full_corrected_content": {
                    "type": "string",
                    "description": "修正后的完整章节 Markdown 内容，必须包含标题行",
                },
                "reason": {
                    "type": "string",
                    "description": "修正的主要原因摘要",
                },
            },
            "required": ["section_num", "full_corrected_content", "reason"],
        },
    },
    {
        "name": "mark_unit_done",
        "description": (
            "标记当前处理单元已完成校对。"
            "完成所有检查（包括内容审查、术语更新、问题报告、修正应用）后调用。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "unit_id": {
                    "type": "string",
                    "description": "处理单元 ID，如 'unit_01'",
                },
                "summary": {
                    "type": "string",
                    "description": "本单元校对摘要（3-5 句话，说明主要发现和修改）",
                },
            },
            "required": ["unit_id", "summary"],
        },
    },
    {
        "name": "get_progress",
        "description": "获取当前校对进度（已完成/待处理的单元数和统计信息）。",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        # 工具定义放在最后一个条目上添加 cache_control，使工具定义整体被缓存。
        # Anthropic API 按 tools → system → messages 顺序构建缓存前缀，
        # 此处缓存覆盖全部工具定义，后续请求直接命中，节省输入 token。
        "cache_control": {"type": "ephemeral"},
    },
]


# ─────────────────────────────────────────────────────────
# Tool Executor
# ─────────────────────────────────────────────────────────

class ToolExecutor:
    """执行 Claude 请求的工具调用，更新 AgentState。"""

    def __init__(self, guide: str, state: AgentState, dry_run: bool = False):
        self.guide = guide
        self.state = state
        self.dry_run = dry_run
        self._corrections_buffer: dict[str, dict] = {}  # section_num -> correction info

    def execute(self, tool_name: str, tool_input: dict) -> Any:
        """执行工具调用，返回结果（将被序列化为字符串发给 Claude）。"""
        handler = getattr(self, f"_tool_{tool_name}", None)
        if handler is None:
            return {"error": f"未知工具: {tool_name}"}
        try:
            return handler(**tool_input)
        except Exception as e:
            return {"error": str(e)}

    def _tool_read_section(self, section_num: str) -> dict:
        original = read_original_section(self.guide, section_num)
        translated = read_translated_section(self.guide, section_num)
        combined_tokens = estimate_tokens(original or "") + estimate_tokens(translated or "")
        return {
            "section_num": section_num,
            "original": original or "（未找到原文）",
            "translated": translated or "（暂无译文）",
            "has_translation": translated is not None and len((translated or "").strip()) > 50,
            "token_estimate": combined_tokens,
        }

    def _tool_get_glossary(self) -> str:
        return self.state.get_glossary_markdown()

    def _tool_update_glossary(
        self,
        term_en: str,
        term_zh: str,
        note: str = "",
        source_section: str = "",
    ) -> dict:
        result = self.state.add_or_update_glossary(term_en, term_zh, note, source_section)
        return result

    def _tool_check_term_consistency(self, term_en: str) -> dict:
        return self.state.check_term(term_en)

    def _tool_report_issue(
        self,
        section_num: str,
        issue_type: str,
        description: str,
        severity: str,
    ) -> dict:
        issue_id = self.state.add_issue(section_num, issue_type, description, severity)
        return {"issue_id": issue_id, "status": "recorded"}

    def _tool_flag_for_human_review(
        self,
        section_num: str,
        question: str,
        context: str,
        options: list[str] | None = None,
    ) -> dict:
        rid = self.state.add_review_item(section_num, question, context, options or [])
        return {"review_id": rid, "status": "flagged"}

    def _tool_apply_section_correction(
        self,
        section_num: str,
        full_corrected_content: str,
        reason: str,
    ) -> dict:
        # 记录修正（不管 dry_run 都记录）
        cid = self.state.add_correction(
            section_num=section_num,
            original_zh=read_translated_section(self.guide, section_num) or "",
            corrected_zh=full_corrected_content,
            reason=reason,
        )

        if self.dry_run:
            # 标记已应用（逻辑上）
            for c in self.state.corrections:
                if c.correction_id == cid:
                    c.applied = False  # dry_run 下不实际应用
            return {"correction_id": cid, "status": "dry_run_skipped", "diff_lines": 0}

        try:
            diff = write_section(self.guide, section_num, full_corrected_content)
            for c in self.state.corrections:
                if c.correction_id == cid:
                    c.applied = True
            return {"correction_id": cid, "status": "applied", "diff_lines": diff}
        except Exception as e:
            return {"correction_id": cid, "status": "error", "error": str(e)}

    def _tool_mark_unit_done(self, unit_id: str, summary: str) -> dict:
        remaining = self.state.mark_unit_done(unit_id, summary)
        return {
            "status": "done",
            "unit_id": unit_id,
            "remaining_units": remaining,
        }

    def _tool_get_progress(self) -> dict:
        return {
            "done": self.state.units_done,
            "pending": [u.unit_id for u in self.state.units_pending],
            "total_units": len(self.state.processing_plan),
            "total_issues": self.state.total_issues,
            "total_corrections": self.state.total_corrections,
            "total_human_reviews": self.state.total_human_reviews,
        }
