"""
Workflow summary and token usage tracking (same structure as manim-generator).
Uses Rich for styled console output (rules, tables).
"""

from dataclasses import dataclass
from typing import Any

from rich.console import Console
from rich.table import Table


@dataclass
class WorkflowStats:
    """Stats collected during run_manim_workflow."""
    total_time_seconds: float = 0.0
    review_cycles_completed: int = 0
    execution_count: int = 0
    successful_executions: int = 0
    initial_success: bool = False
    final_working_code: bool = False
    final_video_path: str = ""


class TokenUsageTracker:
    """Tracks token usage and costs across workflow steps (Gemini)."""

    def __init__(self) -> None:
        self.token_usage_tracking: dict[str, Any] = {
            "steps": [],
            "total_tokens": 0,
            "total_cost": 0.0,
            "total_llm_time": 0.0,
            "total_reasoning_tokens": 0,
            "total_answer_tokens": 0,
        }

    def add_step(self, step_name: str, model: str, usage_info: dict[str, Any]) -> None:
        """Add a step's usage information."""
        step_info: dict[str, Any] = {
            "step": step_name,
            "model": model,
            **usage_info,
        }
        step_info.setdefault("reasoning_tokens", 0)
        step_info.setdefault("answer_tokens", step_info.get("completion_tokens", 0))
        self.token_usage_tracking["steps"].append(step_info)
        self.token_usage_tracking["total_tokens"] += usage_info.get("total_tokens", 0)
        self.token_usage_tracking["total_cost"] += usage_info.get("cost", 0.0)
        self.token_usage_tracking["total_llm_time"] += usage_info.get("llm_time", 0.0)
        self.token_usage_tracking["total_reasoning_tokens"] += step_info.get("reasoning_tokens", 0)
        self.token_usage_tracking["total_answer_tokens"] += step_info.get("answer_tokens", 0)

    def get_tracking_data(self) -> dict[str, Any]:
        return self.token_usage_tracking


def format_duration(seconds: float) -> str:
    """Format duration in seconds to human-readable format."""
    if seconds < 60:
        return f"{seconds:.1f} seconds"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        remaining_seconds = seconds % 60
        return f"{minutes}m {remaining_seconds:.1f}s"
    else:
        hours = int(seconds // 3600)
        remaining_minutes = int((seconds % 3600) // 60)
        remaining_seconds = seconds % 60
        return f"{hours}h {remaining_minutes}m {remaining_seconds:.1f}s"


def display_workflow_summary(console: Console, stats: WorkflowStats) -> None:
    """Print workflow summary (same style as manim-generator)."""
    console.rule("[bold cyan]Workflow Summary", style="cyan")
    console.print(
        f"[bold cyan]Total workflow time:[/bold cyan] {format_duration(stats.total_time_seconds)}"
    )
    console.print(f"[cyan]Review cycles completed:[/cyan] {stats.review_cycles_completed}")
    console.print(f"[cyan]Total executions:[/cyan] {stats.execution_count}")
    console.print(f"[cyan]Successful executions:[/cyan] {stats.successful_executions}")
    console.print(f"[cyan]Initial success:[/cyan] {'✓' if stats.initial_success else '✗'}")
    console.print(
        f"[cyan]Final working code:[/cyan] {'✓' if stats.final_working_code else '✗'}"
    )
    if stats.final_video_path:
        console.print(f"[cyan]Final video:[/cyan] {stats.final_video_path}")


def get_usage_totals(token_usage_tracking: dict[str, Any]) -> tuple[int, int, int, int]:
    """Total prompt, completion, reasoning, and answer tokens."""
    steps = token_usage_tracking.get("steps", [])
    total_prompt = sum(s.get("prompt_tokens", 0) or 0 for s in steps)
    total_completion = sum(s.get("completion_tokens", 0) or 0 for s in steps)
    total_reasoning = sum(s.get("reasoning_tokens", 0) or 0 for s in steps)
    total_answer = sum(s.get("answer_tokens", 0) or 0 for s in steps)
    return total_prompt, total_completion, total_reasoning, total_answer


def display_usage_summary(console: Console, token_usage_tracking: dict[str, Any]) -> None:
    """Print token usage & cost table (same as manim-generator)."""
    steps = token_usage_tracking.get("steps", [])
    if not steps:
        return

    table = Table(
        title="Token Usage & Cost Summary",
        expand=True,
        show_lines=False,
    )
    table.add_column("Step", style="cyan", min_width=24, no_wrap=False)
    table.add_column("Model", style="green", min_width=36, no_wrap=False)
    table.add_column("Prompt Tokens", justify="right", style="blue", min_width=14)
    table.add_column("Completion Tokens", justify="right", style="blue", min_width=16)
    table.add_column("Reasoning Tokens", justify="right", style="blue", min_width=16)
    table.add_column("Answer Tokens", justify="right", style="blue", min_width=13)
    table.add_column("Total Tokens", justify="right", style="blue", min_width=12)
    table.add_column("Cost (USD)", justify="right", style="red", min_width=10)

    (
        total_prompt_tokens,
        total_completion_tokens,
        total_reasoning_tokens,
        total_answer_tokens,
    ) = get_usage_totals(token_usage_tracking)

    for step in steps:
        table.add_row(
            step.get("step", ""),
            str(step.get("model", "")),
            str(step.get("prompt_tokens", 0)),
            str(step.get("completion_tokens", 0)),
            str(step.get("reasoning_tokens", 0)),
            str(step.get("answer_tokens", 0)),
            str(step.get("total_tokens", 0)),
            f"${step.get('cost', 0.0):.6f}",
        )

    table.add_section()
    table.add_row(
        "[bold]TOTAL",
        "",
        f"[bold]{total_prompt_tokens}",
        f"[bold]{total_completion_tokens}",
        f"[bold]{total_reasoning_tokens}",
        f"[bold]{total_answer_tokens}",
        f"[bold]{token_usage_tracking['total_tokens']}",
        f"[bold]${token_usage_tracking['total_cost']:.6f}",
    )

    console.print(table)


def extract_gemini_usage(response: Any) -> dict[str, Any]:
    """
    Extract usage from a google.generativeai GenerateContentResponse.
    Returns dict with prompt_tokens, completion_tokens, total_tokens, cost (estimate).
    """
    out: dict[str, Any] = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "reasoning_tokens": 0,
        "answer_tokens": 0,
        "cost": 0.0,
        "llm_time": 0.0,
    }
    try:
        um = getattr(response, "usage_metadata", None)
        if um is None:
            return out
        out["prompt_tokens"] = getattr(um, "prompt_token_count", 0) or 0
        out["completion_tokens"] = getattr(um, "candidates_token_count", 0) or 0
        out["total_tokens"] = getattr(um, "total_token_count", 0) or (out["prompt_tokens"] + out["completion_tokens"])
        out["answer_tokens"] = out["completion_tokens"]
        # Rough Gemini 2.5 Flash cost (input $0.075/1M, output $0.30/1M)
        out["cost"] = (out["prompt_tokens"] * 0.075 / 1e6) + (out["completion_tokens"] * 0.30 / 1e6)
    except Exception:
        pass
    return out
