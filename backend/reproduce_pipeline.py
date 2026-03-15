"""
Paper Reproduction Pipeline — 6-stage orchestrator.

Stages:
  1. Paper Parsing         – extract structured metadata from abstract
  2. Spec Extraction       – build reproducibility specification via LLM
  3. External Resource Search – query Papers With Code + HuggingFace
  4. Code Planning         – generate notebook cell plan via LLM
  5. Code Generation       – generate full runnable code via LLM
  6. Notebook Assembly     – build .ipynb from generated cells
"""

import json
import os
import re
import time
from collections.abc import Callable

import google.generativeai as genai
import requests
from rich.console import Console

from manim_utils import format_prompt
from notebook_utils import save_notebook
from workflow_usage import TokenUsageTracker, extract_gemini_usage

GEMINI_MODEL_NAME = "gemini-2.5-flash"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_json_response(text: str) -> dict | list | None:
    """Extract the first JSON object or array from LLM output."""
    # Try object first
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start : end + 1]
        candidate = re.sub(r"^\s*//.*$", "", candidate, flags=re.MULTILINE).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    # Try array
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        candidate = text[start : end + 1]
        candidate = re.sub(r"^\s*//.*$", "", candidate, flags=re.MULTILINE).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    return None


def _llm_call(prompt: str, usage_tracker: TokenUsageTracker, step_name: str, timeout: int = 120) -> str:
    """Single Gemini call with usage tracking. Returns raw text."""
    model = genai.GenerativeModel(GEMINI_MODEL_NAME)
    response = model.generate_content(prompt, request_options={"timeout": timeout})
    if getattr(response, "usage_metadata", None):
        usage_tracker.add_step(step_name, GEMINI_MODEL_NAME, extract_gemini_usage(response))
    return response.text or ""


# ---------------------------------------------------------------------------
# Stage 1 — Paper Parsing
# ---------------------------------------------------------------------------

def stage_parse_paper(
    paper_title: str,
    paper_summary: str,
    usage_tracker: TokenUsageTracker,
) -> dict:
    """Extract structured metadata from the paper abstract via LLM."""
    prompt = format_prompt("reproduce_parse_prompt", {
        "paper_title": paper_title,
        "paper_summary": paper_summary,
    })
    raw = _llm_call(prompt, usage_tracker, "Paper Parsing")
    parsed = _parse_json_response(raw)
    if not isinstance(parsed, dict):
        return {"title": paper_title, "task_type": "unknown", "datasets_mentioned": [], "model_names": [], "metrics_mentioned": [], "key_techniques": [], "domain": "unknown", "key_contributions": [], "baseline_models": []}
    return parsed


# ---------------------------------------------------------------------------
# Stage 2 — Reproducibility Spec Extraction
# ---------------------------------------------------------------------------

def stage_extract_spec(
    paper_title: str,
    paper_summary: str,
    parsed_metadata: dict,
    external_resources: dict,
    usage_tracker: TokenUsageTracker,
) -> dict:
    """Generate reproducibility specification via LLM."""
    prompt = format_prompt("reproduce_spec_prompt", {
        "paper_title": paper_title,
        "paper_summary": paper_summary,
        "parsed_metadata": json.dumps(parsed_metadata, indent=2),
        "external_resources": json.dumps(external_resources, indent=2),
    })
    raw = _llm_call(prompt, usage_tracker, "Spec Extraction", timeout=120)
    parsed = _parse_json_response(raw)
    if not isinstance(parsed, dict):
        return {"task": "unknown", "framework": "PyTorch", "dataset": {"name": "unknown", "source": "unknown"}, "model_architecture": {"name": "unknown"}, "training": {"epochs": 3}, "evaluation": {"metrics": ["accuracy"]}, "dependencies": [], "assumptions": ["Could not fully parse paper spec"]}
    return parsed


# ---------------------------------------------------------------------------
# Stage 3 — External Resource Search
# ---------------------------------------------------------------------------

def stage_search_resources(paper_id: str, parsed_metadata: dict) -> dict:
    """Query Papers With Code and HuggingFace for existing resources."""
    resources: dict = {
        "paperswithcode": None,
        "github_repos": [],
        "huggingface_datasets": [],
        "huggingface_models": [],
    }

    # Papers With Code
    try:
        clean_id = paper_id.replace("/", "_").strip()
        resp = requests.get(
            f"https://paperswithcode.com/api/v1/papers/?arxiv_id={clean_id}",
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", data) if isinstance(data, dict) else data
            if isinstance(results, list) and results:
                paper_data = results[0]
                resources["paperswithcode"] = {
                    "title": paper_data.get("title", ""),
                    "url": paper_data.get("url_abs", ""),
                }
                # Fetch repos
                paper_pwc_id = paper_data.get("id", "")
                if paper_pwc_id:
                    repo_resp = requests.get(
                        f"https://paperswithcode.com/api/v1/papers/{paper_pwc_id}/repositories/",
                        timeout=10,
                    )
                    if repo_resp.status_code == 200:
                        repo_data = repo_resp.json()
                        repos = repo_data.get("results", repo_data) if isinstance(repo_data, dict) else repo_data
                        if isinstance(repos, list):
                            resources["github_repos"] = [
                                {"url": r.get("url", ""), "stars": r.get("stars", 0), "is_official": r.get("is_official", False)}
                                for r in repos[:5]
                            ]
    except Exception:
        pass

    # HuggingFace dataset search
    datasets_mentioned = parsed_metadata.get("datasets_mentioned", [])
    for ds_name in datasets_mentioned[:3]:
        try:
            resp = requests.get(
                f"https://huggingface.co/api/datasets?search={ds_name}&limit=3",
                timeout=10,
            )
            if resp.status_code == 200:
                for item in resp.json()[:2]:
                    resources["huggingface_datasets"].append({
                        "id": item.get("id", ""),
                        "downloads": item.get("downloads", 0),
                    })
        except Exception:
            pass

    # HuggingFace model search
    model_names = parsed_metadata.get("model_names", [])
    for model_name in model_names[:3]:
        try:
            resp = requests.get(
                f"https://huggingface.co/api/models?search={model_name}&limit=3",
                timeout=10,
            )
            if resp.status_code == 200:
                for item in resp.json()[:2]:
                    resources["huggingface_models"].append({
                        "id": item.get("id", ""),
                        "downloads": item.get("downloads", 0),
                    })
        except Exception:
            pass

    return resources


# ---------------------------------------------------------------------------
# Stage 4 — Code Planning
# ---------------------------------------------------------------------------

def stage_plan_notebook(
    paper_title: str,
    repro_spec: dict,
    usage_tracker: TokenUsageTracker,
) -> list[dict]:
    """Generate a structured notebook cell plan via LLM."""
    prompt = format_prompt("reproduce_plan_prompt", {
        "paper_title": paper_title,
        "repro_spec": json.dumps(repro_spec, indent=2),
    })
    raw = _llm_call(prompt, usage_tracker, "Notebook Planning")
    parsed = _parse_json_response(raw)
    if not isinstance(parsed, list):
        # Fallback minimal plan
        return [
            {"cell_type": "markdown", "purpose": "title_and_summary", "description": f"# {paper_title}"},
            {"cell_type": "code", "purpose": "install_dependencies", "description": "Install packages"},
            {"cell_type": "code", "purpose": "full_implementation", "description": "Complete implementation"},
        ]
    return parsed


# ---------------------------------------------------------------------------
# Stage 5 — Code Generation
# ---------------------------------------------------------------------------

def stage_generate_code(
    paper_title: str,
    paper_summary: str,
    repro_spec: dict,
    notebook_plan: list[dict],
    external_resources: dict,
    usage_tracker: TokenUsageTracker,
) -> list[dict]:
    """Generate all notebook cells with complete, runnable code via LLM."""
    prompt = format_prompt("reproduce_codegen_prompt", {
        "paper_title": paper_title,
        "paper_summary": paper_summary,
        "repro_spec": json.dumps(repro_spec, indent=2),
        "notebook_plan": json.dumps(notebook_plan, indent=2),
        "external_resources": json.dumps(external_resources, indent=2),
    })
    raw = _llm_call(prompt, usage_tracker, "Code Generation", timeout=180)
    parsed = _parse_json_response(raw)
    if not isinstance(parsed, list):
        return [
            {"cell_type": "markdown", "source": f"# {paper_title}\n\nCode generation failed. Please retry."},
            {"cell_type": "code", "source": "# Code generation did not return valid cells.\n# Please try again or check the paper URL."},
        ]
    return parsed


# ---------------------------------------------------------------------------
# Stage 6 — Notebook Assembly
# ---------------------------------------------------------------------------

def stage_assemble_notebook(cells: list[dict], paper_title: str) -> dict:
    """Assemble cells into a .ipynb notebook dict."""
    nb_cells = []
    for cell in cells:
        cell_type = cell.get("cell_type", "code")
        source = cell.get("source", cell.get("content", ""))
        if not source:
            continue
        lines = source.splitlines(keepends=True)
        if cell_type == "markdown":
            nb_cells.append({
                "cell_type": "markdown",
                "metadata": {},
                "source": lines,
            })
        else:
            nb_cells.append({
                "cell_type": "code",
                "metadata": {},
                "source": lines,
                "outputs": [],
                "execution_count": None,
            })

    return {
        "nbformat": 4,
        "nbformat_minor": 0,
        "metadata": {
            "colab": {
                "provenance": [],
                "name": f"Reproduce: {paper_title}",
                "gpuType": "T4",
            },
            "kernelspec": {
                "name": "python3",
                "display_name": "Python 3",
            },
            "language_info": {"name": "python"},
            "accelerator": "GPU",
        },
        "cells": nb_cells,
    }


# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------

def run_reproduce_pipeline(
    paper_title: str,
    paper_summary: str,
    paper_id: str,
    progress_callback: Callable[[str], None] | None = None,
    console: Console | None = None,
) -> tuple[str, dict]:
    """
    Run the full 6-stage reproduction pipeline.
    Returns (notebook_url_path, usage_tracking_data).
    """
    usage_tracker = TokenUsageTracker()

    def report(msg: str) -> None:
        if progress_callback:
            progress_callback(msg)

    # Stage 1 — Parse
    report("Parsing paper structure...")
    parsed_metadata = stage_parse_paper(paper_title, paper_summary, usage_tracker)
    if console:
        console.print(f"[green]Stage 1 complete:[/green] Parsed {len(parsed_metadata.get('datasets_mentioned', []))} datasets, {len(parsed_metadata.get('model_names', []))} models")

    # Stage 3 — External Resources (run before spec so spec can use them)
    report("Searching external resources (Papers With Code, HuggingFace)...")
    external_resources = stage_search_resources(paper_id, parsed_metadata)
    n_repos = len(external_resources.get("github_repos", []))
    n_datasets = len(external_resources.get("huggingface_datasets", []))
    if console:
        console.print(f"[green]Stage 3 complete:[/green] Found {n_repos} repos, {n_datasets} HF datasets")

    # Stage 2 — Spec
    report("Extracting reproducibility specification...")
    repro_spec = stage_extract_spec(paper_title, paper_summary, parsed_metadata, external_resources, usage_tracker)
    if console:
        console.print(f"[green]Stage 2 complete:[/green] Task={repro_spec.get('task', 'unknown')}")

    # Stage 4 — Plan
    report("Planning notebook structure...")
    notebook_plan = stage_plan_notebook(paper_title, repro_spec, usage_tracker)
    if console:
        console.print(f"[green]Stage 4 complete:[/green] {len(notebook_plan)} cells planned")

    # Stage 5 — Code Generation
    report("Generating reproduction code (this may take a minute)...")
    cells = stage_generate_code(paper_title, paper_summary, repro_spec, notebook_plan, external_resources, usage_tracker)
    if console:
        console.print(f"[green]Stage 5 complete:[/green] {len(cells)} cells generated")

    # Stage 6 — Assemble
    report("Assembling Colab notebook...")
    notebook = stage_assemble_notebook(cells, paper_title)

    # Save notebook
    safe_id = paper_id.replace("/", "_").replace(":", "_")
    notebook_dir = os.path.join(os.getcwd(), "static", "notebooks")
    os.makedirs(notebook_dir, exist_ok=True)
    notebook_filename = f"reproduce_{safe_id}.ipynb"
    notebook_path = os.path.join(notebook_dir, notebook_filename)
    save_notebook(notebook, notebook_path)

    notebook_url_path = f"/static/notebooks/{notebook_filename}"
    if console:
        console.print(f"[green]Stage 6 complete:[/green] Notebook saved to {notebook_path}")

    return notebook_url_path, usage_tracker.get_tracking_data()
