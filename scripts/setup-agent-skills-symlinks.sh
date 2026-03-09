#!/usr/bin/env bash
# Project-level: use .agents/skills as canonical; symlink .cursor/skills and .claude/skills to it.
# Run from repo root.

set -e

REPO_ROOT="${1:-.}"
cd "$REPO_ROOT"

AGENTS_SKILLS=".agents/skills"
CURSOR_SKILLS=".cursor/skills"
CLAUDE_SKILLS=".claude/skills"
TARGET_FROM_CURSOR="../.agents/skills"
TARGET_FROM_CLAUDE="../.agents/skills"

mkdir -p "$AGENTS_SKILLS" .cursor .claude

link_or_warn() {
  local dir=$1
  local target=$2
  local name=$3
  if [[ -L "$dir" ]]; then
    current=$(readlink "$dir")
    if [[ "$current" == "$target" ]]; then
      echo "[ok] $name already symlinked to $target"
      return 0
    fi
    echo "[warn] $name is a symlink to something else: $(readlink "$dir")"
    return 1
  fi
  if [[ -d "$dir" ]]; then
    echo "[warn] $name is a real directory. Move its contents into $AGENTS_SKILLS/ then re-run, or remove it to allow symlink."
    return 1
  fi
  ln -snf "$target" "$dir"
  echo "[ok] $name -> $target"
  return 0
}

link_or_warn "$CURSOR_SKILLS" "$TARGET_FROM_CURSOR" ".cursor/skills" || true
link_or_warn "$CLAUDE_SKILLS" "$TARGET_FROM_CLAUDE" ".claude/skills" || true

echo "Done. Skills in $AGENTS_SKILLS are shared via .cursor/skills and .claude/skills."
