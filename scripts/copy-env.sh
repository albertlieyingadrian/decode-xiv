#!/usr/bin/env bash
# Copy repo root .env into all target folders (arxiv-animator, examples, etc.).
# Create a single .env at the repo root, then run: ./scripts/copy-env.sh

set -e
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

ROOT_ENV="$REPO_ROOT/.env"

if [[ ! -f "$ROOT_ENV" ]]; then
  echo "No .env at repo root. Create $ROOT_ENV first (e.g. copy from arxiv-animator/backend/.env.local.example)."
  exit 1
fi

# Directories that should receive a copy of the root .env
TARGETS=(
  "arxiv-animator/backend"
  "arxiv-animator/frontend"
  "examples/2026-03-07-google-adk"
  "examples/2026-03-07-google-adk/python/multi_tool_agent"
)

echo "Copying root .env to:"
for dir in "${TARGETS[@]}"; do
  if [[ -d "$dir" ]]; then
    mkdir -p "$dir"
    cp "$ROOT_ENV" "$dir/.env"
    echo "  $dir/.env"
  else
    echo "  (skip $dir - not present)"
  fi
done
echo "Done."
