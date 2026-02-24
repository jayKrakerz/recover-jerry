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

# 2. Find a Python 3.11+ binary, or install one
find_python() {
    for cmd in python3.13 python3.12 python3.11; do
        if command -v "$cmd" &>/dev/null; then
            echo "$cmd"
            return
        fi
    done
    if command -v python3 &>/dev/null; then
        if python3 -c "import sys; assert sys.version_info >= (3, 11)" 2>/dev/null; then
            echo "python3"
            return
        fi
    fi
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
    echo "Installing Python 3.11..."
    brew install python@3.11
    # Find it again after install
    PYTHON=$(find_python) || {
        echo "Error: Python installation failed. Try: brew install python@3.11"
        exit 1
    }
}

echo "Using: $PYTHON ($($PYTHON --version))"

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
"$PYTHON" -m pip install -r "$INSTALL_DIR/requirements.txt"

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
