#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Create venv if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate venv and install deps
source venv/bin/activate
pip install -q -r requirements.txt

# Check for .env
if [ ! -f ".env" ]; then
    echo "ERROR: .env file not found. Copy .env.example to .env and fill in your credentials."
    exit 1
fi

echo "Starting Race Dashboard..."

if [ "$1" = "--kiosk" ]; then
    # Start Flask in background
    python app.py &
    FLASK_PID=$!
    sleep 2

    # Launch Chromium in kiosk mode
    chromium-browser --kiosk --noerrdialogs --disable-infobars --no-first-run \
        --disable-session-crashed-bubble --disable-translate \
        http://localhost:5000 &

    echo "Dashboard running in kiosk mode. Press Ctrl+C to stop."
    trap "kill $FLASK_PID 2>/dev/null" EXIT
    wait $FLASK_PID
else
    python app.py
fi
