#!/usr/bin/env bash
# Launch script: builds a venv, installs deps, runs the 4-20 mA logger.
# Usage: ./run.sh [extra args passed to logger.py]
#   e.g. ./run.sh --interval 0.5 --duration 600

set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$APP_DIR/.venv"
cd "$APP_DIR"

# --- sanity checks -----------------------------------------------------------
if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 not found. Install it with: sudo apt install -y python3 python3-venv" >&2
    exit 1
fi

if [ ! -e /dev/i2c-1 ] && [ ! -e /dev/i2c-0 ]; then
    echo "WARNING: no /dev/i2c-* device found."
    echo "  Enable I2C with: sudo raspi-config  ->  Interface Options  ->  I2C"
    echo "  Then reboot. (Continuing anyway - use --demo to test without hardware.)"
fi

# --- venv --------------------------------------------------------------------
# --system-site-packages lets the venv reuse an apt-installed matplotlib/numpy
# if one is present, which saves a long build on a Pi.
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment in $VENV_DIR ..."
    python3 -m venv --system-site-packages "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# --- deps --------------------------------------------------------------------
STAMP="$VENV_DIR/.deps-installed"
if [ ! -f "$STAMP" ] || [ requirements.txt -nt "$STAMP" ]; then
    echo "Installing dependencies ..."
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
    touch "$STAMP"
fi

# --- go ----------------------------------------------------------------------
mkdir -p data
exec python logger.py "$@"
