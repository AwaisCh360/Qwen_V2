#!/usr/bin/env bash
# Qwen HTTP Account Maker Launcher
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

# Check Python environment
if [ -d "../captcha-solver/.venv" ]; then
    PYTHON_BIN="../captcha-solver/.venv/bin/python"
elif [ -d "venv" ]; then
    PYTHON_BIN="venv/bin/python"
else
    PYTHON_BIN="python3"
fi

# Instant startup with embedded high-speed solver engine
echo "⚡ Starting Qwen HTTP Account Maker (High-Speed Mode)..."

# Run the account creator
exec "$PYTHON_BIN" main.py "$@"
