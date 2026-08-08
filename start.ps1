#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# Create venv if it doesn't exist
if (-not (Test-Path "venv")) {
  Write-Host "Creating Python virtual environment..."
  python -m venv venv
}

# Activate venv and install deps
& .\venv\Scripts\Activate.ps1
pip install -q -r requirements.txt

# Check for .env
if (-not (Test-Path ".env")) {
  Write-Error "ERROR: .env file not found. Copy .env.example to .env and fill in your credentials."
  exit 1
}

Write-Host "Starting Race Dashboard..."

if ($args[0] -eq "--kiosk") {
  # Start Flask in background
  $flask = Start-Process -FilePath python -ArgumentList "app.py" -PassThru -NoNewWindow
  Start-Sleep -Seconds 2

  # Launch Chromium in kiosk mode
  $chromium = Start-Process -FilePath "chromium-browser" -ArgumentList @(
    "--kiosk", "--noerrdialogs", "--disable-infobars", "--no-first-run",
    "--disable-session-crashed-bubble", "--disable-translate",
    "http://localhost:5000"
  ) -PassThru

  Write-Host "Dashboard running in kiosk mode. Press Ctrl+C to stop."
  try {
    $flask.WaitForExit()
  }
  finally {
    if (-not $flask.HasExited) { $flask.Kill() }
    if ($chromium -and -not $chromium.HasExited) { $chromium.Kill() }
  }
}
else {
  python app.py
}
