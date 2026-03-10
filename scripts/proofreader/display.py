"""
display.py - Terminal UI for the proofreader.

Design: Rich console for structured output (headers, progress, summaries).
        sys.stdout.write for streaming model text (avoids Rich Live conflicts).
"""
from __future__ import annotations

import sys
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich import box


class Display:
    def __init__(self) -> None:
        self.console = Console()

    # ──────────────────────────────────────────────
    # Session-level
    # ──────────────────────────────────────────────

    def show_header(self, guide: str, session_id: str, mode: str) -> None:
        self.console.print()
        self.console.print(Panel(
            f"[bold]指南:[/bold] {guide}  |  "
            f"[bold]会话:[/bold] {session_id}  |  "
            f"[bold]模式:[/bold] {mode}",
            title="[bold cyan]Google 风格指南校对助手[/bold cyan]",
            border_style="cyan",
        ))

    def show_progress(self, done: int, total: int) -> None:
        pct = int(done / total * 100) if total > 0 else 0
        filled = pct // 5
        bar = "█" * filled + "░" * (20 - filled)
        self.console.print(
            f"[blue]进度[/blue] [{bar}] [green]{done}[/green]/{total} ([cyan]{pct}%[/cyan])"
        )

    def show_final_summary(self, state) -> None:
        done = sum(1 for c in state.chunks if c.status == "done")
        total = len(state.chunks)
        total_corrections = sum(c.corrections_count for c in state.chunks)
        total_issues = len(state.issues)
        new_terms = len(state.glossary)

        table = Table(title=f"校对完成 — {state.guide}", box=box.ROUNDED, border_style="green")
        table.add_column("项目", style="cyan", min_width=12)
        table.add_column("数值", style="green", justify="right")
        table.add_row("处理块数", f"{done}/{total}")
        table.add_row("修正数", str(total_corrections))
        table.add_row("发现问题", str(total_issues))
        table.add_row("术语条目", str(new_terms))
        table.add_row("待人工审核", str(len(state.human_review_items)))
        self.console.print()
        self.console.print(table)

    # ──────────────────────────────────────────────
    # Per-chunk
    # ──────────────────────────────────────────────

    def show_chunk_start(self, chunk) -> None:
        sections_str = ", ".join(chunk.sections[:6])
        if len(chunk.sections) > 6:
            sections_str += f"…(+{len(chunk.sections)-6})"
        self.console.print()
        self.console.print(Rule(
            f"[bold blue]{chunk.chunk_id}[/bold blue] — 章节 {sections_str}",
            style="blue",
        ))
        if chunk.reason:
            self.console.print(f"  [dim]{chunk.reason}[/dim]")
        self.console.print()

    def show_thinking_start(self) -> None:
        self.console.print("[dim]🤔 正在思考…[/dim]")

    def show_thinking_end(self) -> None:
        self.console.print("[dim]── 思考完毕，开始输出 ──[/dim]")
        self.console.print()

    def stream_text(self, text: str) -> None:
        """Write streaming model text directly to stdout (no Rich markup processing)."""
        sys.stdout.write(text)
        sys.stdout.flush()

    def show_chunk_done(self, chunk, corrections_count: int) -> None:
        # Ensure we're on a new line after streaming
        sys.stdout.write("\n")
        sys.stdout.flush()
        self.console.print(
            f"[green]✓ {chunk.chunk_id} 完成[/green] — "
            f"{corrections_count} 处修正，{chunk.issues_count} 个问题"
        )

    def show_chunk_skipped(self, chunk) -> None:
        self.console.print(f"[yellow]⏭ {chunk.chunk_id} 跳过[/yellow] — 无译文可校对")

    def show_error(self, message: str) -> None:
        self.console.print(f"\n[bold red]错误:[/bold red] {message}")

    def show_info(self, message: str) -> None:
        self.console.print(f"[dim]{message}[/dim]")

    def show_resume_hint(self, command: str) -> None:
        self.console.print()
        self.console.print(Panel(
            f"[yellow]已保存进度，下次可用以下命令继续：[/yellow]\n\n  [bold]{command}[/bold]",
            title="已中断",
            border_style="yellow",
        ))
