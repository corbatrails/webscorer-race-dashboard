#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Create venv if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    if ! python3 -c "import ensurepip" 2>/dev/null; then
        echo "ERROR: python3-venv is not installed. Install it with:"
        echo "    sudo apt install python3-venv"
        exit 1
    fi
    python3 -m venv venv
fi

# Activate venv and install deps
source venv/bin/activate
pip install -q -r requirements.txt

# Download pinned JS vendor dependencies
VENDOR_DIR="static/vendor"
if command -v python3 &>/dev/null; then PY=python3; else PY=python; fi
$PY -c "
import json, urllib.request, os
vendor_dir = '$VENDOR_DIR'
with open(os.path.join(vendor_dir, 'vendor.json')) as f:
    deps = json.load(f)
for name, info in deps.items():
    dest = os.path.join(vendor_dir, info['file'])
    if not os.path.exists(dest):
        print(f'Downloading {name} v{info[\"version\"]}...')
        urllib.request.urlretrieve(info['url'], dest)
"

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
