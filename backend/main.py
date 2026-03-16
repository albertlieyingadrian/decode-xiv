from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import arxiv
import google.generativeai as genai
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from queue import Empty, Queue
from dotenv import load_dotenv

from manim_utils import (
    format_previous_reviews,
    format_prompt,
    parse_code_block,
    run_manim_capture_logs,
    extract_scene_class_names,
    calculate_scene_success_rate,
)
from notebook_utils import generate_colab_notebook, save_notebook
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.syntax import Syntax
from workflow_usage import (
    WorkflowStats,
    TokenUsageTracker,
    extract_gemini_usage,
    display_workflow_summary,
    display_usage_summary,
)

load_dotenv(override=True) # Load variables from .env to override parent env

# Manim workflow config (aligned with manim-generator)
MANIM_REVIEW_CYCLES = int(os.environ.get("MANIM_REVIEW_CYCLES", "3"))
MANIM_SCENE_TIMEOUT = int(os.environ.get("MANIM_SCENE_TIMEOUT", "300"))  # seconds
MANIM_LOGS = os.environ.get("MANIM_LOGS", "").lower() in ("1", "true", "yes")  # print execution logs to console
SUCCESS_THRESHOLD = float(os.environ.get("SUCCESS_THRESHOLD", "100"))  # use enhanced (visual) review when success_rate >= this %

# OpenRouter (LiteLLM): when set, workflow uses OpenRouter for init/review/revision (model reasoning + logs like manim-generator)
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openrouter/google/gemini-2.0-flash-001")
USE_OPENROUTER = bool(OPENROUTER_API_KEY.strip())

# Base URL for generated resources (videos, PDFs, notebooks)
# In production (Cloud Run), this should be the public URL of the backend service
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")

# Forcefully remove google application credentials from environment if they exist
# to force the usage of the raw API key instead of gcloud oauth.
if "GOOGLE_APPLICATION_CREDENTIALS" in os.environ:
    del os.environ["GOOGLE_APPLICATION_CREDENTIALS"]

app = FastAPI(title="ArXiv Animator API")

# Setup CORS for the Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the static directory for serving Manim videos
app.mount("/static", StaticFiles(directory="static"), name="static")

# Configure Gemini
# Expects GEMINI_API_KEY to be set in the environment
if "GEMINI_API_KEY" in os.environ and os.environ["GEMINI_API_KEY"]:
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
else:
    print("WARNING: GEMINI_API_KEY environment variable not set or empty in .env.")

class PaperRequest(BaseModel):
    url: str

class PaperResponse(BaseModel):
    title: str
    authors: list[str]
    summary: str
    manim_video_url: str
    three_js_config: str

def extract_arxiv_id(url: str) -> str | None:
    """Extracts the arXiv ID from a given URL."""
    try:
        # Handles https://arxiv.org/abs/1706.03762 or https://arxiv.org/pdf/1706.03762.pdf
        if "arxiv.org/abs/" in url:
            return url.split("arxiv.org/abs/")[1].split("v")[0] # Strip version if present
        elif "arxiv.org/pdf/" in url:
            return url.split("arxiv.org/pdf/")[1].replace(".pdf", "").split("v")[0]
        else:
             # Try assuming the URL is just the ID
             return url
    except Exception:
        return None

def fetch_arxiv_details(arxiv_id: str):
    """Fetches metadata and abstract for a given arXiv ID."""
    client = arxiv.Client()
    search = arxiv.Search(
        id_list=[arxiv_id],
        max_results=1
    )
    try:
        results = list(client.results(search))
        if not results:
            return None
        return results[0]
    except Exception as e:
        print(f"Error fetching arXiv data: {e}")
        return None


def _parse_init_json_response(text: str) -> tuple[str, str]:
    """Parse Gemini JSON response for manim_code and threejs_config. Returns ('', '{}') on failure."""
    try:
        start_idx = text.find("{")
        end_idx = text.rfind("}")
        if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
            return "", "{}"
        json_str = text[start_idx : end_idx + 1]
        json_str = re.sub(r"^\s*//.*$", "", json_str, flags=re.MULTILINE)
        json_str = json_str.strip()
        try:
            result = json.loads(json_str)
        except json.JSONDecodeError:
            try:
                import ast
                result = ast.literal_eval(json_str)
            except Exception:
                return "", "{}"
        manim_code = result.get("manim_code", "")
        threejs_config = json.dumps(result.get("threejs_config", {}))
        return manim_code, threejs_config
    except Exception:
        return "", "{}"


GEMINI_MODEL_NAME = "gemini-2.5-flash"


def _display_execution_status(
    console: Console,
    success: bool,
    combined_logs: str,
    scenes_rendered: str = "1 of 1",
    show_logs: bool = False,
) -> None:
    """Print execution status and optional logs panel (same format as manim-generator)."""
    status_color = "green" if success else "red"
    console.print(
        f"[bold {status_color}]Execution Status: {'Success' if success else 'Failed'}[/bold {status_color}]"
    )
    console.print(
        f"[bold {status_color}]Scenes Rendered: {scenes_rendered}[/bold {status_color}]"
    )
    if show_logs and combined_logs:
        log_title = (
            "[green]Execution Logs[/green]" if success else "[red]Execution Errors[/red]"
        )
        log_style = "green" if success else "red"
        console.print(Panel(combined_logs, title=log_title, border_style=log_style))
    sys.stdout.flush()
    sys.stderr.flush()


def _display_reasoning_panel(
    console: Console,
    reasoning_content: str | None,
    fallback_summary: str | None = None,
) -> None:
    """Show Model Reasoning panel (same as manim-generator). Always show something when console set."""
    text = (reasoning_content or "").strip() or (fallback_summary or "").strip()
    if text:
        console.print(
            Panel(
                text,
                title="[yellow]Model Reasoning[/yellow]",
                border_style="yellow",
            )
        )
        sys.stdout.flush()


def _print_model_step(console: Console, step_label: str, model: str) -> None:
    """Print persistent lines showing which model is used for this LLM step (visible in terminal and .txt logs)."""
    console.print(f"[cyan]Model:[/cyan] [bold]{model}[/bold]")
    console.print(f"[bold green]{step_label} [{model}][/bold green]")
    sys.stdout.flush()


def print_code_with_syntax(code: str, console: Console, title: str = "Code") -> None:
    """Print code with syntax highlighting in a panel (same as manim-generator)."""
    syntax = Syntax(code, "python", theme="monokai", line_numbers=True)
    console.print(Panel(syntax, title=title, border_style="green"))
    sys.stdout.flush()


def print_request_summary(console: Console, usage_info: dict) -> None:
    """Print one-line token/cost summary for a request (same as manim-generator)."""
    rt = usage_info.get("reasoning_tokens", 0) or 0
    at = usage_info.get("answer_tokens", usage_info.get("completion_tokens", 0)) or 0
    summary = (
        f"Request completed in {usage_info.get('llm_time', 0):.2f} seconds | "
        f"Input Tokens: {usage_info.get('prompt_tokens', 0)} | "
        f"Output Tokens: {usage_info.get('completion_tokens', 0)} "
        f"(reasoning: {rt}, answer: {at}) | "
        f"Cost: ${usage_info.get('cost', 0):.6f}"
    )
    console.print(f"[dim italic]{summary}[/dim italic]")
    sys.stdout.flush()


def _generate_initial_with_openrouter(
    paper_summary: str,
    paper_title: str,
    usage_tracker: TokenUsageTracker | None,
    step_name: str,
    console: Console | None,
) -> tuple[str, str]:
    """Generate initial Manim + Three.js via OpenRouter (LiteLLM); show reasoning/code/summary when console set."""
    from llm_openrouter import get_completion

    prompt = format_prompt("init_prompt", {"paper_title": paper_title, "paper_summary": paper_summary})
    messages = [{"role": "user", "content": prompt}]
    if console:
        _print_model_step(console, "Generating initial code", OPENROUTER_MODEL)
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold green]{task.description}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(
                f"Generating initial code [{OPENROUTER_MODEL}]",
                total=None,
            )
            content, usage_info, reasoning_content = get_completion(
                OPENROUTER_MODEL, messages, temperature=None, timeout=120
            )
            progress.update(task, completed=True)
        if usage_tracker:
            usage_tracker.add_step(step_name, OPENROUTER_MODEL, usage_info)
        manim_code, threejs_config = _parse_init_json_response(content)
        _display_reasoning_panel(
            console,
            reasoning_content,
            fallback_summary="Generate Manim script and Three.js config from paper title and abstract.",
        )
        if manim_code.strip():
            print_code_with_syntax(manim_code, console, "Generated Initial Manim Code")
        print_request_summary(console, usage_info)
        return manim_code, threejs_config
    content, usage_info, reasoning_content = get_completion(
        OPENROUTER_MODEL, messages, temperature=None, timeout=120
    )
    if usage_tracker:
        usage_tracker.add_step(step_name, OPENROUTER_MODEL, usage_info)
    return _parse_init_json_response(content)


def _generate_initial_manim_and_threejs(
    paper_summary: str,
    paper_title: str,
    usage_tracker: TokenUsageTracker | None = None,
    step_name: str = "Initial Code Generation",
    console: Console | None = None,
) -> tuple[str, str]:
    """Generate initial Manim code and Three.js config via Gemini using init_prompt template."""
    if console:
        _print_model_step(console, "Generating initial code", GEMINI_MODEL_NAME)
    model = genai.GenerativeModel(GEMINI_MODEL_NAME)
    prompt = format_prompt("init_prompt", {"paper_title": paper_title, "paper_summary": paper_summary})
    try:
        response = model.generate_content(prompt, request_options={"timeout": 120})
        if usage_tracker and getattr(response, "usage_metadata", None):
            usage_info = extract_gemini_usage(response)
            usage_tracker.add_step(step_name, GEMINI_MODEL_NAME, usage_info)
        if console:
            _display_reasoning_panel(
                console,
                None,
                fallback_summary="Generate Manim script and Three.js config from paper title and abstract.",
            )
        return _parse_init_json_response(response.text)
    except Exception as e:
        print(f"LLM initial generation error: {e}")
        return "", "{}"


def run_manim_workflow(
    paper_summary: str,
    paper_title: str,
    paper_id: str,
    max_review_cycles: int | None = None,
    progress_callback: Callable[[str], None] | None = None,
    console: Console | None = None,
) -> tuple[str, str, WorkflowStats, dict]:
    """
    Run the manim-generator-style flow: initial generation, execute, then review/revision
    loop on failure. Returns (manim_video_url_path, threejs_config, workflow_stats, usage_tracking_dict, final_manim_code).
    When console is provided, logs match manim-generator (rules, execution status, optional logs panel).
    """
    start_time = time.time()
    usage_tracker = TokenUsageTracker()
    execution_count = 0
    successful_executions = 0
    initial_success = False
    cycles_completed = 0
    show_logs = MANIM_LOGS and console is not None

    def report(msg: str) -> None:
        if progress_callback:
            progress_callback(msg)

    def make_stats(
        final_path: str = "",
        working: bool = False,
    ) -> WorkflowStats:
        return WorkflowStats(
            total_time_seconds=time.time() - start_time,
            review_cycles_completed=cycles_completed,
            execution_count=execution_count,
            successful_executions=successful_executions,
            initial_success=initial_success,
            final_working_code=working,
            final_video_path=final_path,
        )

    cycles = max_review_cycles if max_review_cycles is not None else MANIM_REVIEW_CYCLES
    video_dir = os.path.join(os.getcwd(), "static", "videos")
    os.makedirs(video_dir, exist_ok=True)
    safe_id = paper_id.replace("/", "_").replace(":", "_")
    output_filename = f"animation_{safe_id}.mp4"
    final_mp4_path = os.path.join(video_dir, output_filename)
    video_url_path = f"/static/videos/{output_filename}"

    report("Generating Python Manim script and 3D schema...")
    if console:
        console.rule("[bold green]Initial Code Generation", style="green")
        sys.stdout.flush()
    if USE_OPENROUTER:
        manim_code, threejs_config = _generate_initial_with_openrouter(
            paper_summary, paper_title, usage_tracker, "Initial Code Generation", console
        )
    else:
        manim_code, threejs_config = _generate_initial_manim_and_threejs(
            paper_summary, paper_title, usage_tracker=usage_tracker, step_name="Initial Code Generation", console=console
        )
    if not manim_code.strip():
        return "", threejs_config, make_stats(), usage_tracker.get_tracking_data(), ""

    report("Rendering 2D Manim MP4 (This process takes ~1 minute)...")
    if console:
        console.rule("[bold green]Running Manim Script - Initial", style="green")
        sys.stdout.flush()
    success, combined_logs = run_manim_capture_logs(
        manim_code,
        scene_name="PaperAnimation",
        final_mp4_path=final_mp4_path,
        timeout_seconds=MANIM_SCENE_TIMEOUT,
    )
    current_code = manim_code
    execution_count += 1
    successful_scenes = ["PaperAnimation"] if success else []
    working_code = current_code if success else None
    initial_success = success
    if success:
        successful_executions += 1
    if console:
        _display_execution_status(console, success, combined_logs, "1 of 1", show_logs)
    if not success and console:
        console.print(
            Panel(
                "[bold red]Initial code failed to execute properly. Starting review cycles to fix issues.[/bold red]",
                border_style="red",
            )
        )
        sys.stdout.flush()
        sys.stderr.flush()

    previous_reviews: list[str] = []
    model = genai.GenerativeModel(GEMINI_MODEL_NAME)

    # Run all review cycles (same as manim-generator: no early exit; use last working code)
    for cycle in range(1, cycles + 1):
        cycles_completed = cycle
        report(f"Fixing script (attempt {cycle} of {cycles})...")
        if console:
            console.rule(f"[bold blue]Review Cycle {cycle}", style="blue")
            sys.stdout.flush()

        # Success rate from previous run determines which review prompt to use (manim-generator logic)
        scene_names = extract_scene_class_names(current_code)
        success_rate, scenes_rendered, total_scenes = calculate_scene_success_rate(
            successful_scenes, scene_names
        )
        use_enhanced_prompt = success_rate >= SUCCESS_THRESHOLD
        prompt_name = "review_prompt_enhanced" if use_enhanced_prompt else "review_prompt"

        if console:
            if use_enhanced_prompt:
                console.print(
                    f"[green]High success rate ({success_rate:.1f}%) - Using enhanced visual review prompt[/green]"
                )
            else:
                console.print(
                    f"[yellow]Success rate ({success_rate:.1f}%) - Using standard technical review prompt[/yellow]"
                )
            sys.stdout.flush()

        if use_enhanced_prompt:
            review_content = format_prompt(
                prompt_name,
                {
                    "previous_reviews": format_previous_reviews(previous_reviews),
                    "video_code": current_code,
                    "execution_logs": combined_logs,
                    "success_rate": success_rate,
                    "scenes_rendered": scenes_rendered,
                    "total_scenes": total_scenes,
                },
            )
        else:
            review_content = format_prompt(
                prompt_name,
                {
                    "previous_reviews": format_previous_reviews(previous_reviews),
                    "video_code": current_code,
                    "execution_logs": combined_logs,
                },
            )

        try:
            if USE_OPENROUTER:
                from llm_openrouter import get_completion as openrouter_completion
                if console:
                    _print_model_step(console, f"Generating review (cycle {cycle})", OPENROUTER_MODEL)
                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[bold blue]{task.description}"),
                        TimeElapsedColumn(),
                        console=console,
                    ) as progress:
                        task = progress.add_task(f"Generating review [{OPENROUTER_MODEL}]", total=None)
                        review_text, review_usage, review_reasoning = openrouter_completion(
                            OPENROUTER_MODEL,
                            [{"role": "user", "content": review_content}],
                            temperature=None,
                            timeout=60,
                        )
                        progress.update(task, completed=True)
                    usage_tracker.add_step(f"Review Cycle {cycle}", OPENROUTER_MODEL, review_usage)
                    _display_reasoning_panel(
                        console,
                        review_reasoning,
                        fallback_summary="Review Manim code and execution logs; suggest fixes.",
                    )
                    print_request_summary(console, review_usage)
                else:
                    review_text, review_usage, _ = openrouter_completion(
                        OPENROUTER_MODEL,
                        [{"role": "user", "content": review_content}],
                        temperature=None,
                        timeout=60,
                    )
                    usage_tracker.add_step(f"Review Cycle {cycle}", OPENROUTER_MODEL, review_usage)
                review_text = review_text or ""
            else:
                if console:
                    _print_model_step(console, f"Generating review (cycle {cycle})", GEMINI_MODEL_NAME)
                review_response = model.generate_content(review_content, request_options={"timeout": 60})
                if getattr(review_response, "usage_metadata", None):
                    usage_tracker.add_step(
                        f"Review Cycle {cycle}", GEMINI_MODEL_NAME, extract_gemini_usage(review_response)
                    )
                review_text = review_response.text or ""
                if console:
                    _display_reasoning_panel(
                        console,
                        None,
                        fallback_summary="Review Manim code and execution logs; suggest fixes.",
                    )
        except Exception as e:
            print(f"Review call error: {e}")
            review_text = "The code failed to render. Check execution logs for errors and fix syntax and Manim API usage."
        previous_reviews.append(review_text)
        if console and review_text:
            console.print(
                Panel(
                    Markdown(review_text),
                    title="[blue]Review Feedback[/blue]",
                    border_style="blue",
                )
            )
            sys.stdout.flush()

        revision_prompt = (
            f"You are an expert in Manim Community v0.19.0. Here is the original task context.\n\n"
            f"Paper Title: {paper_title}\nPaper Abstract: {paper_summary}\n\n"
            f"Here is the current code:\n\n```python\n{current_code}\n```\n\n"
            f"Here is review feedback. Implement the suggested fixes and return the complete revised script.\n\n{review_text}\n\n"
            "Respond with ONLY the full Python script inside a single ```python ... ``` code block. Keep the class name PaperAnimation(Scene)."
        )
        try:
            if USE_OPENROUTER:
                from llm_openrouter import get_completion as openrouter_completion
                rev_messages = [{"role": "user", "content": revision_prompt}]
                if console:
                    _print_model_step(console, f"Generating code revision (cycle {cycle})", OPENROUTER_MODEL)
                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[bold green]{task.description}"),
                        TimeElapsedColumn(),
                        console=console,
                    ) as progress:
                        task = progress.add_task(f"Generating code revision [{OPENROUTER_MODEL}]", total=None)
                        rev_content, rev_usage, rev_reasoning = openrouter_completion(
                            OPENROUTER_MODEL, rev_messages, temperature=None, timeout=60
                        )
                        progress.update(task, completed=True)
                    usage_tracker.add_step(f"Code Revision {cycle}", OPENROUTER_MODEL, rev_usage)
                    _display_reasoning_panel(
                        console,
                        rev_reasoning,
                        fallback_summary="Generate revised Manim script from review feedback.",
                    )
                    revised_code = parse_code_block(rev_content or "")
                    if revised_code.strip():
                        print_code_with_syntax(revised_code, console, f"Revised Code - Cycle {cycle}")
                    print_request_summary(console, rev_usage)
                else:
                    rev_content, rev_usage, _ = openrouter_completion(
                        OPENROUTER_MODEL, rev_messages, temperature=None, timeout=60
                    )
                    usage_tracker.add_step(f"Code Revision {cycle}", OPENROUTER_MODEL, rev_usage)
                    revised_code = parse_code_block(rev_content or "")
            else:
                if console:
                    _print_model_step(console, f"Generating code revision (cycle {cycle})", GEMINI_MODEL_NAME)
                revision_response = model.generate_content(revision_prompt, request_options={"timeout": 60})
                if getattr(revision_response, "usage_metadata", None):
                    usage_tracker.add_step(
                        f"Code Revision {cycle}", GEMINI_MODEL_NAME, extract_gemini_usage(revision_response)
                    )
                revised_code = parse_code_block(revision_response.text or "")
                if console:
                    _display_reasoning_panel(
                        console,
                        None,
                        fallback_summary="Generate revised Manim script from review feedback.",
                    )
        except Exception as e:
            print(f"Revision call error: {e}")
            break
        if not revised_code.strip():
            break
        current_code = revised_code

        report("Rendering 2D Manim MP4 (retry)...")
        if console:
            console.rule(f"[bold blue]Running Manim Script - Revision {cycle}", style="blue")
            sys.stdout.flush()
        success, combined_logs = run_manim_capture_logs(
            current_code,
            scene_name="PaperAnimation",
            final_mp4_path=final_mp4_path,
            timeout_seconds=MANIM_SCENE_TIMEOUT,
        )
        execution_count += 1
        successful_scenes = ["PaperAnimation"] if success else []
        if success:
            successful_executions += 1
            working_code = current_code
        if console:
            _display_execution_status(console, success, combined_logs, "1 of 1", show_logs)

    # Return last working code result (same as manim-generator: run all cycles, then finalize)
    return (
        video_url_path if working_code else "",
        threejs_config,
        make_stats(final_mp4_path if working_code else "", working=working_code is not None),
        usage_tracker.get_tracking_data(),
        working_code or "",
    )


def generate_manim_and_threejs_content(paper_summary: str, paper_title: str):
    """Uses Gemini Flash to analyze the paper summary and generate Manim Python code and a Three.js config."""
    
    prompt = f"""
    You are an expert in creating animated videos using the Manim Community library (v0.19.0+).
    I will provide you with the title and abstract of an arXiv paper.
    Your task is to:
    1. Identify the core mathematical or architectural concept.
    2. Write a complete, execution-ready Python script using the 'manim' Community library (NOT manimlib). The class name MUST be exactly 'PaperAnimation' inheriting from 'Scene'. 
       Make sure you instantiate objects correctly (e.g., Circle, Square) and animate them using `self.play(Create(obj))` instead of deprecated names. Always end with `self.wait()`. Do NOT use `ShowCreation`, use `Create`.
       CRITICAL: Be aware of the screen size and resolution and make sure elements do not overlap or go out of frame.
       CRITICAL: Do NOT use external resources or dependencies like svg's, images, or other libraries.
       CRITICAL: When using `move_to()` or `next_to()`, pass the Mobject directly (e.g., `move_to(other_obj)` or `move_to(other_obj.get_center())`). Do NOT pass uncalled methods like `move_to(other_obj.get_center)`.
       CRITICAL: If using `ArcBetweenPoints`, you MUST use the exact keyword arguments `start` and `end` (e.g., `ArcBetweenPoints(start=..., end=...)`), NOT `start_point` / `end_point`.
       CRITICAL: Always use standard, basic color names (e.g., RED, BLUE, GREEN, ORANGE, PURPLE, YELLOW, WHITE). Do NOT use suffixed variables such as ORANGE_A or BLUE_E.
       CRITICAL: Use standard Manim spacing and alignment. Avoid complicated custom math for coordinates that could throw exceptions.
       CRITICAL: DO NOT use `VGroup(*self.mobjects)`. If you need to group everything or fade out all objects, use `Group(*self.mobjects)` since `VGroup` only accepts `VMobject`s and text/images will crash it.
       CRITICAL: STRICTLY FORBIDDEN to use `MathTex` or `Tex`. You MUST use `Text()` for ALL text and math. This environment does not have LaTeX installed (`dvisvgm` is missing). If you use `MathTex`, the video generation WILL FAIL!
    3. Generate a structured JSON configuration for a 3D visualization of the same concept.

    Paper Title: {paper_title}
    Paper Abstract: {paper_summary}

    Return your response strictly in the following JSON format without Markdown blocks surrounding the overall structural JSON:
    {{
        "manim_code": "from manim import *\\n\\nclass PaperAnimation(Scene):\\n    def construct(self):\\n...",
        "threejs_config": {{
            "nodes": [
                {{ "id": "unique_str", "type": "box", "position": [0, 0, 0], "color": "#ff0000", "label": "description", "scale": [1, 1, 1] }},
                {{ "id": "unique_str_2", "type": "sphere", "position": [2, 0, 0], "color": "#00ff00", "label": "description", "scale": [1, 1, 1] }}
            ],
            "edges": [
                {{ "source": "unique_str", "target": "unique_str_2", "color": "#ffffff" }}
            ]
        }}
    }}
    CRITICAL: ALWAYS output strictly valid JSON. NEVER include any // or /* comments inside the JSON structure.
    (Note: For node 'type', use standard shapes like 'box', 'sphere', 'cylinder')
    """
    
    # Initialize the model
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    try:
        # Increase the timeout because generating complicated code scripts takes time
        response = model.generate_content(prompt, request_options={"timeout": 120})
        # We need to parse the JSON response here.
        # For safety in this MVP, we'll return a placeholder if parsing fails.
        import json
        import re
        
        try:
             text = response.text
             # Find the first { and last }
             start_idx = text.find('{')
             end_idx = text.rfind('}')
             
             if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                 json_str = text[start_idx:end_idx+1]
                 
                 # Forcefully remove JS-style // comments which break Python's json parser
                 json_str = re.sub(r'^\s*//.*$', '', json_str, flags=re.MULTILINE)
                 
                 # In case Gemini returns it inside a markdown block with ```json, it was already handled by start_idx/end_idx
                 # However, if there are trailing decorators or bad whitespace, we can clean it
                 json_str = json_str.strip()
                 
                 try:
                     result = json.loads(json_str)
                 except json.JSONDecodeError as de:
                     # Attempt an even more aggressive clean if the first parsing fails
                     import ast
                     import textwrap
                     try:
                        # Fallback parsing strategy in case it generated Python dict strings instead of strict JSON
                        result = ast.literal_eval(json_str)
                     except Exception:
                         raise de # Re-raise original error if fallback fails
                 
                 manim_code = result.get("manim_code", "")
                 threejs_config = json.dumps(result.get("threejs_config", {}))
                 
                 return manim_code, threejs_config
             else:
                 with open('/tmp/llm_debug.txt', 'w') as f: f.write(f"No JSON block in LLM response.\\nRaw:\\n{text}")
                 print("No JSON block found in LLM response")
                 print("Raw response:", text)
                 return "", "{}"
                 
        except json.JSONDecodeError as e:
             with open('/tmp/llm_debug.txt', 'w') as f: f.write(f"JSON Parse Error: {e}\\nRaw:\\n{response.text}")
             print(f"Failed to decode LLM JSON response: {e}")
             print("Raw response:", response.text)
             return "", "{}"
             
    except Exception as e:
        import traceback
        with open('/tmp/llm_debug.txt', 'w') as f: f.write(f"LLM Generation Error: {e}\\n{traceback.format_exc()}")
        print(f"LLM Generation Error: {e}")
        return "", "{}"

def render_manim_video(manim_code: str, paper_id: str) -> str:
    """Renders the Manim code to an MP4 and returns the path (or URL in a real app)."""
    if not manim_code:
        return ""
        
    # Create static directory to serve videos
    video_dir = os.path.join(os.getcwd(), "static", "videos")
    os.makedirs(video_dir, exist_ok=True)
    
    # We need a stable identifier for the output file
    safe_id = paper_id.replace("/", "_").replace(":", "_")
    output_filename = f"animation_{safe_id}.mp4"
    output_filepath = os.path.join(video_dir, output_filename)
        
    with tempfile.TemporaryDirectory() as tmpdir:
        script_path = os.path.join(tmpdir, "animation.py")
        with open(script_path, "w") as f:
            f.write(manim_code)
            
        # Run Manim
        # We use -ql (low quality) for faster generation during testing
        try:
            print(f"Running manim for {output_filename}...")
            # Instruct manim to output the file directly to our static video folder
            subprocess.run(
                ["manim", "-ql", "-o", output_filepath, script_path, "PaperAnimation"],
                cwd=tmpdir,
                check=True,
                capture_output=True
            )
            print(f"Manim render successful: {output_filepath}")
            # The URL path the frontend will request
            return f"/static/videos/{output_filename}" 
        except subprocess.CalledProcessError as e:
            print(f"Manim rendering failed: {e.stderr.decode()}")
            return ""

from fastapi.responses import StreamingResponse

from adk_agents import extract_concepts_with_adk

@app.post("/api/process-paper")
async def process_paper(request: PaperRequest):
    import asyncio

    async def generation_routine():
        yield json.dumps({"status": "step", "message": "Fetching paper metadata from ArXiv..."}) + "\n"

        arxiv_id = extract_arxiv_id(request.url)
        if not arxiv_id:
            yield json.dumps({"status": "error", "message": "Invalid arXiv URL or ID"}) + "\n"
            return

        loop = asyncio.get_event_loop()
        paper = await loop.run_in_executor(None, fetch_arxiv_details, arxiv_id)
        if not paper:
            yield json.dumps({"status": "error", "message": "Paper not found on arXiv"}) + "\n"
            return

        yield json.dumps({"status": "step", "message": "Summarizing & parsing core concepts with AI (using Google ADK)..."}) + "\n"
        
        # Enhanced concept extraction using ADK
        adk_concepts = await extract_concepts_with_adk(paper.title, paper.summary)
        enhanced_summary = paper.summary
        if adk_concepts:
            enhanced_summary += f"\n\n### Key Visual Concepts (Extracted by ADK Agent):\n{adk_concepts}"
            yield json.dumps({"status": "step", "message": "Concepts extracted. Starting workflow..."}) + "\n"
        
        await asyncio.sleep(0.2)

        progress_queue: Queue[str] = Queue()
        # Console for manim-generator-style logs (rules, execution status, optional MANIM_LOGS panel)
        # record=True so we can export plain text to a .txt file next to the video
        console = Console(force_terminal=True, record=True)

        def workflow_with_progress() -> tuple[str, str, WorkflowStats, dict, str]:
            return run_manim_workflow(
                enhanced_summary,
                paper.title,
                arxiv_id,
                max_review_cycles=MANIM_REVIEW_CYCLES,
                progress_callback=lambda msg: progress_queue.put(msg),
                console=console,
            )

        # Run Manim workflow and reproduction pipeline in parallel
        from reproduce_pipeline import run_reproduce_pipeline

        reproduce_console = Console(force_terminal=True, record=True)

        def reproduce_with_progress() -> tuple[str, dict]:
            return run_reproduce_pipeline(
                paper.title,
                enhanced_summary,
                arxiv_id,
                progress_callback=lambda msg: progress_queue.put(f"[Reproduce] {msg}"),
                console=reproduce_console,
            )

        manim_future = loop.run_in_executor(None, workflow_with_progress)
        reproduce_future = loop.run_in_executor(None, reproduce_with_progress)

        # Stream progress from both futures until both complete
        while not manim_future.done() or not reproduce_future.done():
            try:
                while True:
                    msg = progress_queue.get_nowait()
                    yield json.dumps({"status": "step", "message": msg}) + "\n"
            except Empty:
                pass
            await asyncio.sleep(0.05)

        while not progress_queue.empty():
            try:
                msg = progress_queue.get_nowait()
                yield json.dumps({"status": "step", "message": msg}) + "\n"
            except Empty:
                break

        video_url_path, threejs_config, workflow_stats, usage_data, final_manim_code = manim_future.result()

        # Get reproduction result (don't crash if it failed)
        reproduce_notebook_url = ""
        try:
            reproduce_notebook_path, reproduce_usage = reproduce_future.result()
            if reproduce_notebook_path:
                reproduce_notebook_url = f"http://localhost:8000{reproduce_notebook_path}"
        except Exception as e:
            print(f"Reproduction pipeline failed (non-fatal): {e}")

        # Workflow summary and token usage (same as manim-generator; console already created above)
        display_workflow_summary(console, workflow_stats)
        display_usage_summary(console, usage_data)
        sys.stdout.flush()
        sys.stderr.flush()

        # Write manim workflow logs to a .txt file next to the video (plain text, no ANSI)
        safe_id = arxiv_id.replace("/", "_").replace(":", "_")
        video_dir = os.path.join(os.getcwd(), "static", "videos")
        os.makedirs(video_dir, exist_ok=True)
        log_path = os.path.join(video_dir, f"animation_{safe_id}_logs.txt")
        try:
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(console.export_text())
        except Exception as e:
            print(f"Failed to write log file {log_path}: {e}")

        # Generate Colab notebook from working Manim code
        notebook_url = ""
        if final_manim_code.strip():
            try:
                notebook = generate_colab_notebook(final_manim_code, paper.title, paper.summary)
                notebook_filename = f"animation_{safe_id}.ipynb"
                notebook_path = os.path.join(video_dir, notebook_filename)
                save_notebook(notebook, notebook_path)
                notebook_url = f"{BASE_URL}/static/videos/{notebook_filename}"
            except Exception as e:
                print(f"Failed to generate Colab notebook: {e}")

        yield json.dumps({"status": "step", "message": "Finalizing payload..."}) + "\n"

        yield json.dumps({
            "status": "complete",
            "result": {
                "title": paper.title,
                "authors": [auth.name for auth in paper.authors],
                "summary": paper.summary,
                "manim_video_url": f"{BASE_URL}{video_url_path}" if video_url_path else "",
                "three_js_config": threejs_config,
                "notebook_url": f"{BASE_URL}/static/videos/{notebook_filename}" if notebook_url else "",
                "reproduce_notebook_url": f"{BASE_URL}{reproduce_notebook_path}" if reproduce_notebook_path else "",
            },
        }) + "\n"

    return StreamingResponse(generation_routine(), media_type="application/x-ndjson")

@app.post("/api/reproduce-paper")
async def reproduce_paper(request: PaperRequest):
    """Generate a runnable Colab notebook that reproduces the paper's core experiment."""
    import asyncio
    from reproduce_pipeline import run_reproduce_pipeline

    async def generation_routine():
        yield json.dumps({"status": "step", "message": "Fetching paper metadata from ArXiv..."}) + "\n"

        arxiv_id = extract_arxiv_id(request.url)
        if not arxiv_id:
            yield json.dumps({"status": "error", "message": "Invalid arXiv URL or ID"}) + "\n"
            return

        loop = asyncio.get_event_loop()
        paper = await loop.run_in_executor(None, fetch_arxiv_details, arxiv_id)
        if not paper:
            yield json.dumps({"status": "error", "message": "Paper not found on arXiv"}) + "\n"
            return

        yield json.dumps({"status": "step", "message": "Starting reproduction pipeline..."}) + "\n"

        progress_queue: Queue[str] = Queue()
        console = Console(force_terminal=True, record=True)

        def pipeline_with_progress() -> tuple[str, dict]:
            return run_reproduce_pipeline(
                paper.title,
                paper.summary,
                arxiv_id,
                progress_callback=lambda msg: progress_queue.put(msg),
                console=console,
            )

        future = loop.run_in_executor(None, pipeline_with_progress)

        while not future.done():
            try:
                while True:
                    msg = progress_queue.get_nowait()
                    yield json.dumps({"status": "step", "message": msg}) + "\n"
            except Empty:
                pass
            await asyncio.sleep(0.05)

        while not progress_queue.empty():
            try:
                msg = progress_queue.get_nowait()
                yield json.dumps({"status": "step", "message": msg}) + "\n"
            except Empty:
                break

        try:
            notebook_url_path, usage_data = future.result()
        except Exception as e:
            yield json.dumps({"status": "error", "message": f"Pipeline failed: {e}"}) + "\n"
            return

        yield json.dumps({"status": "step", "message": "Finalizing notebook..."}) + "\n"

        yield json.dumps({
            "status": "complete",
            "result": {
                "title": paper.title,
                "authors": [auth.name for auth in paper.authors],
                "summary": paper.summary,
                "reproduce_notebook_url": f"{BASE_URL}{notebook_url_path}" if notebook_url_path else "",
            },
        }) + "\n"

    return StreamingResponse(generation_routine(), media_type="application/x-ndjson")


@app.post("/api/process-paper-sections")
async def process_paper_sections(request: PaperRequest):
    """Generate section-by-section animations with PDF page mapping."""
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    from pdf_utils import download_arxiv_pdf, extract_text_by_page, identify_sections

    async def generation_routine():
        yield json.dumps({"status": "step", "message": "Fetching paper metadata from ArXiv..."}) + "\n"

        arxiv_id = extract_arxiv_id(request.url)
        if not arxiv_id:
            yield json.dumps({"status": "error", "message": "Invalid arXiv URL or ID"}) + "\n"
            return

        loop = asyncio.get_event_loop()
        paper = await loop.run_in_executor(None, fetch_arxiv_details, arxiv_id)
        if not paper:
            yield json.dumps({"status": "error", "message": "Paper not found on arXiv"}) + "\n"
            return

        yield json.dumps({"status": "step", "message": "Downloading paper PDF..."}) + "\n"

        safe_id = arxiv_id.replace("/", "_").replace(":", "_")
        pdf_dir = os.path.join(os.getcwd(), "static", "pdfs")
        os.makedirs(pdf_dir, exist_ok=True)

        try:
            pdf_path = await loop.run_in_executor(None, download_arxiv_pdf, arxiv_id, pdf_dir)
        except Exception as e:
            yield json.dumps({"status": "error", "message": f"Failed to download PDF: {e}"}) + "\n"
            return

        pdf_url = f"{BASE_URL}/static/pdfs/{os.path.basename(pdf_path)}"

        yield json.dumps({"status": "step", "message": "Extracting text from PDF..."}) + "\n"
        pages_text = await loop.run_in_executor(None, extract_text_by_page, pdf_path)

        yield json.dumps({"status": "step", "message": "Identifying paper sections with AI..."}) + "\n"
        usage_tracker = TokenUsageTracker()

        try:
            sections = await loop.run_in_executor(
                None, identify_sections, pages_text, paper.title, usage_tracker
            )
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "quota" in error_msg.lower() or "rate" in error_msg.lower():
                yield json.dumps({"status": "error", "message": "Gemini API rate limit reached. Please wait a minute and try again, or upgrade your API key."}) + "\n"
            else:
                yield json.dumps({"status": "error", "message": f"Failed to identify sections: {error_msg}"}) + "\n"
            return

        yield json.dumps({"status": "step", "message": f"Found {len(sections)} sections. Generating animations..."}) + "\n"

        # Generate animations for each section sequentially to avoid rate limits
        progress_queue: Queue[str] = Queue()
        video_dir = os.path.join(os.getcwd(), "static", "videos")
        os.makedirs(video_dir, exist_ok=True)

        def generate_section_animation(section: dict) -> dict:
            """Generate a Manim animation for a single section."""
            section_id = section.get("id", "unknown")
            section_title = section.get("title", section_id)
            section_text = section.get("text", "")
            scene_class = section_id.replace("_", " ").title().replace(" ", "") + "Animation"
            output_filename = f"section_{safe_id}_{section_id}.mp4"

            progress_queue.put(f"Generating animation for: {section_title}")

            try:
                prompt = format_prompt("section_animation_prompt", {
                    "paper_title": paper.title,
                    "section_title": section_title,
                    "section_text": section_text,
                    "scene_class_name": scene_class,
                })

                model = genai.GenerativeModel(GEMINI_MODEL_NAME)
                response = model.generate_content(prompt, request_options={"timeout": 120})
                if getattr(response, "usage_metadata", None):
                    usage_tracker.add_step(
                        f"Animation: {section_title}", GEMINI_MODEL_NAME, extract_gemini_usage(response)
                    )
                raw_code = response.text or ""
                code = parse_code_block(raw_code)

                if not code.strip():
                    progress_queue.put(f"Empty code for: {section_title}")
                    return {**section, "video_url": ""}

                # Render the animation
                output_path = os.path.join(video_dir, output_filename)
                success, logs = run_manim_capture_logs(
                    code, scene_name=scene_class, final_mp4_path=output_path,
                    timeout_seconds=MANIM_SCENE_TIMEOUT,
                )

                if success:
                    progress_queue.put(f"Rendered: {section_title}")
                    return {**section, "video_url": f"{BASE_URL}/static/videos/{output_filename}"}

                # One retry with error feedback
                progress_queue.put(f"Retrying: {section_title}")
                error_snippet = logs[-500:] if logs else "Unknown render error"
                retry_prompt = format_prompt("section_animation_prompt", {
                    "paper_title": paper.title,
                    "section_title": section_title,
                    "section_text": section_text + f"\n\nPREVIOUS ATTEMPT FAILED WITH ERROR:\n{error_snippet}\nFix these issues.",
                    "scene_class_name": scene_class,
                })
                response = model.generate_content(retry_prompt, request_options={"timeout": 120})
                if getattr(response, "usage_metadata", None):
                    usage_tracker.add_step(
                        f"Retry: {section_title}", GEMINI_MODEL_NAME, extract_gemini_usage(response)
                    )
                code = parse_code_block(response.text or "")
                if code.strip():
                    success, logs = run_manim_capture_logs(
                        code, scene_name=scene_class, final_mp4_path=output_path,
                        timeout_seconds=MANIM_SCENE_TIMEOUT,
                    )
                    if success:
                        progress_queue.put(f"Rendered (retry): {section_title}")
                        return {**section, "video_url": f"{BASE_URL}/static/videos/{output_filename}"}

                progress_queue.put(f"Failed: {section_title}")
                return {**section, "video_url": ""}

            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg or "quota" in error_msg.lower():
                    progress_queue.put(f"Rate limited, skipping: {section_title}")
                else:
                    progress_queue.put(f"Error: {section_title}: {error_msg[:100]}")
                return {**section, "video_url": ""}

        def run_all_sections():
            from concurrent.futures import ThreadPoolExecutor, as_completed
            results = []
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {executor.submit(generate_section_animation, s): s for s in sections}
                for future in as_completed(futures):
                    results.append(future.result())
            results.sort(key=lambda x: x.get("page_start", 0))
            return results

        section_future = loop.run_in_executor(None, run_all_sections)

        # Stream progress while sections are being generated
        while not section_future.done():
            try:
                while True:
                    msg = progress_queue.get_nowait()
                    yield json.dumps({"status": "step", "message": msg}) + "\n"
            except Empty:
                pass
            await asyncio.sleep(0.05)

        # Drain remaining progress messages
        while not progress_queue.empty():
            try:
                msg = progress_queue.get_nowait()
                yield json.dumps({"status": "step", "message": msg}) + "\n"
            except Empty:
                break

        try:
            section_results = section_future.result()
        except Exception as e:
            yield json.dumps({"status": "error", "message": f"Animation generation failed: {e}"}) + "\n"
            return

        yield json.dumps({"status": "step", "message": "Finalizing..."}) + "\n"

        yield json.dumps({
            "status": "complete",
            "result": {
                "title": paper.title,
                "authors": [auth.name for auth in paper.authors],
                "summary": paper.summary,
                "pdf_url": pdf_url,
                "total_pages": len(pages_text),
                "sections": [
                    {
                        "id": s.get("id", ""),
                        "title": s.get("title", ""),
                        "text": s.get("text", ""),
                        "video_url": s.get("video_url", ""),
                        "page_start": s.get("page_start", 1),
                        "page_end": s.get("page_end", 1),
                    }
                    for s in section_results
                ],
            },
        }) + "\n"

    return StreamingResponse(generation_routine(), media_type="application/x-ndjson")


@app.get("/health")
def health_check():
    return {"status": "ok"}
