@echo off
setlocal
if defined KINGAI_FLASHER_PYTHON (
    set "FL_PYTHON=%KINGAI_FLASHER_PYTHON%"
) else (
    set "FL_PYTHON=%~dp0.venv\Scripts\python.exe"
)
if not exist "%FL_PYTHON%" (
    echo ERROR: Python environment not found. Run run_me_first_dependancie_installer.bat first.
    echo Or set KINGAI_FLASHER_PYTHON to the full Python executable path.
    exit /b 1
)
"%FL_PYTHON%" "%~dp0kingai_commie_flasher.py" gui
exit /b %ERRORLEVEL%
