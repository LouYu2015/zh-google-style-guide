"""
display.py - Rich 终端 UI

实时显示：
- 总体进度条
- 当前处理状态（单元、章节、工具调用）
- 流式模型输出
- 最终汇总表
"""

from contextlib import contextmanager
from typing import Generator

from rich.columns import Columns
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text

console = Console()


class ProofreadingDisplay:
    """管理整个校对会话的终端显示。"""

    def __init__(self, guide: str, session_id: str, stream: bool = True):
        self.guide = guide
        self.session_id = session_id
        self.stream = stream

        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=30),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console,
        )
        self._task_id: TaskID | None = None
        self._live: Live | None = None

        # 状态文本（供 Live 渲染）
        self._status_lines: list[str] = []
        self._stream_buf: list[str] = []
        self._current_unit = ""
        self._current_tool = ""
        self._stats = {"issues": 0, "corrections": 0, "reviews": 0}

    # ── 启动 / 停止 ────────────────────────────────────────

    def start(self, total_units: int) -> None:
        self._task_id = self._progress.add_task(
            f"[{self.guide.upper()}] 校对进度",
            total=total_units,
        )
        self._live = Live(
            self._render(),
            console=console,
            refresh_per_second=5,
            transient=False,
        )
        self._live.__enter__()

    def stop(self) -> None:
        if self._live:
            self._live.__exit__(None, None, None)

    # ── 状态更新 ───────────────────────────────────────────

    def update_unit(self, unit_id: str, sections: list[str]) -> None:
        self._current_unit = f"{unit_id}（章节 {', '.join(sections)}）"
        self._stream_buf = []
        self._refresh()

    def update_tool_call(self, tool_name: str, inputs: dict) -> None:
        inputs_preview = ", ".join(f"{k}={repr(v)[:30]}" for k, v in inputs.items())
        self._current_tool = f"{tool_name}({inputs_preview})"
        self._refresh()

    def update_stats(self, issues: int, corrections: int, reviews: int) -> None:
        self._stats = {"issues": issues, "corrections": corrections, "reviews": reviews}
        self._refresh()

    def advance_progress(self) -> None:
        if self._task_id is not None:
            self._progress.advance(self._task_id)
        self._refresh()

    # ── 流式输出 ───────────────────────────────────────────

    def stream_token(self, token: str) -> None:
        """接收单个流式 token 并更新显示。"""
        if not self.stream:
            return
        self._stream_buf.append(token)
        # 避免 buffer 过大
        if len(self._stream_buf) > 2000:
            self._stream_buf = self._stream_buf[-1500:]
        self._refresh()

    def print_tool_result(self, tool_name: str, result: str) -> None:
        """在 Live 上下文之外打印工具调用结果（不常用，仅调试）。"""
        console.print(f"  [dim]→ {tool_name}: {result[:100]}[/dim]")

    # ── 渲染 ────────────────────────────────────────────────

    def _render(self):
        # 上半部分：进度 + 状态
        stats_text = (
            f"[green]问题: {self._stats['issues']}[/green]  "
            f"[yellow]修正: {self._stats['corrections']}[/yellow]  "
            f"[cyan]人工审核: {self._stats['reviews']}[/cyan]"
        )
        status_text = (
            f"[bold]当前单元:[/bold] {self._current_unit or '（准备中）'}\n"
            f"[bold]工具调用:[/bold] [dim]{self._current_tool or '—'}[/dim]\n"
            f"{stats_text}"
        )
        status_panel = Panel(
            status_text,
            title=f"[bold blue]会话: {self.session_id}[/bold blue]",
            border_style="blue",
        )

        # 下半部分：流式输出
        stream_text = "".join(self._stream_buf)
        # 只显示最后 30 行
        stream_lines = stream_text.splitlines()[-30:]
        stream_content = "\n".join(stream_lines) if stream_lines else "[dim]（等待模型响应）[/dim]"
        stream_panel = Panel(
            stream_content,
            title="[bold]模型输出[/bold]",
            border_style="dim",
        )

        from rich.console import Group
        return Group(
            self._progress,
            status_panel,
            stream_panel,
        )

    def _refresh(self) -> None:
        if self._live:
            self._live.update(self._render())

    # ── 最终报告显示 ────────────────────────────────────────

    def print_final_summary(self, state, report_path, dry_run: bool) -> None:
        """在 Live 结束后打印最终汇总表。"""
        from rich.rule import Rule

        console.print()
        console.print(Rule(f"[bold green]校对完成 — {self.guide.upper()} 指南[/bold green]"))
        console.print()

        table = Table(title="校对汇总", show_header=True, header_style="bold magenta")
        table.add_column("指标", style="bold")
        table.add_column("数值", justify="right")

        applied = sum(1 for c in state.corrections if c.applied)
        table.add_row("处理单元", f"{len(state.units_done)}/{len(state.processing_plan)}")
        table.add_row("发现问题", str(state.total_issues))
        table.add_row(
            "  └ 高优先级",
            str(sum(1 for i in state.issues if i.severity == "high")),
        )
        table.add_row("修正记录", str(state.total_corrections))
        table.add_row("  └ 已写入文件", "0（dry-run）" if dry_run else str(applied))
        table.add_row("待人工审核", str(state.total_human_reviews))

        console.print(table)
        console.print()
        console.print(f"[bold]报告已保存至:[/bold] {report_path}")
        console.print()

        if state.human_review_items:
            console.print(Panel(
                "\n".join(
                    f"[{item.review_id}] §{item.section_num}: {item.question}"
                    for item in state.human_review_items
                ),
                title="[bold yellow]需要人工审核的问题[/bold yellow]",
                border_style="yellow",
            ))

    # ── 工具方法 ────────────────────────────────────────────

    @staticmethod
    def print_banner(guide: str, session_id: str, dry_run: bool) -> None:
        mode = "[yellow]DRY RUN（仅报告，不修改文件）[/yellow]" if dry_run else "[green]正常模式（修正将写入文件）[/green]"
        console.print(Panel(
            f"[bold blue]Google Style Guide 翻译校对智能体[/bold blue]\n"
            f"指南: [bold]{guide.upper()}[/bold]  |  会话: [dim]{session_id}[/dim]\n"
            f"模式: {mode}",
            border_style="blue",
        ))

    @staticmethod
    def print_planning_result(units) -> None:
        table = Table(title="处理计划", show_header=True, header_style="bold cyan")
        table.add_column("单元", style="bold")
        table.add_column("章节")
        table.add_column("分组原因", max_width=50)

        for unit in units:
            table.add_row(
                unit.unit_id,
                ", ".join(unit.sections),
                unit.reason,
            )
        console.print(table)
        console.print()

    @staticmethod
    def print_warning(msg: str) -> None:
        console.print(f"[bold yellow]⚠  {msg}[/bold yellow]")

    @staticmethod
    def print_error(msg: str) -> None:
        console.print(f"[bold red]✗ {msg}[/bold red]")

    @staticmethod
    def print_info(msg: str) -> None:
        console.print(f"[dim]{msg}[/dim]")
