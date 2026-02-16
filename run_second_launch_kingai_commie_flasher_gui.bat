@echo off
REM ═══════════════════════════════════════════════════════════════════
REM  KingAi VY V6 L36 Commo Flasher — GUI Launcher
REM  Make sure you ran run_me_first_dependancie_installer.bat first!
REM ═══════════════════════════════════════════════════════════════════
title KingAi Commie Flasher
echo.
echo  ╔═══════════════════════════════════════════════════════╗
echo  ║  KingAi VY V6 L36 Commo Flasher                     ║
echo  ║  Starting GUI...                                     ║
echo  ╚═══════════════════════════════════════════════════════╝
echo.

REM ── Check Python ──
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo  ERROR: Python not found. Run the dependency installer first.
    echo  run_me_first_dependancie_installer.bat
    pause
    exit /b 1
)

REM ── Check pyserial ──
python -c "import serial" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo  WARNING: pyserial not installed. Serial communication will not work.
    echo  Run the dependency installer first or: python -m pip install pyserial
    echo.
)

REM ── Check PySide6 ──
python -c "from PySide6 import QtWidgets" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo  ERROR: PySide6 not installed. GUI mode requires PySide6.
    echo  Run the dependency installer first or: python -m pip install PySide6
    echo.
    echo  You can still use CLI mode:
    echo    python kingai_commie_flasher.py read --port COM3 --output read.bin
    echo    python kingai_commie_flasher.py --help
    echo.
    pause
    exit /b 1
)

REM ── Launch the GUI ──
echo  Launching KingAi Commie Flasher GUI...
echo  (Close this window to stop the application)
echo.

cd /d "%~dp0"
python kingai_commie_flasher.py gui

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo  Application exited with an error (code %ERRORLEVEL%).
    echo  Check the logs/ folder for details.
    pause
)