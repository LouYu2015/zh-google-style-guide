"""
tests/test_state.py - Unit tests for state.py

Tests cover:
- AgentState save/load round-trip
- Glossary file parsing and writing
- glossary_as_markdown output
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from state import AgentState, Chunk, Issue, HumanReviewItem


# ──────────────────────────────────────────────
# Save / load round-trip
# ──────────────────────────────────────────────

def _make_state() -> AgentState:
    return AgentState(
        guide="java",
        session_id="20990101_000000_java",
        chunks=[
            Chunk(chunk_id="chunk_01", sections=["1", "1.1"], reason="small"),
            Chunk(chunk_id="chunk_02", sections=["2"], reason="medium", status="done", notes="some notes"),
        ],
        glossary={
            "Override": {"term_zh": "重写", "note": "优先于\"覆盖\""},
            "Javadoc": {"term_zh": "Javadoc", "note": "保留英文"},
        },
        issues=[
            Issue(chunk_id="chunk_01", section="1.1", severity="low", description="typo"),
        ],
        human_review_items=[
            HumanReviewItem(chunk_id="chunk_01", section="1.2", description="ambiguous"),
        ],
        dry_run=False,
        started_at="2099-01-01T00:00:00",
    )


def test_save_load_round_trip(tmp_path):
    state = _make_state()
    state.save(tmp_path)

    assert (tmp_path / "state.json").exists()

    loaded = AgentState.load(tmp_path)
    assert loaded.guide == "java"
    assert loaded.session_id == "20990101_000000_java"
    assert len(loaded.chunks) == 2
    assert loaded.chunks[0].chunk_id == "chunk_01"
    assert loaded.chunks[1].status == "done"
    assert loaded.chunks[1].notes == "some notes"
    assert loaded.glossary["Override"]["term_zh"] == "重写"
    assert len(loaded.issues) == 1
    assert loaded.issues[0].severity == "low"
    assert len(loaded.human_review_items) == 1


def test_save_creates_dir(tmp_path):
    new_dir = tmp_path / "nested" / "session"
    state = _make_state()
    state.save(new_dir)
    assert (new_dir / "state.json").exists()


def test_load_missing_fields(tmp_path):
    # Minimal state.json missing optional fields
    minimal = {
        "guide": "python",
        "session_id": "test",
        "dry_run": True,
        "started_at": "",
        "chunks": [],
        "glossary": {},
        "issues": [],
        "human_review_items": [],
    }
    (tmp_path / "state.json").write_text(json.dumps(minimal), encoding="utf-8")
    loaded = AgentState.load(tmp_path)
    assert loaded.guide == "python"
    assert loaded.dry_run is True
    assert loaded.chunks == []


# ──────────────────────────────────────────────
# Glossary file round-trip
# ──────────────────────────────────────────────

_GLOSSARY_CONTENT = """\
# 术语对照表

| 英文 | 中文 | 说明 |
|------|------|------|
| Javadoc | Javadoc | 保留英文 |
| Override | 重写 | 优先于"覆盖" |
| Style Guide | 风格指南 | 不译为"代码规范" |
"""


def test_from_glossary_file(tmp_path):
    gpath = tmp_path / "GLOSSARY.md"
    gpath.write_text(_GLOSSARY_CONTENT, encoding="utf-8")
    state = AgentState.from_glossary_file(gpath, "java", "test", False, "")
    assert "Javadoc" in state.glossary
    assert state.glossary["Javadoc"]["term_zh"] == "Javadoc"
    assert "Override" in state.glossary
    assert state.glossary["Override"]["term_zh"] == "重写"
    assert "Style Guide" in state.glossary
    assert state.glossary["Style Guide"]["note"] == '不译为"代码规范"'


def test_save_glossary(tmp_path):
    state = _make_state()
    gpath = tmp_path / "GLOSSARY.md"
    state.save_glossary(gpath)
    content = gpath.read_text(encoding="utf-8")
    assert "# 术语对照表" in content
    assert "Override" in content
    assert "重写" in content
    assert "Javadoc" in content


def test_glossary_as_markdown():
    state = _make_state()
    md = state.glossary_as_markdown()
    assert "| 英文 | 中文 | 说明 |" in md
    assert "Override" in md
    assert "重写" in md
    assert "Javadoc" in md


# ──────────────────────────────────────────────
# Glossary parse empty file
# ──────────────────────────────────────────────

def test_from_glossary_missing_file(tmp_path):
    gpath = tmp_path / "NONEXISTENT.md"
    state = AgentState.from_glossary_file(gpath, "java", "test", False, "")
    assert state.glossary == {}
