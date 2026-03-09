"""Manim generation utilities: parsing, prompt loading, execution with log capture."""

import ast
import os
import re
import shutil
import subprocess
import tempfile
from typing import Callable


class SceneParsingError(Exception):
    """Raised when scene class names cannot be extracted from code."""

    pass


def parse_code_block(text: str) -> str:
    """
    Extract the first Python code block from text (```python ... ``` or ``` ... ```).
    Returns stripped code, or the whole text if no block found.
    """
    match = re.search(
        r"```(?:python)?\s*\n(.*?)```",
        text,
        re.DOTALL,
    )
    return match.group(1).strip() if match else text.strip()


def extract_scene_class_names(code: str) -> list[str] | SceneParsingError:
    """
    Extract Scene class names from Manim code via AST.
    Returns list of class names or SceneParsingError on parse failure.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return SceneParsingError(f"Syntax error in code: {e}")

    scene_names: list[str] = []
    try:
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    base_id = (
                        base.id
                        if isinstance(base, ast.Name)
                        else getattr(base, "attr", "")
                    )
                    if isinstance(base, ast.Attribute):
                        base_id = base.attr
                    if base_id and str(base_id).endswith("Scene"):
                        scene_names.append(node.name)
                        break
    except Exception as e:
        return SceneParsingError(f"Error extracting scene names: {e}")
    return scene_names


def format_prompt(prompt_name: str, replacements: dict[str, str]) -> str:
    """
    Load a prompt template from backend/prompts/{name}.txt and replace placeholders.
    """
    base = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base, "prompts", f"{prompt_name}.txt")
    with open(path, encoding="utf-8") as f:
        template = f.read()
    for key, value in replacements.items():
        template = template.replace(f"{{{key}}}", str(value))
    return template


def format_previous_reviews(previous_reviews: list[str]) -> str:
    """
    Format a list of review feedback strings into XML-style tagged format (same as manim-generator).
    """
    return "\n".join(
        f"<review_{idx}>\n{feedback}\n</review_{idx}>"
        for idx, feedback in enumerate(previous_reviews)
    )


def calculate_scene_success_rate(
    successful_scenes: list[str],
    scene_names: list[str] | SceneParsingError,
) -> tuple[float, int, int]:
    """
    Calculate the success rate of scene rendering (same as manim-generator).
    Returns (success_rate, scenes_rendered, total_scenes).
    """
    if isinstance(scene_names, SceneParsingError):
        return 0.0, 0, 0
    total_scenes = len(scene_names)
    if total_scenes == 0:
        return 0.0, 0, 0
    scenes_rendered = len(successful_scenes)
    success_rate = (scenes_rendered / total_scenes) * 100
    return success_rate, scenes_rendered, total_scenes


def run_manim_capture_logs(
    manim_code: str,
    scene_name: str = "PaperAnimation",
    final_mp4_path: str | None = None,
    timeout_seconds: int | None = None,
) -> tuple[bool, str]:
    """
    Run Manim on the given code, capture stdout/stderr, and optionally write
    the output video to final_mp4_path on success.

    Returns:
        (success, combined_log_string)
    """
    if not manim_code.strip():
        return False, "No code provided."

    with tempfile.TemporaryDirectory() as tmpdir:
        script_path = os.path.join(tmpdir, "animation.py")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(manim_code)

        # Manim with -o: output file path. We need to run from tmpdir and point output.
        # If final_mp4_path is set, we run with -o pointing to that path (manim will create parent dirs for media_dir but -o is the file path).
        # Actually manim -ql -o /path/to/file.mp4 script.py Scene writes to that file.
        output_path = final_mp4_path if final_mp4_path else os.path.join(tmpdir, "out.mp4")
        if final_mp4_path:
            os.makedirs(os.path.dirname(final_mp4_path), exist_ok=True)

        cmd = [
            "manim",
            "-ql",
            "-o", output_path,
            script_path,
            scene_name,
        ]
        try:
            result = subprocess.run(
                cmd,
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as e:
            combined = f"<{scene_name}>\nstdout:\n{e.stdout or ''}\nstderr:\n{e.stderr or ''}\n(Timed out after {timeout_seconds}s)"
            return False, combined

        stdout = result.stdout or ""
        stderr = result.stderr or ""
        combined_log = f"<{scene_name}>\nstdout:\n{stdout}\nstderr:\n{stderr}\n"

        if result.returncode != 0:
            return False, combined_log

        # On success, if we ran with a temp path and final_mp4_path was provided, copy to final
        if final_mp4_path and output_path != final_mp4_path:
            # Manim -o output path: the file is written at output_path (we set it to final_mp4_path above)
            # So when final_mp4_path is set, we already passed it as -o, so the file should be there.
            pass
        # When final_mp4_path is set we passed it as -o, so manim wrote there. No copy needed.
        return True, combined_log
