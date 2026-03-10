"""
logger.py - Debug logging for proofreader sessions.

Writes structured logs to debug/proofreader_{session_id}/
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


class DebugLogger:
    def __init__(self, session_id: str, guide: str, debug_root: str = "debug") -> None:
        self.session_id = session_id
        self.guide = guide
        root = Path(__file__).parent.parent.parent / debug_root
        self.session_dir = root / f"proofreader_{session_id}"
        self.session_dir.mkdir(parents=True, exist_ok=True)

    def _write_json(self, path: Path, data: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _write_text(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    # ──────────────────────────────────────────────
    # Session-level logs
    # ──────────────────────────────────────────────

    def write_run_info(
        self,
        guide: str,
        model: str,
        dry_run: bool,
        resume: bool,
        started_at: str,
    ) -> None:
        self._write_json(
            self.session_dir / "run_info.json",
            {
                "session_id": self.session_id,
                "guide": guide,
                "model": model,
                "dry_run": dry_run,
                "resume": resume,
                "started_at": started_at,
            },
        )

    def write_planning_request(self, request: dict) -> None:
        self._write_json(self.session_dir / "planning_request.json", request)

    def write_planning_response(self, response: str) -> None:
        self._write_text(self.session_dir / "planning_response.txt", response)

    def write_state(self, state_obj) -> None:
        """Delegate to AgentState.save() so state.json is always up to date."""
        state_obj.save(self.session_dir)

    # ──────────────────────────────────────────────
    # Per-chunk logs
    # ──────────────────────────────────────────────

    def _chunk_dir(self, chunk_id: str) -> Path:
        return self.session_dir / chunk_id

    def write_chunk_request(self, chunk_id: str, request: dict) -> None:
        self._write_json(self._chunk_dir(chunk_id) / "request.json", request)

    def write_chunk_response(
        self, chunk_id: str, full_text: str, thinking_text: str
    ) -> None:
        d = self._chunk_dir(chunk_id)
        self._write_text(d / "response.txt", full_text)
        if thinking_text:
            self._write_text(d / "thinking.txt", thinking_text)

    def write_chunk_result(
        self,
        chunk_id: str,
        corrections: dict,
        issues_text: str,
        notes: str,
        human_review: str,
    ) -> None:
        self._write_json(
            self._chunk_dir(chunk_id) / "result.json",
            {
                "corrections": {k: v for k, v in corrections.items()},
                "issues": issues_text,
                "notes": notes,
                "human_review": human_review,
                "corrections_count": len(corrections),
            },
        )

    # ──────────────────────────────────────────────
    # Final report
    # ──────────────────────────────────────────────

    def write_report(self, state) -> None:
        from state import AgentState  # avoid circular import at module level

        lines: list[str] = []
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        mode = "dry-run（未写入）" if state.dry_run else "已应用修正"

        done_count = sum(1 for c in state.chunks if c.status == "done")
        total_corrections = sum(c.corrections_count for c in state.chunks)
        high = sum(1 for i in state.issues if i.severity == "high")
        med = sum(1 for i in state.issues if i.severity == "medium")
        low = sum(1 for i in state.issues if i.severity == "low")

        lines += [
            f"# {state.guide.upper()} 风格指南校对报告",
            f"**日期**: {now} | **会话**: {state.session_id} | **模式**: {mode}",
            "",
            "## 执行摘要",
            f"- 处理块数: {done_count}/{len(state.chunks)} 个",
            f"- 发现问题: {len(state.issues)} 个（高: {high}, 中: {med}, 低: {low}）",
            f"- 修正记录: {total_corrections} 处",
            f"- 待人工审核: {len(state.human_review_items)} 项",
            "",
            "## 各处理块摘要",
        ]

        for chunk in state.chunks:
            sections_str = ", ".join(chunk.sections)
            status_icon = {"done": "✅", "skipped": "⏭️", "pending": "⏳", "processing": "🔄"}.get(
                chunk.status, "❓"
            )
            lines.append(f"### {chunk.chunk_id}（章节 {sections_str}）{status_icon} {chunk.status}")
            if chunk.notes:
                lines.append(chunk.notes[:300])
            lines.append("")

        if state.issues:
            lines += ["## 发现的问题", ""]
            for issue in state.issues:
                sev_map = {"high": "🔴", "medium": "🟡", "low": "🟢"}
                icon = sev_map.get(issue.severity, "⚪")
                lines.append(f"- {icon} [{issue.section}] {issue.description}")
            lines.append("")

        if state.human_review_items:
            lines += ["## 待人工审核", ""]
            for item in state.human_review_items:
                lines.append(f"- [{item.section}] {item.description}")
            lines.append("")

        if state.glossary:
            lines += ["## 术语表变更", "| 英文 | 中文 | 说明 |", "|------|------|------|"]
            for term_en, entry in sorted(state.glossary.items()):
                lines.append(f"| {term_en} | {entry.get('term_zh', '')} | {entry.get('note', '')} |")
            lines.append("")

        self._write_text(self.session_dir / "report.md", "\n".join(lines))
