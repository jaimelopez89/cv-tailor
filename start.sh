#!/bin/bash
# CV Tailor — start local web server
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate venv if it exists
if [ -d "venv" ]; then
  source venv/bin/activate
fi

echo ""
echo "  CV Tailor"
echo "  ─────────────────────────────────────"
echo "  Open in browser: http://localhost:8080"
echo "  Stop with:       Ctrl+C"
echo ""

uvicorn app:app --reload --port 8080 --host 127.0.0.1
