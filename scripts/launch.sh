#!/bin/bash
# Launch recover-jerry server and open browser

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

PORT="${JERRY_PORT:-8787}"
HOST="${JERRY_HOST:-127.0.0.1}"

echo "recover-jerry: starting on http://${HOST}:${PORT}"
echo ""

# Check Python version
python3 -c "import sys; assert sys.version_info >= (3, 11), 'Python 3.11+ required'" 2>/dev/null || {
    echo "Error: Python 3.11+ is required"
    exit 1
}

# Install dependencies if needed
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo "Installing dependencies..."
    pip3 install -r requirements.txt
fi

# Open browser after a short delay
(sleep 2 && open "http://${HOST}:${PORT}") &

# Start server
python3 -m recover_jerry
