# Paper Crawler Web UI Launcher
# Right-click -> "Run with PowerShell" (or double-click if .ps1 is associated)
# Then open http://127.0.0.1:8501 in browser
# To stop: right-click stop.ps1 -> "Run with PowerShell"

$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$streamlitExe = Join-Path $projectRoot ".venv\Scripts\streamlit.exe"

if (-not (Test-Path $streamlitExe)) {
    Write-Host "ERROR: streamlit.exe not found." -ForegroundColor Red
    Write-Host "Please run: pip install -r requirements.txt"
    Read-Host "Press Enter to exit"
    exit 1
}

# Environment variables
$env:STREAMLIT_TELEMETRY_OPT_OUT = "1"
$env:STREAMLIT_BROWSER_GATHERUSAGESTATS = "false"
$env:STREAMLIT_SERVER_ADDRESS = "127.0.0.1"
$env:STREAMLIT_SERVER_PORT = "8501"
$env:STREAMLIT_SERVER_HEADLESS = "true"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Starting Paper Crawler Web UI..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "When ready, open in your browser:" -ForegroundColor Yellow
Write-Host "  http://127.0.0.1:8501" -ForegroundColor Yellow
Write-Host ""
Write-Host "Press Ctrl+C to stop" -ForegroundColor Gray
Write-Host ""

# Start streamlit (hidden window, 在项目根目录运行)
Start-Process -FilePath $streamlitExe -ArgumentList "run", "$projectRoot\web\streamlit_app.py" -WorkingDirectory $projectRoot -WindowStyle Hidden

Read-Host "Service started. Press Enter to close this window (service keeps running in background)"
