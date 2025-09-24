#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_CMD=""

if command -v python3 >/dev/null 2>&1; then
  PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_CMD="python"
else
  echo "Python 3 is required but was not found. Install Python from https://www.python.org/downloads/."
  read -r -p "Press Enter to exit..." _
  exit 1
fi

VENV_DIR="$SCRIPT_DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtual environment..."
  "$PYTHON_CMD" -m venv "$VENV_DIR" || {
    echo "Failed to create virtual environment.";
    read -r -p "Press Enter to exit..." _;
    exit 1;
  }
fi

"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -r "$SCRIPT_DIR/requirements.txt"
"$VENV_DIR/bin/python" "$SCRIPT_DIR/GUI.py"
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
  echo "Application exited with code $EXIT_CODE."
fi
read -r -p "Press Enter to exit..." _
exit $EXIT_CODE
