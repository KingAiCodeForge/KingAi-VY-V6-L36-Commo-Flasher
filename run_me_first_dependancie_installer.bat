@echo off
setlocal
pushd "%~dp0" || exit /b 1
if defined KINGAI_FLASHER_PYTHON (
    set "FL_PYTHON=%KINGAI_FLASHER_PYTHON%"
) else (
    set "FL_PYTHON=python"
)
"%FL_PYTHON%" -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python 3.10 or newer is required. Set KINGAI_FLASHER_PYTHON to its executable path.
    popd
    exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
    "%FL_PYTHON%" -m venv ".venv"
    if errorlevel 1 goto :failed
)
".venv\Scripts\python.exe" -m pip install ".[gui,serial]"
if errorlevel 1 goto :failed
".venv\Scripts\python.exe" -m kingai_commie_flasher --help
if errorlevel 1 goto :failed
echo Installation complete. This is experimental software; physical programming remains unqualified.
popd
exit /b 0
:failed
echo ERROR: Installation failed. Review the error above; no successful install is claimed.
popd
exit /b 1
