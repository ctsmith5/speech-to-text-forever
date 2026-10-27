#!/bin/bash
# macOS launcher: double-click in Finder
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
    echo "First run: setting up..."
    python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt
fi
.venv/bin/python voicechat.py
