#!/usr/bin/env bash
set -euo pipefail
source .venv/bin/activate
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)/src"
exec python -m elearning_bot.runner
