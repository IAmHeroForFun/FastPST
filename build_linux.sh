#!/usr/bin/env bash
set -e

echo "==================================================="
echo "FastPST - Linux Standalone Binary Builder"
echo "==================================================="

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Ensure virtualenv exists
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

echo "Installing/verifying dependencies..."
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

echo ""
echo "Building FastPST standalone Linux binary..."
.venv/bin/python build_exe.py

echo ""
echo "==================================================="
echo "[SUCCESS] Build completed!"
echo "Binary location: $PROJECT_DIR/dist/FastPST"
echo "You can copy 'dist/FastPST' into any folder with .pst/.ost files and run it."
echo "==================================================="
