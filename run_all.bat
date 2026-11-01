@echo off
title DDSS - Dawood Data Science Society Launcher
echo ===========================================================================
echo   Starting DDSS - Dawood Data Science Society System
echo   FastAPI (Port 8000) ^& Streamlit (Port 8501)
echo ===========================================================================

cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

%PYTHON_EXE% run_all.py
pause
