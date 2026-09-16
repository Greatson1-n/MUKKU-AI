# MUKKU.AI 1-Click Startup Script for Windows PowerShell
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "         Starting MUKKU.AI Local Assistant      " -ForegroundColor Green
Write-Host "      Powered by Ollama + Qwen2.5 3B Instruct   " -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan

$root = $PSScriptRoot

# 1. Start Backend in Background
Write-Host "`n[1/2] Launching Backend API server on http://127.0.0.1:8000..." -ForegroundColor Yellow
$backendProcess = Start-Process -FilePath "$root\.venv\Scripts\python.exe" -ArgumentList "$root\backend\run.py" -WorkingDirectory "$root" -PassThru

Start-Sleep -Seconds 2

# 2. Start Frontend Dev Server
Write-Host "[2/2] Launching Frontend UI on http://localhost:5173..." -ForegroundColor Yellow
Set-Location -Path "$root\frontend"
npm.cmd run dev

# Stop backend when user exits
Stop-Process -Id $backendProcess.Id -Force
