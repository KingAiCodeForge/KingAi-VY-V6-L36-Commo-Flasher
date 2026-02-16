@echo off
REM ═══════════════════════════════════════════════════════════════════
REM  KingAi VY V6 L36 Commo Flasher — Dependency Installer
REM  Run this FIRST before launching the flash tool.
REM ═══════════════════════════════════════════════════════════════════
title KingAi Commie Flasher - Dependency Installer
echo.
echo  ╔═══════════════════════════════════════════════════════╗
echo  ║  KingAi VY V6 L36 Commo Flasher                     ║
echo  ║  Dependency Installer                                ║
echo  ╚═══════════════════════════════════════════════════════╝
echo.

REM ── Check Python is installed ──
echo [1/4] Checking for Python...
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo  ERROR: Python is not installed or not in PATH.
    echo  Download Python 3.10+ from https://www.python.org/downloads/
    echo  Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo  Found Python %PYVER%
echo.

REM ── Check pip is available ──
echo [2/4] Checking for pip...
python -m pip --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo  ERROR: pip is not available. Installing pip...
    python -m ensurepip --upgrade
    if %ERRORLEVEL% NEQ 0 (
        echo  ERROR: Could not install pip. Please install manually.
        pause
        exit /b 1
    )
)
echo  pip is available.
echo.

REM ── Install required packages ──
echo [3/4] Installing required packages...
echo.
echo  Installing pyserial (ALDL serial communication)...
python -m pip install pyserial --quiet
if %ERRORLEVEL% NEQ 0 (
    echo  WARNING: pyserial install failed. CLI mode may not work with real hardware.
) else (
    echo  pyserial installed OK.
)
echo.

echo  Installing PySide6 (GUI framework)...
python -m pip install PySide6 --quiet
if %ERRORLEVEL% NEQ 0 (
    echo  WARNING: PySide6 install failed. GUI mode will not be available.
    echo  CLI mode will still work. You can try: python -m pip install PySide6
) else (
    echo  PySide6 installed OK.
)
echo.

REM ── Optional packages ──
echo [4/4] Installing optional packages...
echo.
echo  Installing ftd2xx (FTDI D2XX transport - optional, lower latency)...
python -m pip install ftd2xx --quiet
if %ERRORLEVEL% NEQ 0 (
    echo  NOTE: ftd2xx not installed. This is optional - PySerial transport works fine.
) else (
    echo  ftd2xx installed OK.
)
echo.

echo  Installing rich (colored console output - optional)...
python -m pip install rich --quiet
if %ERRORLEVEL% NEQ 0 (
    echo  NOTE: rich not installed. Logging will use standard formatting.
) else (
    echo  rich installed OK.
)
echo.

REM ── Verify installation ──
echo ═══════════════════════════════════════════════════════════
echo  Verification:
echo ═══════════════════════════════════════════════════════════
python -c "import serial; print('  pyserial:  OK (v' + serial.__version__ + ')')" 2>nul || echo   pyserial:  NOT INSTALLED
python -c "from PySide6 import QtWidgets; print('  PySide6:   OK')" 2>nul || echo   PySide6:   NOT INSTALLED (GUI unavailable, CLI still works)
python -c "import ftd2xx; print('  ftd2xx:    OK')" 2>nul || echo   ftd2xx:    NOT INSTALLED (optional)
python -c "from rich import print; print('  rich:      OK')" 2>nul || echo   rich:      NOT INSTALLED (optional)
echo.

REM ── Quick syntax check on the main file ──
echo  Checking kingai_commie_flasher.py syntax...
python -c "import py_compile; py_compile.compile('kingai_commie_flasher.py', doraise=True)" 2>nul
if %ERRORLEVEL% EQU 0 (
    echo  Syntax check: PASS
) else (
    echo  Syntax check: FAIL - there may be an issue with the source file.
)
echo.

echo ═══════════════════════════════════════════════════════════
echo  Done! You can now run:
echo    run_second_launch_kingai_commie_flasher_gui.bat
echo  Or use CLI mode:
echo    python kingai_commie_flasher.py --help
echo ═══════════════════════════════════════════════════════════
echo.
pause