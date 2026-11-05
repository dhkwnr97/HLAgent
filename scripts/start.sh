#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
export HLAGENT_INBOX="${HLAGENT_INBOX:-${PWD}/knowledge/inbox}"
export UV_PROJECT_ENVIRONMENT="${HLAGENT_HOME:-${HOME}/.local/share/hlagent}/venv"
if ! command -v uv >/dev/null 2>&1; then
    export PATH="${HOME}/.local/bin:${PATH}"
fi
if ! command -v uv >/dev/null 2>&1; then
    printf '%s\n' 'Install uv using scripts/bootstrap.sh first.' >&2
    exit 1
fi
uv sync --frozen --no-dev --python 3.12
uv run --frozen --no-sync hlagent start --open-browser
