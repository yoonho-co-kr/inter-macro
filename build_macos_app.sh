#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
pip install -r requirements.txt
pip install pyinstaller

pyinstaller \
  --noconfirm \
  --windowed \
  --name "InterMacro" \
  --add-data "ticket_watch.py:." \
  ticket_gui.py

echo "Built app: dist/InterMacro.app"
