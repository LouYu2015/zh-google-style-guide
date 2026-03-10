"""
state.py - Session state dataclasses and JSON persistence.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class SectionInfo:
    section_num: str
    title: str
    level: int
    token_estimate: int
    has_translation: bool


@dataclass
class Chunk:
    chunk_id: str
    sections: list
    reason: str
    status: str = "pending"       # pending / processing / done / skipped
    notes: str = ""               # memory for the next chunk
    issues_count: int = 0
    corrections_count: int = 0


@dataclass
class Issue:
    chunk_id: str
    section: str
    severity: str                 # high / medium / low
    description: str


@dataclass
class HumanReviewItem:
    chunk_id: str
    section: str
    description: str


@dataclass
class AgentState:
    guide: str
    session_id: str
    chunks: list
    glossary: dict                # term_en -> {"term_zh": str, "note": str}
    issues: list
    human_review_items: list
    dry_run: bool
    started_at: str

    # ──────────────────────────────────────────────
    # Persistence
    # ──────────────────────────────────────────────

    def save(self, debug_dir: Path) -> None:
        debug_dir.mkdir(parents=True, exist_ok=True)
        state_dict = {
            "guide": self.guide,
            "session_id": self.session_id,
            "dry_run": self.dry_run,
            "started_at": self.started_at,
            "chunks": [asdict(c) for c in self.chunks],
            "glossary": self.glossary,
            "issues": [asdict(i) for i in self.issues],
            "human_review_items": [asdict(h) for h in self.human_review_items],
        }
        (debug_dir / "state.json").write_text(
            json.dumps(state_dict, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @classmethod
    def load(cls, debug_dir: Path) -> "AgentState":
        data = json.loads((debug_dir / "state.json").read_text(encoding="utf-8"))
        return cls(
            guide=data["guide"],
            session_id=data["session_id"],
            dry_run=data.get("dry_run", False),
            started_at=data.get("started_at", ""),
            chunks=[Chunk(**c) for c in data["chunks"]],
            glossary=data.get("glossary", {}),
            issues=[Issue(**i) for i in data.get("issues", [])],
            human_review_items=[
                HumanReviewItem(**h) for h in data.get("human_review_items", [])
            ],
        )

    # ──────────────────────────────────────────────
    # Glossary helpers
    # ──────────────────────────────────────────────

    @classmethod
    def from_glossary_file(
        cls,
        glossary_path: Path,
        guide: str,
        session_id: str,
        dry_run: bool,
        started_at: str,
    ) -> "AgentState":
        """Create a new AgentState seeded from translation/GLOSSARY.md."""
        glossary: dict = {}
        if glossary_path.exists():
            for line in glossary_path.read_text(encoding="utf-8").splitlines():
                if (
                    line.startswith("|")
                    and not line.startswith("| 英文")
                    and not line.startswith("|---")
                    and not line.startswith("| English")
                ):
                    parts = [p.strip() for p in line.strip("|").split("|")]
                    if len(parts) >= 2 and parts[0]:
                        term_en = parts[0]
                        term_zh = parts[1] if len(parts) > 1 else ""
                        note = parts[2] if len(parts) > 2 else ""
                        glossary[term_en] = {"term_zh": term_zh, "note": note}
        return cls(
            guide=guide,
            session_id=session_id,
            chunks=[],
            glossary=glossary,
            issues=[],
            human_review_items=[],
            dry_run=dry_run,
            started_at=started_at,
        )

    def save_glossary(self, glossary_path: Path) -> None:
        """Write the current glossary back to translation/GLOSSARY.md."""
        lines = [
            "# 术语对照表",
            "",
            "| 英文 | 中文 | 说明 |",
            "|------|------|------|",
        ]
        for term_en, entry in sorted(self.glossary.items(), key=lambda x: x[0].lower()):
            term_zh = entry.get("term_zh", "")
            note = entry.get("note", "")
            lines.append(f"| {term_en} | {term_zh} | {note} |")
        lines.append("")
        glossary_path.write_text("\n".join(lines), encoding="utf-8")

    def glossary_as_markdown(self) -> str:
        """Return the glossary as a Markdown table string."""
        lines = ["| 英文 | 中文 | 说明 |", "|------|------|------|"]
        for term_en, entry in sorted(self.glossary.items(), key=lambda x: x[0].lower()):
            term_zh = entry.get("term_zh", "")
            note = entry.get("note", "")
            lines.append(f"| {term_en} | {term_zh} | {note} |")
        return "\n".join(lines)
