@echo off
setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

where python >nul 2>&1
if errorlevel 1 (
  echo Python 3 is required but was not found. Install Python from https://www.python.org/downloads/.
  echo.
  pause
  exit /b 1
)

set "VENV_DIR=%SCRIPT_DIR%\.venv"
if not exist "%VENV_DIR%\Scripts\python.exe" (
  echo Creating virtual environment...
  python -m venv "%VENV_DIR%"
  if errorlevel 1 (
    echo Failed to create virtual environment.
    echo.
    pause
    exit /b 1
  )
)

set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
set "TEMP_TCL=%TEMP%\tcldir_%RANDOM%.txt"
"%VENV_PY%" -c "import os, sys; print(os.path.join(sys.base_prefix, 'tcl', 'tcl8.6'))" > "%TEMP_TCL%"
if errorlevel 1 goto :tcl_missing
set /p TCL_DIR=<"%TEMP_TCL%"
del "%TEMP_TCL%" >nul 2>&1
if not exist "%TCL_DIR%\init.tcl" goto :tcl_missing
set "TCL_LIBRARY=%TCL_DIR%"

set "TEMP_TK=%TEMP%\tkdir_%RANDOM%.txt"
"%VENV_PY%" -c "import os, sys; print(os.path.join(sys.base_prefix, 'tcl', 'tk8.6'))" > "%TEMP_TK%"
if errorlevel 1 goto :tcl_missing
set /p TK_DIR=<"%TEMP_TK%"
del "%TEMP_TK%" >nul 2>&1
if not exist "%TK_DIR%" goto :tcl_missing
set "TK_LIBRARY=%TK_DIR%"

"%VENV_PY%" -m pip install --upgrade pip
if errorlevel 1 goto :pip_error
"%VENV_PY%" -m pip install -r "%SCRIPT_DIR%\requirements.txt"
if errorlevel 1 goto :pip_error
"%VENV_PY%" "%SCRIPT_DIR%\GUI.py"
set EXIT_CODE=%ERRORLEVEL%
if not %EXIT_CODE%==0 (
  echo Application exited with code %EXIT_CODE%.
)

echo.
pause
exit /b %EXIT_CODE%

:pip_error
echo Failed to install required packages.
echo.
pause
exit /b 1

:tcl_missing
echo Tcl/Tk runtime was not found in the base Python installation.
echo Re-run the Python installer and ensure "tcl/tk and IDLE" is selected.
echo.
pause
exit /b 1
