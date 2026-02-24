#!/bin/bash
# One-command installer for recover-jerry
set -e

echo ""
echo "==================================="
echo "  recover-jerry installer"
echo "==================================="
echo ""

# 1. Check for Homebrew, install if missing
if ! command -v brew &>/dev/null; then
    echo "Installing Homebrew (macOS package manager)..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # Add brew to PATH for Apple Silicon Macs
    if [ -f /opt/homebrew/bin/brew ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
fi

# 2. Install Python 3.11+ if needed
NEED_PYTHON=false
if command -v python3 &>/dev/null; then
    PY_VERSION=$(python3 -c "import sys; print(sys.version_info[:2] >= (3, 11))" 2>/dev/null || echo "False")
    if [ "$PY_VERSION" != "True" ]; then
        NEED_PYTHON=true
    fi
else
    NEED_PYTHON=true
fi

if [ "$NEED_PYTHON" = true ]; then
    echo "Installing Python 3.11..."
    brew install python@3.11
fi

# 3. Clone the repo
INSTALL_DIR="$HOME/recover-jerry"
if [ -d "$INSTALL_DIR" ]; then
    echo "Updating existing install..."
    git -C "$INSTALL_DIR" pull
else
    echo "Downloading recover-jerry..."
    git clone https://github.com/jayKrakerz/recover-jerry.git "$INSTALL_DIR"
fi

# 4. Install Python dependencies
echo "Installing dependencies..."
pip3 install -r "$INSTALL_DIR/requirements.txt"

# 5. Optional: install testdisk for PhotoRec file carving
if ! command -v photorec &>/dev/null; then
    echo "Installing testdisk (for advanced file carving)..."
    brew install testdisk
fi

# 6. Launch
echo ""
echo "==================================="
echo "  Starting recover-jerry..."
echo "==================================="
echo ""
echo "A browser window will open shortly."
echo "To run again later, paste this into Terminal:"
echo "  ~/recover-jerry/scripts/launch.sh"
echo ""

bash "$INSTALL_DIR/scripts/launch.sh"
