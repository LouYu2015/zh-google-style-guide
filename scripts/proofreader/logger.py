"""
logger.py - Debug 日志记录

每次运行创建独立目录：debug/proofreader_{session_id}/
记录所有 API 请求/响应、工具调用、状态变更和最终报告。
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .state import AgentState


class SessionLogger:
    """会话级别的 Debug 日志记录器。"""

    def __init__(self, session_id: str, repo_root: Path):
        self.session_id = session_id
        self.debug_dir = repo_root / "debug" / f"proofreader_{session_id}"
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        self._unit_counters: dict[str, int] = {}  # unit_id -> call count

    def _write_json(self, path: Path, data: Any) -> None:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def log_run_info(self, guide: str, model: str, dry_run: bool, extra: dict | None = None) -> None:
        info = {
            "session_id": self.session_id,
            "guide": guide,
            "model": model,
            "dry_run": dry_run,
            "started_at": datetime.now().isoformat(),
        }
        if extra:
            info.update(extra)
        self._write_json(self.debug_dir / "run_info.json", info)

    def log_planning_request(self, request: dict) -> None:
        self._write_json(self.debug_dir / "planning_request.json", request)

    def log_planning_response(self, response: dict) -> None:
        self._write_json(self.debug_dir / "planning_response.json", response)

    def get_unit_dir(self, unit_id: str, sections: list[str]) -> Path:
        """获取并创建处理单元的日志目录。"""
        sections_str = "_".join(sections[:3])  # 最多取前3个章节号
        if len(sections) > 3:
            sections_str += "..."
        unit_dir = self.debug_dir / f"{unit_id}_{sections_str}"
        unit_dir.mkdir(exist_ok=True)
        return unit_dir

    def log_unit_request(self, unit_dir: Path, messages: list, system: list, tools: list) -> None:
        self._write_json(unit_dir / "request.json", {
            "system": system,
            "messages": messages,
            "tools": tools,
        })

    def log_unit_response(self, unit_dir: Path, response_data: dict) -> None:
        """追加记录每轮响应（不覆盖，保留所有轮次的历史）。"""
        path = unit_dir / "response.json"
        rounds: list = []
        if path.exists():
            try:
                existing = json.loads(path.read_text())
                rounds = existing if isinstance(existing, list) else [existing]
            except json.JSONDecodeError:
                pass
        rounds.append(response_data)
        self._write_json(path, rounds)

    def log_tool_calls(self, unit_dir: Path, tool_calls: list[dict]) -> None:
        """记录本轮工具调用的输入/输出。"""
        existing_path = unit_dir / "tool_calls.json"
        existing: list = []
        if existing_path.exists():
            existing = json.loads(existing_path.read_text())
        existing.extend(tool_calls)
        self._write_json(existing_path, existing)

    def log_glossary_update(self, term_en: str, term_zh: str, note: str, result: dict) -> None:
        updates_path = self.debug_dir / "glossary_updates.json"
        updates: list = []
        if updates_path.exists():
            updates = json.loads(updates_path.read_text())
        updates.append({
            "timestamp": datetime.now().isoformat(),
            "term_en": term_en,
            "term_zh": term_zh,
            "note": note,
            "result": result,
        })
        self._write_json(updates_path, updates)

    def save_state(self, state: AgentState) -> None:
        state.save(self.debug_dir / "state.json")

    def write_final_report(self, state: AgentState, dry_run: bool) -> Path:
        """生成最终校对报告（Markdown）。"""
        lines = [
            f"# {state.guide.title()} 风格指南校对报告\n",
            f"**日期**: {datetime.now().strftime('%Y-%m-%d %H:%M')} | "
            f"**会话**: {state.session_id} | "
            f"**模式**: {'仅报告（dry-run）' if dry_run else '已应用修正'}\n",
            "\n## 执行摘要\n",
        ]

        units_done = len(state.units_done)
        units_total = len(state.processing_plan)
        applied = sum(1 for c in state.corrections if c.applied)
        high = sum(1 for i in state.issues if i.severity == "high")
        med = sum(1 for i in state.issues if i.severity == "medium")
        low = sum(1 for i in state.issues if i.severity == "low")

        lines += [
            f"- 处理单元: {units_done}/{units_total} 个\n",
            f"- 发现问题: {state.total_issues} 个"
            f"（高: {high}, 中: {med}, 低: {low}）\n",
            f"- 修正记录: {state.total_corrections} 处"
            f"（已应用: {applied}）\n",
            f"- 待人工审核: {state.total_human_reviews} 项\n",
        ]

        # 单元摘要
        lines.append("\n## 各处理单元摘要\n")
        for unit in state.processing_plan:
            status = "✅ 已完成" if unit.done else "⏳ 未处理"
            lines.append(f"### {unit.unit_id}（章节 {', '.join(unit.sections)}）{status}\n")
            if unit.summary:
                lines.append(f"{unit.summary}\n\n")

        # 术语表更新
        lines.append("\n## 术语表变更\n")
        if state.glossary:
            lines.append("| 英文 | 中文 | 说明 | 来源章节 |\n")
            lines.append("|------|------|------|----------|\n")
            for entry in sorted(state.glossary.values(), key=lambda e: e.term_en):
                src = entry.source_section or "—"
                lines.append(f"| {entry.term_en} | {entry.term_zh} | {entry.note} | {src} |\n")
        else:
            lines.append("无术语表变更。\n")

        # 问题列表
        lines.append("\n## 详细问题列表\n")
        if state.issues:
            for severity in ("high", "medium", "low"):
                label = {"high": "🔴 高优先级", "medium": "🟡 中等优先级", "low": "🟢 低优先级"}[severity]
                issues = [i for i in state.issues if i.severity == severity]
                if issues:
                    lines.append(f"\n### {label}\n\n")
                    for issue in issues:
                        lines.append(
                            f"**[{issue.issue_id}]** 章节 `{issue.section_num}` "
                            f"（{issue.issue_type}）\n"
                        )
                        lines.append(f"{issue.description}\n\n")
        else:
            lines.append("未发现问题。\n")

        # 人工审核项
        lines.append("\n## 需要人工介入的问题\n")
        if state.human_review_items:
            for item in state.human_review_items:
                lines.append(f"\n### [{item.review_id}] 章节 {item.section_num}\n")
                lines.append(f"**问题**: {item.question}\n\n")
                lines.append(f"**上下文**:\n```\n{item.context}\n```\n\n")
                if item.options:
                    lines.append("**可能的选项**:\n")
                    for opt in item.options:
                        lines.append(f"- {opt}\n")
                lines.append("\n")
        else:
            lines.append("无需人工介入的问题。\n")

        report_path = self.debug_dir / "report.md"
        report_path.write_text("".join(lines), encoding="utf-8")
        return report_path
