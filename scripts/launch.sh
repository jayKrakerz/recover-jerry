#!/bin/bash
# Launch recover-jerry server and open browser

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

PORT="${JERRY_PORT:-8787}"
HOST="${JERRY_HOST:-127.0.0.1}"

# Find a Python 3.11+ binary
find_python() {
    # Check versioned binary first (what brew install python@3.11 provides)
    for cmd in python3.13 python3.12 python3.11; do
        if command -v "$cmd" &>/dev/null; then
            echo "$cmd"
            return
        fi
    done
    # Check if system python3 is 3.11+
    if command -v python3 &>/dev/null; then
        if python3 -c "import sys; assert sys.version_info >= (3, 11)" 2>/dev/null; then
            echo "python3"
            return
        fi
    fi
    # Check common Homebrew paths
    for prefix in /opt/homebrew /usr/local; do
        for cmd in python3.13 python3.12 python3.11 python3; do
            if [ -x "$prefix/bin/$cmd" ]; then
                if "$prefix/bin/$cmd" -c "import sys; assert sys.version_info >= (3, 11)" 2>/dev/null; then
                    echo "$prefix/bin/$cmd"
                    return
                fi
            fi
        done
    done
    return 1
}

PYTHON=$(find_python) || {
    echo "Error: Python 3.11+ is required. Install it with: brew install python@3.11"
    exit 1
}

echo "recover-jerry: starting on http://${HOST}:${PORT}"
echo "  Using: $PYTHON ($($PYTHON --version))"
echo ""

# Install dependencies if needed
if ! "$PYTHON" -c "import fastapi" 2>/dev/null; then
    echo "Installing dependencies..."
    "$PYTHON" -m pip install -r requirements.txt
fi

# Open browser after a short delay
(sleep 2 && open "http://${HOST}:${PORT}") &

# Start server
"$PYTHON" -m recover_jerry
