#!/usr/bin/env bash
# Wrapper around `uv sync --all-packages` that fixes the macOS UF_HIDDEN
# flag on editable .pth files. See QUICKSTART.md for context.
set -euo pipefail

cd "$(dirname "$0")/.."

uv sync --all-packages "$@"

# macOS-only: strip the hidden flag so Python's site.py processes the .pth.
if [[ "$OSTYPE" == "darwin"* ]]; then
    PTH_GLOB=".venv/lib/python*/site-packages/*.pth"
    # shellcheck disable=SC2086
    chflags nohidden $PTH_GLOB 2>/dev/null || true
fi

echo "Sync complete."
