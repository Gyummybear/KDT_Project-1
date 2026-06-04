@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" run.py >> server.cmd.log 2>&1
