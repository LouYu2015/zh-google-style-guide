#!/usr/bin/env python3
"""
main.py - 翻译校对智能体 CLI 入口

用法:
  python scripts/proofreader/main.py java
  python scripts/proofreader/main.py java --dry-run
  python scripts/proofreader/main.py java --resume
  python scripts/proofreader/main.py java --unit unit_03
  python scripts/proofreader/main.py java --no-stream

两阶段工作流：
  Phase 1 (Planning): 调用 Claude 分析文档结构，生成处理计划
  Phase 2 (Review):   逐单元执行带工具调用的 ReAct 校对循环
"""

import argparse
import sys
from pathlib import Path

# 将 proofreader 目录的父目录加入 sys.path，以便 import 本包
_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE.parent.parent))

import anthropic

from scripts.proofreader.agent import proofread_unit
from scripts.proofreader.chunker import plan_processing_units, validate_plan
from scripts.proofreader.config import get_api_key, MODEL
from scripts.proofreader.display import ProofreadingDisplay, console
from scripts.proofreader.logger import SessionLogger
from scripts.proofreader.reader import (
    SUPPORTED_GUIDES,
    list_all_sections,
    is_placeholder,
    REPO_ROOT,
)
from scripts.proofreader.state import (
    AgentState,
    make_session_id,
    load_glossary_from_md,
    save_glossary_to_md,
)
from scripts.proofreader.tools import ToolExecutor


def find_latest_session(guide: str) -> Path | None:
    """查找最近一次未完成的会话状态文件。"""
    debug_dir = REPO_ROOT / "debug"
    if not debug_dir.exists():
        return None
    candidates = sorted(
        [d for d in debug_dir.iterdir()
         if d.is_dir() and d.name.startswith(f"proofreader_") and guide in d.name],
        reverse=True,
    )
    for d in candidates:
        state_file = d / "state.json"
        if state_file.exists():
            return state_file
    return None


def load_translation_notes(repo_root: Path) -> str:
    """加载翻译注意事项（用于上下文，非必须）。"""
    notes_path = repo_root / "translation" / "NOTES.md"
    if notes_path.exists():
        return notes_path.read_text(encoding="utf-8")
    return ""


def run(args: argparse.Namespace) -> int:
    guide = args.guide
    dry_run: bool = args.dry_run
    resume: bool = args.resume
    unit_filter: str | None = args.unit
    stream: bool = not args.no_stream
    update_glossary_file: bool = not args.no_glossary_update

    # ── 初始化 ──────────────────────────────────────────────
    # 检查是否为占位页
    if is_placeholder(guide):
        console.print(f"[bold red]✗ '{guide}' 指南译文尚未完成（为占位页），无法校对。[/bold red]")
        console.print("请先完成翻译后再运行校对。")
        return 1

    # ── API Key ─────────────────────────────────────────────
    try:
        api_key = get_api_key()
    except RuntimeError as e:
        console.print(f"[bold red]✗ {e}[/bold red]")
        return 1

    client = anthropic.Anthropic(api_key=api_key)

    # ── 恢复或新建会话 ──────────────────────────────────────
    state: AgentState

    if resume:
        state_file = find_latest_session(guide)
        if state_file is None:
            console.print(f"[yellow]未找到 '{guide}' 的未完成会话，将新建会话。[/yellow]")
            resume = False
        else:
            state = AgentState.load(state_file)
            console.print(f"[green]恢复会话: {state.session_id}（已完成 {len(state.units_done)}/{len(state.processing_plan)} 个单元）[/green]")

    if not resume:
        session_id = make_session_id(guide)
        # 从 GLOSSARY.md 加载初始术语表
        glossary_path = REPO_ROOT / "translation" / "GLOSSARY.md"
        glossary = load_glossary_from_md(glossary_path)
        state = AgentState(guide=guide, session_id=session_id, glossary=glossary)

    logger = SessionLogger(state.session_id, REPO_ROOT)
    logger.log_run_info(guide, MODEL, dry_run, {"resume": resume})

    # 初始化 Display
    display = ProofreadingDisplay(guide, state.session_id, stream)
    ProofreadingDisplay.print_banner(guide, state.session_id, dry_run)

    # ── Phase 1: Planning ────────────────────────────────────
    if not state.processing_plan:
        console.print("\n[bold cyan]Phase 1: 分析文档结构，生成处理计划...[/bold cyan]")
        sections = list_all_sections(guide)
        if not sections:
            console.print(f"[bold red]✗ 未找到 '{guide}' 的章节结构。[/bold red]")
            return 1

        console.print(f"  发现 {len(sections)} 个章节，正在请求 Claude 制定处理计划...")
        try:
            units = plan_processing_units(guide, sections, client, MODEL, logger)
        except Exception as e:
            console.print(f"[bold red]✗ 规划阶段失败: {e}[/bold red]")
            return 1

        warnings = validate_plan(units, sections)
        for w in warnings:
            ProofreadingDisplay.print_warning(w)

        state.processing_plan = units
        logger.save_state(state)

        ProofreadingDisplay.print_planning_result(units)
    else:
        console.print(f"\n[green]使用已有处理计划（共 {len(state.processing_plan)} 个单元）[/green]")

    # ── Phase 2: Review ──────────────────────────────────────
    console.print("\n[bold cyan]Phase 2: 开始逐单元校对...[/bold cyan]\n")

    # 过滤处理单元
    units_to_process = [
        u for u in state.processing_plan
        if u.unit_id not in state.units_done
    ]
    if unit_filter:
        units_to_process = [u for u in units_to_process if u.unit_id == unit_filter]
        if not units_to_process:
            console.print(f"[yellow]指定的处理单元 '{unit_filter}' 未找到或已完成。[/yellow]")
            return 0

    executor = ToolExecutor(guide, state, dry_run)
    display.start(len(state.processing_plan))

    try:
        for unit in units_to_process:
            display.update_unit(unit.unit_id, unit.sections)
            unit_dir = logger.get_unit_dir(unit.unit_id, unit.sections)

            try:
                proofread_unit(
                    guide=guide,
                    unit=unit,
                    state=state,
                    client=client,
                    executor=executor,
                    display=display,
                    logger=logger,
                    unit_dir=unit_dir,
                    stream=stream,
                )
            except KeyboardInterrupt:
                raise
            except Exception as e:
                ProofreadingDisplay.print_error(f"处理 {unit.unit_id} 时出错: {e}")
                # 继续处理下一个单元

            # 每个单元完成后保存状态和术语表
            logger.save_state(state)
            if update_glossary_file:
                glossary_path = REPO_ROOT / "translation" / "GLOSSARY.md"
                save_glossary_to_md(state.glossary, glossary_path)

            display.advance_progress()
            display.update_stats(
                state.total_issues,
                state.total_corrections,
                state.total_human_reviews,
            )

    except KeyboardInterrupt:
        display.stop()
        console.print("\n[yellow]用户中断。进度已保存，可使用 --resume 恢复。[/yellow]")
        logger.save_state(state)
        return 130

    display.stop()

    # ── 生成报告 ─────────────────────────────────────────────
    report_path = logger.write_final_report(state, dry_run)
    display.print_final_summary(state, report_path, dry_run)

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Google Style Guide 翻译校对智能体",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/proofreader/main.py java              # 完整校对 Java 指南（修正写入文件）
  python scripts/proofreader/main.py java --dry-run   # 仅报告，不修改文件
  python scripts/proofreader/main.py java --resume    # 恢复上次中断的会话
  python scripts/proofreader/main.py java --unit unit_03  # 只处理第 3 个单元
        """,
    )
    parser.add_argument(
        "guide",
        choices=SUPPORTED_GUIDES,
        metavar="guide",
        help=f"指南名称，可选: {', '.join(SUPPORTED_GUIDES)}",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="不修改任何文件，仅生成报告（默认：修正会写入文件）",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="恢复最近一次中断的会话",
    )
    parser.add_argument(
        "--unit",
        metavar="UNIT_ID",
        help="只处理指定的处理单元（如 unit_03），用于调试",
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="不流式显示模型输出，等待完整响应后再显示",
    )
    parser.add_argument(
        "--no-glossary-update",
        action="store_true",
        help="不修改 translation/GLOSSARY.md（只在内存中更新术语表）",
    )

    args = parser.parse_args()
    sys.exit(run(args))


if __name__ == "__main__":
    main()
