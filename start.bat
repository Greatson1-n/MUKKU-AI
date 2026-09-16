@echo off
echo ===============================================
echo          Starting MUKKU.AI Local Assistant     
echo       Powered by Ollama + Qwen2.5 3B Instruct  
echo ===============================================

set ROOT=%~dp0

echo [1/2] Starting Backend Server...
start "MUKKU.AI Backend" "%ROOT%.venv\Scripts\python.exe" "%ROOT%backend\run.py"

timeout /t 2 /nobreak >nul

echo [2/2] Starting Frontend Server...
cd /d "%ROOT%frontend"
npm.cmd run dev
