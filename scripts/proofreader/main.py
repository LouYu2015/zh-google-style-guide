#!/usr/bin/env python3
"""
main.py - CLI entry point for the AI proofreading system.

Usage:
  python scripts/proofreader/main.py java              # proofread and apply corrections
  python scripts/proofreader/main.py java --dry-run    # report only, don't modify files
  python scripts/proofreader/main.py java --resume     # resume from last interrupted session

The workflow:
  Phase 1: Claude analyzes section structure and plans chunks
  Phase 2: For each chunk, Claude reads original + translation, outputs corrections + notes
           Corrections are written back to docs/guides/{language}.md
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

# Ensure scripts/proofreader is on sys.path for intra-package imports
_HERE = Path(__file__).parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import anthropic

import config as cfg
import reader as reader_mod
from chunker import plan_chunks
from display import Display
from logger import DebugLogger
from reviewer import review_chunk
from state import AgentState, HumanReviewItem, Issue

# ──────────────────────────────────────────────
# Supported guides
# ──────────────────────────────────────────────

SUPPORTED_GUIDES = list(reader_mod.ORIGINAL_GUIDES.keys())
DEBUG_ROOT = Path(__file__).parent.parent.parent / "debug"
GLOSSARY_PATH = Path(__file__).parent.parent.parent / "translation" / "GLOSSARY.md"


# ──────────────────────────────────────────────
# Resume helper
# ──────────────────────────────────────────────

def _find_latest_session(guide: str) -> Path | None:
    """Find the most recent debug session directory for the given guide."""
    if not DEBUG_ROOT.exists():
        return None
    pattern = re.compile(rf"^proofreader_.*_{re.escape(guide)}$")
    candidates = [
        d for d in DEBUG_ROOT.iterdir()
        if d.is_dir() and pattern.match(d.name) and (d / "state.json").exists()
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda d: d.name)


# ──────────────────────────────────────────────
# Issue / human-review parsing
# ──────────────────────────────────────────────

def _parse_issues(issues_text: str, chunk_id: str) -> list[Issue]:
    issues: list[Issue] = []
    for line in issues_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Pattern: - [section] severity: description
        m = re.match(r"-?\s*\[([^\]]+)\]\s*(high|medium|low)[：:]\s*(.+)", line, re.IGNORECASE)
        if m:
            issues.append(Issue(
                chunk_id=chunk_id,
                section=m.group(1).strip(),
                severity=m.group(2).lower(),
                description=m.group(3).strip(),
            ))
        elif line.startswith("-"):
            # Fallback: treat as low severity
            text = line.lstrip("- ").strip()
            if text:
                issues.append(Issue(
                    chunk_id=chunk_id,
                    section="unknown",
                    severity="low",
                    description=text,
                ))
    return issues


def _parse_human_review(human_review: str, chunk_id: str) -> list[HumanReviewItem]:
    items: list[HumanReviewItem] = []
    for line in human_review.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"\[人工审核\]\s*([^:：]+)[：:]\s*(.+)", line)
        if m:
            items.append(HumanReviewItem(
                chunk_id=chunk_id,
                section=m.group(1).strip(),
                description=m.group(2).strip(),
            ))
        else:
            items.append(HumanReviewItem(
                chunk_id=chunk_id,
                section="unknown",
                description=line,
            ))
    return items


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="AI 翻译校对助手 — 校对 Google 风格指南中文译文"
    )
    parser.add_argument("language", choices=SUPPORTED_GUIDES,
                        help=f"要校对的指南语言 ({', '.join(SUPPORTED_GUIDES)})")
    parser.add_argument("--dry-run", action="store_true",
                        help="只报告问题，不修改译文文件")
    parser.add_argument("--resume", action="store_true",
                        help="从上次中断的会话继续")
    args = parser.parse_args()

    guide = args.language
    dry_run = args.dry_run
    do_resume = args.resume

    # ── API client ──
    api_key = cfg.get_api_key()
    client = anthropic.Anthropic(api_key=api_key)

    display = Display()
    started_at = datetime.now().isoformat()

    # ── Session setup ──
    if do_resume:
        session_dir = _find_latest_session(guide)
        if session_dir is None:
            display.show_error(f"找不到 '{guide}' 的历史会话，请去掉 --resume 重新开始。")
            sys.exit(1)
        state = AgentState.load(session_dir)
        display.show_info(f"恢复会话：{session_dir.name}")
        logger = DebugLogger(state.session_id, guide)
    else:
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S") + f"_{guide}"
        logger = DebugLogger(session_id, guide)
        state = AgentState.from_glossary_file(
            GLOSSARY_PATH, guide, session_id, dry_run, started_at
        )
        logger.write_run_info(guide, cfg.MODEL, dry_run, False, started_at)

        display.show_header(guide, session_id, "dry-run（仅报告）" if dry_run else "自动应用修正")
        display.show_info("正在分析章节结构，规划处理块…")

        sections = reader_mod.list_all_sections(guide)
        if not sections:
            display.show_error(f"未找到指南 '{guide}' 的章节，请检查 styleguide/ 目录。")
            sys.exit(1)

        display.show_info(f"发现 {len(sections)} 个章节，正在调用 Claude 规划分块…")
        chunks = plan_chunks(sections, guide, client, logger)
        state.chunks = chunks
        state.save(logger.session_dir)
        display.show_info(f"分块完成，共 {len(chunks)} 个处理块。")

    mode_str = "dry-run（仅报告）" if dry_run else "自动应用修正"
    display.show_header(guide, state.session_id, mode_str)

    # ── Main loop ──
    pending = [c for c in state.chunks if c.status in ("pending", "processing")]
    total = len(state.chunks)
    done_count = sum(1 for c in state.chunks if c.status == "done")

    if not pending:
        display.show_info("所有处理块已完成。")
    else:
        try:
            for chunk in pending:
                chunk.status = "processing"
                state.save(logger.session_dir)

                # Check if chunk has any translatable sections
                has_any_translation = any(
                    reader_mod.read_translated_section(guide, s) is not None
                    for s in chunk.sections
                )
                if not has_any_translation:
                    chunk.status = "skipped"
                    display.show_chunk_skipped(chunk)
                    state.save(logger.session_dir)
                    done_count += 1
                    display.show_progress(done_count, total)
                    continue

                # Transfer notes from previous chunk (if any)
                if done_count > 0:
                    # Find the last completed chunk's notes
                    for prev_chunk in reversed(state.chunks):
                        if prev_chunk.status == "done" and prev_chunk.notes:
                            chunk.notes = prev_chunk.notes
                            break

                display.show_chunk_start(chunk)

                result = review_chunk(chunk, state, client, display, logger)

                # Apply corrections (unless dry-run)
                corrections_applied = 0
                if not dry_run:
                    for section_num, corrected in result.corrections.items():
                        if corrected.strip():
                            success = reader_mod.apply_correction(guide, section_num, corrected)
                            if success:
                                corrections_applied += 1
                else:
                    corrections_applied = len(result.corrections)

                # Parse and store issues
                new_issues = _parse_issues(result.issues_text, chunk.chunk_id)
                state.issues.extend(new_issues)

                # Parse and store human review items
                new_review = _parse_human_review(result.human_review, chunk.chunk_id)
                state.human_review_items.extend(new_review)

                # Update chunk metadata
                chunk.status = "done"
                chunk.notes = result.notes
                chunk.issues_count = len(new_issues)
                chunk.corrections_count = corrections_applied

                state.save(logger.session_dir)
                logger.write_state(state)

                done_count += 1
                display.show_chunk_done(chunk, corrections_applied)
                display.show_progress(done_count, total)

        except KeyboardInterrupt:
            # Save progress and show resume hint
            state.save(logger.session_dir)
            resume_cmd = f".venv/bin/python scripts/proofreader/main.py {guide} --resume"
            display.show_resume_hint(resume_cmd)
            sys.exit(0)

    # ── Finish ──
    # Update glossary file if we have new terms (from any future glossary expansion)
    state.save_glossary(GLOSSARY_PATH)

    logger.write_report(state)
    display.show_final_summary(state)

    report_path = logger.session_dir / "report.md"
    display.show_info(f"报告已保存：{report_path}")


if __name__ == "__main__":
    main()
