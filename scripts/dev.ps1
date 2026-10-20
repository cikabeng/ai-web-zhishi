# 一键启动开发环境：后端 :8000 + 前端 :5173
# 用法： .\scripts\dev.ps1
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'

if (-not (Test-Path $python)) {
    Write-Host "未找到虚拟环境：$python" -ForegroundColor Red
    Write-Host "请先执行： python -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt"
    exit 1
}

Write-Host "[1/2] 后端 -> http://127.0.0.1:8000  (文档 /api/docs)" -ForegroundColor Cyan
Start-Process -FilePath $python `
    -ArgumentList '-m', 'uvicorn', 'app.main:app', '--reload', '--port', '8000' `
    -WorkingDirectory (Join-Path $root 'backend')

Write-Host "[2/2] 前端 -> http://localhost:5173" -ForegroundColor Cyan
Start-Process -FilePath 'npm.cmd' -ArgumentList 'run', 'dev' -WorkingDirectory (Join-Path $root 'frontend')

Write-Host "两个窗口已启动，关闭窗口即停止服务。" -ForegroundColor Green
