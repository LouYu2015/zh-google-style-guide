"""
state.py - 智能体运行状态管理

AgentState 包含整个校对会话的所有持久数据：
- 术语表（跨章节维护一致性）
- 发现的问题列表
- 修正记录
- 人工审核项
- 处理计划与进度
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class Issue:
    issue_id: str
    section_num: str
    issue_type: str   # omission | fluency | terminology | code_example | other
    description: str
    severity: str     # low | medium | high


@dataclass
class Correction:
    correction_id: str
    section_num: str
    original_zh: str
    corrected_zh: str
    reason: str
    applied: bool = False


@dataclass
class ReviewItem:
    review_id: str
    section_num: str
    question: str
    context: str
    options: list[str] = field(default_factory=list)


@dataclass
class GlossaryEntry:
    term_en: str
    term_zh: str
    note: str = ""
    source_section: str = ""
    usage_count: int = 0


@dataclass
class ProcessingUnit:
    unit_id: str         # e.g. "unit_01"
    sections: list[str]  # e.g. ["1.1", "1.2"]
    reason: str          # Claude 给出的分块理由
    done: bool = False
    summary: str = ""    # 完成后的摘要


@dataclass
class AgentState:
    guide: str
    session_id: str
    glossary: dict[str, GlossaryEntry] = field(default_factory=dict)  # keyed by term_en
    issues: list[Issue] = field(default_factory=list)
    corrections: list[Correction] = field(default_factory=list)
    human_review_items: list[ReviewItem] = field(default_factory=list)
    processing_plan: list[ProcessingUnit] = field(default_factory=list)
    units_done: list[str] = field(default_factory=list)
    checkpointed_at: str = ""

    # ── counters ──────────────────────────────────────────
    @property
    def total_issues(self) -> int:
        return len(self.issues)

    @property
    def total_corrections(self) -> int:
        return len(self.corrections)

    @property
    def total_human_reviews(self) -> int:
        return len(self.human_review_items)

    @property
    def units_pending(self) -> list[ProcessingUnit]:
        done_ids = set(self.units_done)
        return [u for u in self.processing_plan if u.unit_id not in done_ids]

    # ── serialization ──────────────────────────────────────
    def to_dict(self) -> dict:
        d = asdict(self)
        # GlossaryEntry values need to be serialized from dataclass
        d["glossary"] = {k: asdict(v) for k, v in self.glossary.items()}
        return d

    def save(self, path: Path) -> None:
        self.checkpointed_at = datetime.now().isoformat()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2))

    @classmethod
    def load(cls, path: Path) -> "AgentState":
        data = json.loads(path.read_text())
        glossary = {
            k: GlossaryEntry(**v) for k, v in data.pop("glossary", {}).items()
        }
        issues = [Issue(**i) for i in data.pop("issues", [])]
        corrections = [Correction(**c) for c in data.pop("corrections", [])]
        human_review_items = [ReviewItem(**r) for r in data.pop("human_review_items", [])]
        processing_plan = [ProcessingUnit(**u) for u in data.pop("processing_plan", [])]
        state = cls(**data)
        state.glossary = glossary
        state.issues = issues
        state.corrections = corrections
        state.human_review_items = human_review_items
        state.processing_plan = processing_plan
        return state

    # ── glossary helpers ───────────────────────────────────
    def add_or_update_glossary(
        self,
        term_en: str,
        term_zh: str,
        note: str = "",
        source_section: str = "",
    ) -> dict[str, Any]:
        existing = self.glossary.get(term_en)
        if existing:
            prev = asdict(existing)
            existing.term_zh = term_zh
            if note:
                existing.note = note
            existing.usage_count += 1
            return {"status": "updated", "previous": prev}
        else:
            self.glossary[term_en] = GlossaryEntry(
                term_en=term_en,
                term_zh=term_zh,
                note=note,
                source_section=source_section,
                usage_count=1,
            )
            return {"status": "added", "previous": None}

    def get_glossary_markdown(self) -> str:
        if not self.glossary:
            return "（术语表为空）"
        lines = ["| 英文 | 中文 | 说明 |", "|------|------|------|"]
        for entry in sorted(self.glossary.values(), key=lambda e: e.term_en):
            note = entry.note or ""
            lines.append(f"| {entry.term_en} | {entry.term_zh} | {note} |")
        return "\n".join(lines)

    def check_term(self, term_en: str) -> dict[str, Any]:
        entry = self.glossary.get(term_en)
        if entry:
            return {
                "known_translation": entry.term_zh,
                "usage_count": entry.usage_count,
                "note": entry.note,
            }
        # 模糊匹配（大小写不敏感）
        lower = term_en.lower()
        for k, v in self.glossary.items():
            if k.lower() == lower:
                return {
                    "known_translation": v.term_zh,
                    "usage_count": v.usage_count,
                    "note": v.note,
                }
        return {"known_translation": None, "usage_count": 0, "note": ""}

    # ── issue helpers ──────────────────────────────────────
    def add_issue(self, section_num: str, issue_type: str, description: str, severity: str) -> str:
        issue_id = f"issue_{len(self.issues) + 1:03d}"
        self.issues.append(Issue(issue_id, section_num, issue_type, description, severity))
        return issue_id

    def add_correction(self, section_num: str, original_zh: str, corrected_zh: str, reason: str) -> str:
        cid = f"correction_{len(self.corrections) + 1:03d}"
        self.corrections.append(Correction(cid, section_num, original_zh, corrected_zh, reason))
        return cid

    def add_review_item(self, section_num: str, question: str, context: str, options: list[str]) -> str:
        rid = f"review_{len(self.human_review_items) + 1:03d}"
        self.human_review_items.append(ReviewItem(rid, section_num, question, context, options))
        return rid

    def mark_unit_done(self, unit_id: str, summary: str) -> int:
        if unit_id not in self.units_done:
            self.units_done.append(unit_id)
        for u in self.processing_plan:
            if u.unit_id == unit_id:
                u.done = True
                u.summary = summary
                break
        return len(self.units_pending)


def make_session_id(guide: str) -> str:
    return f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{guide}"


def load_glossary_from_md(md_path: Path) -> dict[str, GlossaryEntry]:
    """从 GLOSSARY.md 加载现有术语表。"""
    if not md_path.exists():
        return {}
    entries: dict[str, GlossaryEntry] = {}
    in_table = False
    for line in md_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("| 英文"):
            in_table = True
            continue
        if line.startswith("|---"):
            continue
        if in_table and line.startswith("|"):
            parts = [p.strip() for p in line.strip("|").split("|")]
            if len(parts) >= 2:
                term_en = parts[0].strip()
                term_zh = parts[1].strip()
                note = parts[2].strip() if len(parts) > 2 else ""
                if term_en:
                    entries[term_en] = GlossaryEntry(
                        term_en=term_en,
                        term_zh=term_zh,
                        note=note,
                    )
    return entries


def save_glossary_to_md(entries: dict[str, GlossaryEntry], md_path: Path) -> None:
    """将术语表写回 GLOSSARY.md（保留文件头部注释）。"""
    header = "# 术语对照表\n\n"
    lines = [header, "| 英文 | 中文 | 说明 |\n", "|------|------|------|\n"]
    for entry in sorted(entries.values(), key=lambda e: e.term_en):
        note = entry.note or ""
        lines.append(f"| {entry.term_en} | {entry.term_zh} | {note} |\n")
    md_path.write_text("".join(lines), encoding="utf-8")
