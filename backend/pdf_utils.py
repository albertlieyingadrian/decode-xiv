"""
PDF utilities for downloading arXiv papers and extracting text by page.
"""

import os
import re
import json
import tempfile

import fitz  # PyMuPDF
import requests

import google.generativeai as genai

from manim_utils import format_prompt
from workflow_usage import TokenUsageTracker, extract_gemini_usage

GEMINI_MODEL_NAME = "gemini-2.5-flash"


def download_arxiv_pdf(arxiv_id: str, output_dir: str) -> str:
    """Download a PDF from arXiv and return the local file path."""
    clean_id = arxiv_id.strip().replace(":", "_").replace("/", "_")
    pdf_path = os.path.join(output_dir, f"{clean_id}.pdf")

    if os.path.exists(pdf_path):
        return pdf_path

    url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    resp = requests.get(url, timeout=60, stream=True)
    resp.raise_for_status()

    os.makedirs(output_dir, exist_ok=True)
    with open(pdf_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)

    return pdf_path


def extract_text_by_page(pdf_path: str, max_pages: int = 50) -> list[dict]:
    """Extract text from each page of a PDF using PyMuPDF.

    Returns a list of dicts: [{"page": 1, "text": "..."}, ...]
    """
    doc = fitz.open(pdf_path)
    pages = []
    for i, page in enumerate(doc):
        if i >= max_pages:
            break
        text = page.get_text("text")
        pages.append({"page": i + 1, "text": text.strip()})
    doc.close()
    return pages


def _parse_json_response(text: str) -> dict | list | None:
    """Extract the first JSON object or array from LLM output."""
    # Try object
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


def identify_sections(
    pages_text: list[dict],
    paper_title: str,
    usage_tracker: TokenUsageTracker | None = None,
) -> list[dict]:
    """Use LLM to identify paper sections and map them to page ranges.

    Returns list of dicts:
    [
        {
            "id": "introduction",
            "title": "Introduction",
            "text": "...",
            "page_start": 1,
            "page_end": 2
        },
        ...
    ]
    """
    # Build page-annotated text (truncate to ~30K chars)
    annotated = ""
    for p in pages_text:
        header = f"\n--- PAGE {p['page']} ---\n"
        annotated += header + p["text"] + "\n"
        if len(annotated) > 30000:
            break

    prompt = format_prompt("section_parse_prompt", {
        "paper_title": paper_title,
        "paper_text": annotated,
    })

    model = genai.GenerativeModel(GEMINI_MODEL_NAME)
    response = model.generate_content(prompt, request_options={"timeout": 120})

    if usage_tracker and getattr(response, "usage_metadata", None):
        usage_tracker.add_step("Section Identification", GEMINI_MODEL_NAME, extract_gemini_usage(response))

    raw = response.text or ""
    parsed = _parse_json_response(raw)

    if not isinstance(parsed, list):
        # Fallback: split paper into 3 rough sections
        total_pages = len(pages_text)
        third = max(1, total_pages // 3)
        return [
            {
                "id": "introduction",
                "title": "Introduction",
                "text": "\n".join(p["text"] for p in pages_text[:third]),
                "page_start": 1,
                "page_end": third,
            },
            {
                "id": "method",
                "title": "Method & Architecture",
                "text": "\n".join(p["text"] for p in pages_text[third : 2 * third]),
                "page_start": third + 1,
                "page_end": 2 * third,
            },
            {
                "id": "results",
                "title": "Results & Conclusion",
                "text": "\n".join(p["text"] for p in pages_text[2 * third :]),
                "page_start": 2 * third + 1,
                "page_end": total_pages,
            },
        ]

    return parsed
