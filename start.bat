@echo off
cd /d "%~dp0"
if not exist .venv (
    echo First run: setting up...
    py -m venv .venv
    .venv\Scripts\python -m pip install -r requirements.txt
)
.venv\Scripts\python voicechat.py
pause
