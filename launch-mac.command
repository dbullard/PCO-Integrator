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
  if ! "$PYTHON_CMD" -m venv "$VENV_DIR"; then
    echo "Failed to create virtual environment."
    read -r -p "Press Enter to exit..." _
    exit 1
  fi
fi

VENV_PY="$VENV_DIR/bin/python"
set +e
TCL_INFO="$($VENV_PY - <<'PY'
import os
import sys
try:
    import tkinter
except Exception as exc:  # pragma: no cover
    print(exc, file=sys.stderr)
    sys.exit(1)
base = os.path.dirname(os.path.dirname(os.path.realpath(tkinter.__file__)))
print(os.path.join(base, 'tcl8.6'))
print(os.path.join(base, 'tk8.6'))
PY
)"
STATUS=$?
set -e
if [ $STATUS -ne 0 ]; then
  echo "Could not locate Tcl/Tk runtime from the active Python installation."
  echo "Reinstall Python and ensure the \"tcl/tk and IDLE\" option is selected."
  read -r -p "Press Enter to exit..." _
  exit 1
fi

TCL_DIR="$(printf '%s' "$TCL_INFO" | sed -n '1p')"
TK_DIR="$(printf '%s' "$TCL_INFO" | sed -n '2p')"
if [ ! -f "$TCL_DIR/init.tcl" ] || [ ! -d "$TK_DIR" ]; then
  echo "Tcl/Tk runtime was not found in the base Python installation."
  echo "Reinstall Python and ensure the \"tcl/tk and IDLE\" option is selected."
  read -r -p "Press Enter to exit..." _
  exit 1
fi
export TCL_LIBRARY="$TCL_DIR"
export TK_LIBRARY="$TK_DIR"

"$VENV_PY" -m pip install --upgrade pip
"$VENV_PY" -m pip install -r "$SCRIPT_DIR/requirements.txt"
"$VENV_PY" "$SCRIPT_DIR/GUI.py"
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
  echo "Application exited with code $EXIT_CODE."
fi
read -r -p "Press Enter to exit..." _
exit $EXIT_CODE
