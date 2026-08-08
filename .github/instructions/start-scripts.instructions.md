---
description: "Enforce sync between start.sh and start.ps1 startup scripts"
globs: ["start.sh", "start.ps1"]
alwaysApply: false
---

# Start Script Sync Rule

`start.sh` (bash/Linux) and `start.ps1` (PowerShell/Windows) must always have equivalent behavior. When either script is modified, the other MUST be updated to match in the same commit.

Both scripts do the same thing:
1. cd to script directory
2. Create Python venv if missing
3. Install deps from requirements.txt
4. Validate .env exists
5. Start Flask server (with optional --kiosk flag for Chromium)
