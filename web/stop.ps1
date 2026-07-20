# Stop Paper Crawler Web UI
# Right-click -> "Run with PowerShell"

Get-Process -Name "streamlit" -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -like "*streamlit*" } | Stop-Process -Force

Write-Host "Paper Crawler Web UI stopped." -ForegroundColor Green
Read-Host "Press Enter to exit"
