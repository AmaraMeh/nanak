#!/usr/bin/env bash
set -euo pipefail
if command -v apt >/dev/null 2>&1; then
  sudo apt-get update && sudo apt-get install -y python3-venv || true
fi
python3 -m venv .venv || true
source .venv/bin/activate || true
pip install -U pip
pip install -r requirements.txt
