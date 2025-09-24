#!/bin/bash
set -euo pipefail

pause_on_error() {
  local exit_code=$?
  if [ "$exit_code" -ne 0 ]; then
    echo ""
    echo "Launcher exited with errors (code $exit_code)."
    read -p "Press Enter to close..." _
  fi
}

trap 'pause_on_error' EXIT

# Ensure script runs from its directory so relative paths work
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Find a usable Python interpreter
if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  echo "Python 3 is not installed. Please install Python 3 from https://www.python.org/downloads/."
  read -p "Press Enter to close..." _
  exit 1
fi

# Ensure the selected interpreter has Tk support
if ! "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
import tkinter
PY
then
  echo "The Python interpreter at $(command -v "$PYTHON_BIN") does not include Tk GUI support."
  echo "Install the latest Python distribution from https://www.python.org/downloads/ and try again."
  read -p "Press Enter to close..." _
  exit 1
fi

VENV_DIR="$SCRIPT_DIR/.venv"
PYTHON_VENV="$VENV_DIR/bin/python"

# Create the virtual environment if it does not yet exist
if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtual environment..."
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# Upgrade pip and install dependencies
"$PYTHON_VENV" -m pip install --upgrade pip
"$PYTHON_VENV" -m pip install -r "$SCRIPT_DIR/requirements.txt"

# Launch the GUI application
"$PYTHON_VENV" "$SCRIPT_DIR/GUI.py"
