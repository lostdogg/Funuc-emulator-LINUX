#!/usr/bin/env bash
# install.sh – Install all dependencies required by the Funuc CNC Emulator
# on Linux Mint (or any Ubuntu/Debian-based system).
#
# Usage:
#   chmod +x install.sh
#   ./install.sh

set -euo pipefail

PYTHON_MIN_MAJOR=3
PYTHON_MIN_MINOR=8

echo "=== Funuc CNC Emulator – Linux Mint Installer ==="
echo

# -----------------------------------------------------------------------
# 1. Verify Python 3.8+
# -----------------------------------------------------------------------
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 is not installed."
    echo "Run:  sudo apt install python3"
    exit 1
fi

PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)

if [ "$PY_MAJOR" -lt "$PYTHON_MIN_MAJOR" ] || \
   { [ "$PY_MAJOR" -eq "$PYTHON_MIN_MAJOR" ] && [ "$PY_MINOR" -lt "$PYTHON_MIN_MINOR" ]; }; then
    echo "ERROR: Python ${PYTHON_MIN_MAJOR}.${PYTHON_MIN_MINOR}+ is required (found $PY_VER)."
    exit 1
fi
echo "✓ Python $PY_VER found."

# -----------------------------------------------------------------------
# 2. Install system dependencies (tkinter)
# -----------------------------------------------------------------------
echo
echo "Installing system dependencies (requires sudo) …"
sudo apt-get update -q
sudo apt-get install -y python3-tk

echo "✓ python3-tk installed."

# -----------------------------------------------------------------------
# 3. Make the launcher executable
# -----------------------------------------------------------------------
if [ -f "run_emulator.py" ]; then
    chmod +x run_emulator.py
    echo "✓ run_emulator.py is now executable."
fi

echo
echo "=== Installation complete ==="
echo
echo "To launch the emulator:"
echo "  python3 run_emulator.py"
echo "  – or –"
echo "  ./run_emulator.py"
