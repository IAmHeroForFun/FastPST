#!/usr/bin/env bash
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

export QT_LOGGING_RULES="qt.xkb.compose=false;qt.qpa.*=false"

if [ -f ".venv/bin/python" ]; then
    exec .venv/bin/python main.py "$@"
else
    exec python3 main.py "$@"
fi
