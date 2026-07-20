Clear-Host

Write-Host "--- [FALCON] Starting Services ---" -ForegroundColor Cyan
Write-Host "--- made by ranuka. :3 ---" -ForegroundColor Magenta

# 1. Activate the environment
Write-Host "[1/3] Activating environment..." -ForegroundColor Yellow
& "C:\Users\ranuk\Downloads\Sprout\.sprout\Scripts\Activate.ps1"

# 2. Start Flask in a new window
Write-Host "[2/3] Launching Flask Server..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "python C:\Users\ranuk\Downloads\Sprout\app.py"

# 3. Start ngrok in a new window
Write-Host "[3/3] Launching ngrok Tunnel..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "ngrok http 5000"

Write-Host "--- All systems active! ---" -ForegroundColor Green