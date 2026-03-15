#!/usr/bin/env python3
"""
kingai_commie_flasher.py — VY V6 In-Car Flash Tool
=====================================================

by Jason King (pcmhacking.net: kingaustraliagg)

Founder — KingAi Pty Ltd

https://github.com/KingAiCodeForge

Was this hard to build? No.
To understand and remember everything — the ALDL protocol, 68HC11 opcodes,
flash chip command sequences, bank switching, seed/key auth, kernel upload,
sector geometry, and the VB.NET source that documented none of it — extremely.

No one looks at the code. Not many people understand Python at this level,
otherwise this would have been done already.

The first open-source flash tool for 68HC11 Delco ECUs.
No other tool — in any language, on any platform — has ever done this publicly.
The only comparable tool is closed-source VB.NET from 2010, distributed as
a Windows binary with no source code available anywhere.

    "AI slop"            — GitHub Issue #1
    "Absolute pure junk" — GitHub Issue #2
    "Learn to tune"      — pcmhacking.net

They said it wouldn't work. They made GitHub accounts just to say that.
None of them posted a single correction, a single wrong address, or ran
a single line of code. Just opinions with zero evidence.

If you can read every topic on pcmhacking.net, remember every detail, and
find a single incorrect address in this code — you can do what I did.
If you can't, stop pretending to be an expert and let the people doing
the actual work get on with it.

Portability:
    If you want to use any of these scripts for other ECUs, do it.
    Change a few addresses and names and most of this works for
    VN, VP, VR, VS, VT, VX, and VY Delco ECUs. The disassembly scripts,
    C compiler, and patching tools across the three VY V6 GitHub repos
    were all built in one month. All open source. All MIT licensed.

Context:
    There is no active open-source development of custom OS or code patches
    for VY V6 L36 ECUs. No public disassembly exists. No patching guides.
    The few people who have done this work (chr0m3, the1, VL400, and others)
    have not published their methods, addresses, or tools. Every existing
    68HC11 disassembler I've tested (15+ tools including dis11, IDA Pro, and
    UDIS) fails to correctly handle the 128KB bank-switched image — missing
    opcodes, wrong byte offsets, no separation of calibration vs code, and
    no auto-labelling from XDF definitions. I built my own.

Flash Chip Compatibility:
    The flash kernel and erase/write/verify routines are not AMD-specific.
    All 128KB × 8-bit NOR flash chips used in these ECUs share the same
    JEDEC standard command protocol — same sector geometry (8 × 16KB),
    same erase sequence (AA→5555, 55→2AAA, 80→5555, 30→sector), same
    byte program sequence (AA→5555, 55→2AAA, A0→5555, data→addr). The
    seed/key security handshake is ECU-level, not chip-level.
    Confirmed compatible:
        AMD Am29F010      (0x01, 0x20) — original factory part
        AMD Am29F040      (0x01, 0xA4) — 512KB variant, same command set
        CAT/OnSemi 28F010 (0x31, 0xB4) — Intel-command compatible

Related Projects:
    https://github.com/KingAiCodeForge/KingAi-VY-V6-L36-Commo-Flasher
    https://github.com/KingAiCodeForge/KingAi_68HC11_C_Compiler
    https://github.com/KingAiCodeForge/kingaustraliagg-vy-l36-060a-enhanced-asm-patches

Contributions welcome — open an issue or PR with corrections, improvements,
or experience patching Delco ECUs.

Target Hardware:
    ECU:    Delco/Delphi 68HC11F1
    OS:     $060A (part 92118883)
    Flash:  AMD 29F010 — 128 KB NOR, 8 × 16 KB sectors
    Bus:    ALDL 8192 baud half-duplex serial

Architecture:
    1:1 Python reimplementation of the OSE Enhanced Flash Tool V1.5.1
    (28,985 lines VB.NET, credits to VL400 and the pcmhacking.net community).
    Single-file script (~5720 lines) with PySide6 GUI + full CLI backend.
    Built-in 68HC11 disassembler (311 opcodes, VY V6 annotations).
    Virtual ECU transport for offline testing with real bin files.

GUI Tabs (8):
    1. Dashboard     — 18 live sensor gauges (RPM, ECT, IAT, TPS, MAF, etc.)
    2. Table Editor  — Calibration table viewer (spark maps, fuel trim, OL AFR, TCC duty)
    3. Disassembler  — Built-in 68HC11 disassembler with VY V6 address annotations
    4. Log           — Real-time event bus / log viewer (active tab during flash ops)
    5. Options       — Connection settings, timing, retry, flash behaviour, logging presets
    6. Custom Flash  — Sector-level brick recovery: select sectors 0-7, custom hex range read/write
    7. Chaos Test    — Automated stress test: read→write→readback→compare loop with configurable cycles
    8. Transport     — PySerial + FTDI D2XX low-level settings, timing offsets, vehicle presets

Menu Bar (31 actions, all wired):
    File       — Load/Save .bin, Save .cal, Exit
    Connection — Connect/Disconnect, Refresh Ports, vEEPROM submenu (Load/Unload/Erase/Export/Info)
    Flash      — Read ECU, Write BIN, Write CAL, Cancel, toggles (auto-checksum/verify/high-speed/echo)
    Tools      — Verify/Fix Checksum, ECU Info, Options
    View       — Dashboard (Ctrl+1) through Transport (Ctrl+8)
    Help       — About

CLI Commands (7):
    gui, read, write, datalog, info, checksum, ports

Safety Features (implemented 2026-02-18):
    - UI lockout during flash ops (all tabs except Log disabled)
    - Flash-menu toggles locked during operations
    - File menu locked during operations
    - Disconnect during WRITE requires explicit danger confirmation dialog
    - Window close blocked entirely during WRITE operations
    - Reads can be cancelled/disconnected safely anytime

Transport Reliability (hardened 2026-02-18):
    - RX buffer flush + 50ms inter-retry delay between all retry attempts
    - Write chunk retries flush bus before re-sending
    - Per-block read retries (3x) with bus flush before skipping
    - Retry counting fixed (no more retry 11/10)

Test Suite (275 tests, all passing as of 2026-02-18):
    - test_kingai_commie_flasher.py — 118 tests (protocol, framing, transport, kernel, vECU, events)
    - test_gui_functions.py         — 157 tests (GUI widgets, new tabs, view actions, FlashWorker setup)
    - test_vecu.py                  — 5 tests (virtual ECU integration with real bin files)

Status:
    VIRTUAL TESTING ONLY — not yet tested on real hardware.
    All protocol paths verified against decompiled OSE source.
    Tested with real 128KB bin files via Virtual ECU transport.
    First successful virtual read/write session completed 2026-02-17.
    If you test on hardware before I do, open an issue with results.

WARNING:
    Flashing your ECU carries risk. You are solely responsible for any
    damage to your vehicle or PCM. Always keep a known-good backup bin
    before flashing. Do NOT disconnect power during a write operation.

Requires: Python 3.10+, pyserial
Optional: PySide6 (GUI), ftd2xx (D2XX transport)
 
So scripts on my githubs are not ai slop. why not try reading a cal r bin. 
if the software freezes just like ose flashtool your lucky cause we have 
a logging system and can correct any of the 8 banks individually with my
tool when i code this in, i have it outside will upstream the working code into this.
a resume tab will be added, maybe a repair tab. that has a choice of any of the banks, 
then can even resume or go back and overwrite then continue where the number you punch in to the box in the frontend, simple. will work.

MIT License

Copyright (c) 2026 Jason King (pcmhacking.net: kingaustraliagg)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""




# ═══════════════════════════════════════════════════════════════════════
# SECTION 0 — IMPORTS & GLOBALS
# ═══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import sys
import os
import time
import struct
import hashlib
import logging
import json
import argparse
import threading
import traceback
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, fields
from enum import IntEnum, Enum, auto
from typing import Optional, Callable, List, Tuple, Dict, Any
from collections import deque
from io import BytesIO

# Serial — try pyserial first, fallback stub
try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

# FTDI D2XX — optional
try:
    import ftd2xx
    D2XX_AVAILABLE = True
except ImportError:
    D2XX_AVAILABLE = False

# GUI — PySide6 (optional, CLI works without it)
GUI_AVAILABLE = False
_GUI_IMPORT_ERROR: str = ""
try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QGridLayout, QFormLayout, QLabel, QPushButton, QComboBox, QProgressBar,
        QTextEdit, QFileDialog, QTabWidget, QGroupBox, QCheckBox,
        QSpinBox, QDoubleSpinBox, QTableWidget, QTableWidgetItem,
        QStatusBar, QToolBar, QMessageBox, QSplitter, QFrame, QScrollArea,
        QHeaderView, QMenu, QMenuBar, QSizePolicy, QLineEdit,
    )
    from PySide6.QtCore import (
        Qt, QTimer, Signal, Slot, QThread, QObject, QMutex, QMutexLocker,
    )
    from PySide6.QtGui import (
        QColor, QFont, QAction, QIcon, QPalette, QBrush, QPainter,
    )
    GUI_AVAILABLE = True
except Exception as _e:
    _GUI_IMPORT_ERROR = f"{type(_e).__name__}: {_e}"

# ── Version & Metadata ──
__version__ = "0.1.0"
__app_name__ = "KingAI Commie Flasher"
__target_ecm__ = "VY V6 $060A (92118883)"

# ── Logging Setup (merged from log_setup.py) ──
LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Rich logging handler (optional — install `rich` for colored console output)
try:
    from rich.logging import RichHandler
    RICH_LOGGING_AVAILABLE = True
except ImportError:
    RICH_LOGGING_AVAILABLE = False


def setup_logging(
    name: str = "flasher",
    level: int = logging.DEBUG,
    console_level: int = logging.WARNING,
    log_dir: Optional[Path] = None,
    rich_console: bool = True,
) -> logging.Logger:
    """
    Configure and return a logger.

    Args:
        name:          Logger name and log-file prefix.
        level:         Root level (DEBUG captures everything to file).
        console_level: Level for console/terminal output (WARNING+ by
                       default so Rich panels/tables aren't cluttered).
        log_dir:       Override log directory (default: logs/ next to this file).
        rich_console:  Use Rich handler for console if available.

    Returns:
        Configured ``logging.Logger`` instance.

    Log files: ``<log_dir>/<name>_YYYYMMDD_HHMMSS.log``
    """
    log_dir = log_dir or LOG_DIR
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(level)

    # ── File handler: captures everything (DEBUG+) ──
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"{name}_{ts}.log"
    file_fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(funcName)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    fh = logging.FileHandler(str(log_file), encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(file_fmt)
    logger.addHandler(fh)

    # ── Console handler: only important stuff (WARNING+ default) ──
    if rich_console and RICH_LOGGING_AVAILABLE:
        ch = RichHandler(
            level=console_level,
            show_time=True,
            show_path=False,
            markup=True,
            rich_tracebacks=True,
            tracebacks_show_locals=True,
        )
    else:
        ch = logging.StreamHandler(sys.stderr)
        ch.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-7s | %(message)s", datefmt="%H:%M:%S",
        ))
    ch.setLevel(console_level)
    logger.addHandler(ch)

    # Startup banner (file only)
    logger.info("=" * 60)
    logger.info("Logger initialized: %s", name)
    logger.info("Log file: %s", log_file)
    logger.info("Console level: %s", logging.getLevelName(console_level))
    logger.info("=" * 60)

    return logger

log = setup_logging()


# ═══════════════════════════════════════════════════════════════════════
# SECTION 1 — CONSTANTS & PROTOCOL DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════

class DeviceID(IntEnum):
    """ALDL device IDs for Holden/GM ECUs."""
    VR_F4 = 0xF4
    VS_VT_F5 = 0xF5
    VX_VY_F7 = 0xF7

class ALDLMode(IntEnum):
    """ALDL mode/command bytes."""
    MODE1_DATASTREAM = 0x01
    MODE2_READ_RAM = 0x02
    MODE3_READ_BYTES = 0x03
    MODE4_ACTUATOR = 0x04
    MODE5_ENTER_PROG = 0x05
    MODE6_UPLOAD = 0x06
    MODE8_SILENCE = 0x08
    MODE9_UNSILENCE = 0x09
    MODE10_WRITE_CAL = 0x0A
    MODE13_SECURITY = 0x0D
    MODE16_FLASH_WRITE = 0x10

class FlashBank(IntEnum):
    """AMD 29F010 bank mapping for HC11 bank-switched window ($8000-$FFFF)."""
    BANK_72 = 0x48   # Sectors 0-3 (lower 64KB)
    BANK_88 = 0x58   # Sectors 4-5 (middle 32KB)
    BANK_80 = 0x50   # Sectors 6-7 (upper 32KB)

class FlashSector(IntEnum):
    """Sector base addresses within each bank window."""
    SECTOR_0 = 0x20   # $2000-$3FFF in bank 72
    SECTOR_1 = 0x40   # $4000-$5FFF (calibration area) in bank 72
    SECTOR_2 = 0x80   # $8000-$9FFF in bank 72
    SECTOR_3 = 0xC0   # $C000-$DFFF in bank 72
    SECTOR_4 = 0x80   # in bank 88
    SECTOR_5 = 0xC0   # in bank 88
    SECTOR_6 = 0x80   # in bank 80
    SECTOR_7 = 0xC0   # in bank 80

# Erase map: list of (bank, sector) for each write mode
ERASE_MAP_BIN = [
    # BIN: erase sectors 0-6 (skip sector 7 = boot area)
    (FlashBank.BANK_72, FlashSector.SECTOR_0),
    (FlashBank.BANK_72, FlashSector.SECTOR_1),
    (FlashBank.BANK_72, FlashSector.SECTOR_2),
    (FlashBank.BANK_72, FlashSector.SECTOR_3),
    (FlashBank.BANK_88, FlashSector.SECTOR_4),
    (FlashBank.BANK_88, FlashSector.SECTOR_5),
    (FlashBank.BANK_80, FlashSector.SECTOR_6),
]

ERASE_MAP_CAL = [
    # CAL: erase sector 1 only (calibration area $4000-$7FFF in bank 72)
    (FlashBank.BANK_72, FlashSector.SECTOR_1),
]

ERASE_MAP_PROM = [
    # PROM: erase all 8 sectors (recovery)
    (FlashBank.BANK_72, FlashSector.SECTOR_0),
    (FlashBank.BANK_72, FlashSector.SECTOR_1),
    (FlashBank.BANK_72, FlashSector.SECTOR_2),
    (FlashBank.BANK_72, FlashSector.SECTOR_3),
    (FlashBank.BANK_88, FlashSector.SECTOR_4),
    (FlashBank.BANK_88, FlashSector.SECTOR_5),
    (FlashBank.BANK_80, FlashSector.SECTOR_6),
    (FlashBank.BANK_80, FlashSector.SECTOR_7),
]

# Write address ranges (file offsets, NOT CPU addresses)
WRITE_RANGES = {
    "CAL":  (0x4000, 0x7FFF),         # 16KB calibration only
    "BIN":  (0x2000, 0x1BFFF),        # 104KB OS + cal (sectors 0-6, skip boot sector 7)
    "PROM": (0x2000, 0x1FFFF),        # 120KB full (all 8 sectors minus first 8KB)
}

# Bank→file offset mapping for the write routine
# OSE remaps data for banks 88/80: copies file data into a window at PCM address $8000
# Bank 72: file offsets map 1:1 to PCM addresses (no remap needed)
# Bank 88: file offsets $10000-$17FFF → remapped to PCM addresses $8000-$FFFF
# Bank 80: file offsets $18000-$1FFFF → remapped to PCM addresses $8000-$FFFF
BANK_WRITE_MAP = [
    # (bank_byte, file_start, file_end, pcm_base_offset)
    # pcm_base_offset: subtract from file offset to get PCM address
    (FlashBank.BANK_72, 0x0000,  0xFFFF,  0),        # Sectors 0-3 (64KB, 1:1 mapping)
    (FlashBank.BANK_88, 0x10000, 0x17FFF, 0x8000),   # Sectors 4-5 (32KB, remap to $8000)
    (FlashBank.BANK_80, 0x18000, 0x1FFFF, 0x10000),  # Sectors 6-7 (32KB, remap to $8000)
]

# Per-sector info for custom flash: (sector_num, bank, erase_byte, file_start, file_end, label)
# AMD 29F010: 8 × 16KB sectors.  Sector 7 = boot area — never erase unless you have a bench programmer.
SECTOR_INFO = [
    (0, FlashBank.BANK_72, FlashSector.SECTOR_0, 0x0000, 0x3FFF, "OS Vectors / Boot"),
    (1, FlashBank.BANK_72, FlashSector.SECTOR_1, 0x4000, 0x7FFF, "Calibration (CAL)"),
    (2, FlashBank.BANK_72, FlashSector.SECTOR_2, 0x8000, 0xBFFF, "OS Page 1"),
    (3, FlashBank.BANK_72, FlashSector.SECTOR_3, 0xC000, 0xFFFF, "OS Page 2"),
    (4, FlashBank.BANK_88, FlashSector.SECTOR_4, 0x10000, 0x13FFF, "OS Page 3"),
    (5, FlashBank.BANK_88, FlashSector.SECTOR_5, 0x14000, 0x17FFF, "OS Page 4"),
    (6, FlashBank.BANK_80, FlashSector.SECTOR_6, 0x18000, 0x1BFFF, "OS Page 5"),
    (7, FlashBank.BANK_80, FlashSector.SECTOR_7, 0x1C000, 0x1FFFF, "OS Page 6 + Vectors (BOOT)"),
]

# Checksum location in the bin file
CHECKSUM_OFFSET_HI = 0x4006
CHECKSUM_OFFSET_LO = 0x4007
CHECKSUM_SKIP_START = 0x4000
CHECKSUM_SKIP_END = 0x4007

# Seed/Key magic constant
SEED_KEY_MAGIC = 37709   # 0x934D

# ALDL frame encoding constant
ALDL_LENGTH_OFFSET = 85  # Frame[1] encodes: actual_wire_bytes = Frame[1] - 82
                          # and: checksum_position = Frame[1] - 83
                          # and: payload_length = Frame[1] - 85

# Default comm settings
DEFAULT_BAUD = 8192
DEFAULT_TIMEOUT_MS = 2000
DEFAULT_INTER_FRAME_DELAY_MS = 10
DEFAULT_MAX_RETRIES = 10
DEFAULT_WRITE_CHUNK_SIZE = 32  # bytes per flash write frame

# Timing constants
ECHO_DETECT_TIMEOUT_MS = 500
SILENCE_WAIT_MS = 50
HEARTBEAT_TIMEOUT_MS = 3000
MODE5_TIMEOUT_MS = 5000
MODE6_UPLOAD_TIMEOUT_MS = 10000
ERASE_TIMEOUT_MS = 30000
WRITE_FRAME_TIMEOUT_MS = 5000
CHECKSUM_TIMEOUT_MS = 30000
CLEANUP_DELAY_MS = 2000          # Wait after reset before re-enabling chatter (was 750, too fast)
POST_CHATTER_DELAY_MS = 1500     # Wait after re-enabling chatter before any further comms
INTER_RETRY_DELAY_MS = 50        # Pause between retries — lets the bus settle and RX buffer drain
READ_BLOCK_MAX_RETRIES = 3       # Per-block read retries before skipping
SECTOR_SIZE = 0x4000             # 16KB flash sector boundary for write rollback

# Flash chip IDs
FLASH_AMD_29F010 = (0x01, 0x20)   # Manufacturer=AMD, Device=29F010
FLASH_AMD_29F040 = (0x01, 0xA4)   # Manufacturer=AMD, Device=29F040
FLASH_CAT_28F010 = (0x31, 0xB4)   # Manufacturer=OnSemi, Device=CAT28F010


# ═══════════════════════════════════════════════════════════════════════
# SECTION 2 — DATA STREAM DEFINITIONS (Mode 1 Message 0)
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class DataStreamParam:
    """One parameter in the Mode 1 data stream."""
    name: str
    ram_addr: int
    pkt_offset: int         # byte offset within Mode 1 Msg 0 response data
    size: int               # 1 or 2 bytes
    signed: bool = False
    units: str = ""
    conversion: str = ""    # human-readable conversion formula
    scale: float = 1.0      # multiply raw by this
    offset_val: float = 0.0 # then add this

# Mode 1 Message 0 — 60 data bytes from the VS_Mode1 definition table at $50FE
# These are the confirmed RAM addresses for VS/VX/VY V6 Delco ECUs
MODE1_MSG0_PARAMS: List[DataStreamParam] = [
    DataStreamParam("RPM",              0x0089, 0,  2, units="RPM",    conversion="RPM/25",     scale=25.0),
    DataStreamParam("Desired Idle",     0x1835, 2,  2, units="RPM",    conversion="RPM/25",     scale=25.0),
    DataStreamParam("ECT Voltage",      0x1908, 4,  1, units="V",      conversion="X*5/255",    scale=5.0/255),
    DataStreamParam("ECT Temp",         0x190A, 5,  1, units="°C",     conversion="X*0.75-40",  scale=0.75, offset_val=-40),
    DataStreamParam("IAT Voltage",      0x1901, 6,  1, units="V",      conversion="X*5/255",    scale=5.0/255),
    DataStreamParam("IAT Temp",         0x1904, 7,  1, units="°C",     conversion="X*0.75-40",  scale=0.75, offset_val=-40),
    DataStreamParam("MAF Freq",         0x014F, 8,  2, units="Hz",     conversion="X",          scale=1.0),
    DataStreamParam("MAF",              0x011C, 10, 2, units="g/s",    conversion="X",          scale=1.0),
    DataStreamParam("TPS Voltage",      0x017A, 12, 1, units="V",      conversion="X*5/255",    scale=5.0/255),
    DataStreamParam("TPS %",            0x1B77, 13, 1, units="%",      conversion="X/2.55",     scale=1.0/2.55),
    DataStreamParam("LH O2",           0x0061, 14, 1, units="mV",     conversion="X*4.44",     scale=4.44),
    DataStreamParam("LH O2 Xcount",    0x1827, 15, 1, units="",       conversion="X",          scale=1.0),
    DataStreamParam("RH O2",           0x0060, 16, 1, units="mV",     conversion="X*4.44",     scale=4.44),
    DataStreamParam("RH O2 Xcount",    0x1826, 17, 1, units="",       conversion="X",          scale=1.0),
    DataStreamParam("Inj PW",          0x0153, 18, 2, units="ms",     conversion="X*0.01526",  scale=0.01526),
    DataStreamParam("Inj Voltage",     0x1843, 20, 1, units="V",      conversion="X*0.1",      scale=0.1),
    DataStreamParam("LH STFT",         0x0124, 21, 1, units="%",      conversion="(X-128)/1.28", scale=1.0/1.28, offset_val=-100.0),
    DataStreamParam("RH STFT",         0x0123, 22, 1, units="%",      conversion="(X-128)/1.28", scale=1.0/1.28, offset_val=-100.0),
    DataStreamParam("LH LTFT",         0x0077, 23, 1, units="%",      conversion="(X-128)/1.28", scale=1.0/1.28, offset_val=-100.0),
    DataStreamParam("RH LTFT",         0x0072, 24, 1, units="%",      conversion="(X-128)/1.28", scale=1.0/1.28, offset_val=-100.0),
    DataStreamParam("BLM Cell",        0x006F, 25, 1, units="",       conversion="X",          scale=1.0),
    DataStreamParam("STFT Change",     0x0302, 26, 1, units="",       conversion="X",          scale=1.0),
    DataStreamParam("LTFT Var",        0x0303, 27, 1, units="",       conversion="X",          scale=1.0),
    DataStreamParam("AFR",             0x182A, 28, 1, units=":1",     conversion="X/10",       scale=0.1),
    DataStreamParam("Battery V",       0x006A, 29, 1, units="V",      conversion="X*0.1",      scale=0.1),
    DataStreamParam("Ref Voltage",     0x1841, 30, 1, units="V",      conversion="X*0.02",     scale=0.02),
    DataStreamParam("Status 32",       0x0030, 31, 1, units="",       conversion="flags",      scale=1.0),
    DataStreamParam("Status 33",       0x0031, 32, 1, units="",       conversion="flags",      scale=1.0),
    DataStreamParam("Status 34",       0x0032, 33, 1, units="",       conversion="flags",      scale=1.0),
    DataStreamParam("Status 35",       0x0033, 34, 1, units="",       conversion="flags",      scale=1.0),
    DataStreamParam("Knock Retard",    0x0188, 35, 1, units="°",      conversion="X*0.351",    scale=0.351),
    DataStreamParam("EPROM ID Hi",     0x2000, 36, 1, units="",       conversion="hex",        scale=1.0),
    DataStreamParam("EPROM ID Lo",     0x2001, 37, 1, units="",       conversion="hex",        scale=1.0),
    DataStreamParam("mg/s/cyl",        0x0067, 38, 1, units="mg/s",   conversion="X",          scale=1.0),
    DataStreamParam("Wheel Speed",     0x0208, 39, 1, units="km/h",   conversion="X",          scale=1.0),
    DataStreamParam("Idle Var",        0x1A3D, 40, 2, units="RPM",    conversion="X",          scale=1.0),
    DataStreamParam("IAC Steps",       0x001D, 42, 1, units="steps",  conversion="X",          scale=1.0),
    DataStreamParam("Spark Advance",   0x01A7, 43, 2, units="°",      conversion="X*90/256-35", scale=90.0/256, offset_val=-35.0),
    DataStreamParam("Eng Perf 100",    0x0352, 45, 1, units="%",      conversion="X/2.55",     scale=1.0/2.55),
    DataStreamParam("Eng Perf 50",     0x0354, 46, 1, units="%",      conversion="X/2.55",     scale=1.0/2.55),
    DataStreamParam("EGR Pintle",      0x18F8, 47, 1, units="V",      conversion="X*5/255",    scale=5.0/255),
    DataStreamParam("EGR Feedback",    0x18F2, 48, 1, units="V",      conversion="X*5/255",    scale=5.0/255),
    DataStreamParam("EGR Desired",     0x18F1, 49, 1, units="V",      conversion="X*5/255",    scale=5.0/255),
    DataStreamParam("Canister Purge",  0x189B, 50, 1, units="%",      conversion="X/2.55",     scale=1.0/2.55),
    DataStreamParam("Fuel Consump",    0x0175, 51, 2, units="L/100k", conversion="X",          scale=1.0),
    DataStreamParam("Run Time",        0x001E, 53, 2, units="sec",    conversion="X",          scale=1.0),
    DataStreamParam("Crank Time",      0x017F, 55, 2, units="ms",     conversion="X",          scale=1.0),
]

# Quick lookup by name
PARAM_BY_NAME: Dict[str, DataStreamParam] = {p.name: p for p in MODE1_MSG0_PARAMS}


# ═══════════════════════════════════════════════════════════════════════
# SECTION 3 — CALIBRATION TABLE DEFINITIONS (from XDF analysis)
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class CalibrationTable:
    """A 2D calibration table in the ROM."""
    name: str
    rom_offset: int          # file offset in the 128KB bin
    rows: int
    cols: int
    element_size: int = 1    # bytes per cell (1 or 2)
    x_axis_name: str = ""    # e.g. "RPM"
    y_axis_name: str = ""    # e.g. "CYLAIR50"
    units: str = ""
    conversion: str = ""
    min_value: float = 0
    max_value: float = 255
    x_axis_values: List[float] = field(default_factory=list)
    y_axis_values: List[float] = field(default_factory=list)

    @property
    def byte_size(self) -> int:
        return self.rows * self.cols * self.element_size

# Key calibration tables for VY V6 $060A — from Enhanced XDF analysis
CAL_TABLES: Dict[str, CalibrationTable] = {
    "spark_hi_oct": CalibrationTable(
        name="Main Hi-Oct Spark <4800",
        rom_offset=0x614E,
        rows=17, cols=17,
        x_axis_name="RPM", y_axis_name="CYLAIR50",
        units="°BTDC", conversion="X/256*90-35",
        x_axis_values=[400,600,800,1000,1200,1400,1600,1800,2000,2200,2400,2600,2800,3200,3600,4000,4800],
        y_axis_values=[50,100,150,200,250,300,350,400,450,500,550,600,650,700,750,800,850],
    ),
    "spark_lo_oct": CalibrationTable(
        name="Main Lo-Oct Spark <4800",
        rom_offset=0x6272,
        rows=17, cols=17,
        x_axis_name="RPM", y_axis_name="CYLAIR50",
        units="°BTDC", conversion="X/256*90-35",
        x_axis_values=[400,600,800,1000,1200,1400,1600,1800,2000,2200,2400,2600,2800,3200,3600,4000,4800],
        y_axis_values=[50,100,150,200,250,300,350,400,450,500,550,600,650,700,750,800,850],
    ),
    "fuel_trim": CalibrationTable(
        name="Fuel Trim Factor",
        rom_offset=0x59D5,
        rows=16, cols=17,
        x_axis_name="RPM", y_axis_name="CYLAIR50",
        units="mult", conversion="X/128",
    ),
    "open_loop_afr": CalibrationTable(
        name="Open Loop AFR",
        rom_offset=0x7234,
        rows=17, cols=14,
        x_axis_name="RPM", y_axis_name="CYLAIR50",
        units="AFR", conversion="6.4*256/X",
    ),
    "airflow_gear14": CalibrationTable(
        name="Airflow vs RPM Gear 1-4",
        rom_offset=0x63C2,
        rows=12, cols=14,
        x_axis_name="RPM", y_axis_name="TPS",
        units="g/s",
    ),
    "spark_hi_oct_high": CalibrationTable(
        name="Main Hi-Oct Spark >4800",
        rom_offset=0x785D,
        rows=5, cols=17,
        x_axis_name="RPM", y_axis_name="CYLAIR50",
        units="°BTDC",
    ),
    "tcc_duty": CalibrationTable(
        name="TCC Duty Cycle",
        rom_offset=0x68C2,
        rows=8, cols=17,
        units="%",
    ),
}


# ═══════════════════════════════════════════════════════════════════════
# SECTION 4 — HC11 FLASH KERNEL BYTECODE (extracted from OSE V1.5.1)
# ═══════════════════════════════════════════════════════════════════════

class FlashKernel:
    """
    Raw HC11 machine code uploaded to the PCM RAM via Mode 6.
    These bytes are the flash driver that runs inside the ECU.
    Extracted from OSE Enhanced Flash Tool V1.5.1 decompilation.
    """

    # Block 0: Main loop + SCI handler (171 bytes)
    # byte[21] is patched: 0x81 = high-speed read, 0x41 = normal read
    EXEC_BLOCK_0 = bytearray([
        0xF7, 0xFE, 0x06, 0x01, 0x32, 0x86, 0xAA, 0x36, 0x18, 0x30,
        0x86, 0x06, 0xC6, 0x01, 0xBD, 0xFF, 0xBD, 0x32, 0x39, 0xCC,
        0x02, 0x41, 0x97, 0x34, 0x9D, 0x24, 0x20, 0x99, 0x36, 0x18,
        0x3C, 0x3C, 0x18, 0x38, 0xCE, 0x10, 0x00, 0x86, 0x08, 0xA7,
        0x2D, 0x4F, 0x97, 0x30, 0x86, 0xF7, 0x8D, 0x26, 0x17, 0x8B,
        0x55, 0x8D, 0x21, 0x96, 0x34, 0x8D, 0x1D, 0x5A, 0x27, 0x0A,
        0x18, 0xA6, 0x00, 0x8D, 0x15, 0x18, 0x08, 0x5A, 0x26, 0xF6,
        0x96, 0x30, 0x40, 0x8D, 0x0B, 0x1F, 0x2E, 0x40, 0xFC, 0x1D,
        0x2D, 0x08, 0x18, 0x38, 0x32, 0x39, 0x9D, 0x1E, 0x1F, 0x2E,
        0x80, 0xFA, 0xA7, 0x2F, 0x9B, 0x30, 0x97, 0x30, 0x39, 0x37,
        0xC6, 0x55, 0xF7, 0x10, 0x3A, 0x53, 0xF7, 0x10, 0x3A, 0xC6,
        0x50, 0xF7, 0x18, 0x06, 0xC6, 0xA0, 0xF7, 0x18, 0x06, 0x33,
        0x39, 0xDC, 0x35, 0x4D, 0x26, 0x04, 0xC6, 0x48, 0x20, 0x0D,
        0xC1, 0x80, 0x24, 0x07, 0x14, 0x36, 0x80, 0xC6, 0x58, 0x20,
        0x02, 0xC6, 0x50, 0xF7, 0x10, 0x00, 0x39, 0x3C, 0xCE, 0x10,
        0x00, 0x1C, 0x03, 0x08, 0x1D, 0x02, 0x08, 0x38, 0x39, 0x3C,
        0xCE, 0x10, 0x00, 0x1C, 0x03, 0x08, 0x1C, 0x02, 0x08, 0x38,
        0x39,
    ])

    # Block 1: Flash read + data streaming (172 bytes)
    # byte[166] is patched: 0x80 = high-speed read, 0x40 = normal read
    EXEC_BLOCK_1 = bytearray([
        0xF7, 0xFF, 0x06, 0x00, 0x99, 0x86, 0xAA, 0x36, 0x18, 0x30,
        0x86, 0x06, 0xC6, 0x01, 0xBD, 0xFF, 0xBD, 0x32, 0x39, 0x32,
        0x8D, 0x3F, 0x97, 0x37, 0x7A, 0x00, 0x32, 0xCE, 0x03, 0x00,
        0x20, 0x10, 0x8D, 0x33, 0x97, 0x2E, 0x7A, 0x00, 0x32, 0x8D,
        0x2C, 0x97, 0x2F, 0x7A, 0x00, 0x32, 0xDE, 0x2E, 0x8C, 0x03,
        0xFF, 0x22, 0xA5, 0x8D, 0x1E, 0xA7, 0x00, 0x08, 0x7A, 0x00,
        0x32, 0x26, 0xF1, 0x8D, 0x14, 0x5D, 0x26, 0x96, 0x96, 0x33,
        0x81, 0x10, 0x27, 0x06, 0xDE, 0x2E, 0xAD, 0x00, 0x20, 0x8A,
        0xBD, 0x02, 0x18, 0x20, 0xF9, 0x3C, 0xCE, 0x10, 0x00, 0x18,
        0xCE, 0x05, 0x75, 0x7F, 0x00, 0x31, 0x7A, 0x00, 0x31, 0x26,
        0x04, 0x18, 0x09, 0x27, 0x06, 0x9D, 0x1E, 0x1F, 0x2E, 0x0E,
        0x02, 0x20, 0xDD, 0x1F, 0x2E, 0x20, 0xEB, 0xA6, 0x2F, 0x16,
        0xDB, 0x30, 0xD7, 0x30, 0x38, 0x39, 0x81, 0x02, 0x26, 0xCC,
        0x8D, 0xD1, 0x97, 0x35, 0x8D, 0xCD, 0x97, 0x36, 0x8D, 0xC9,
        0x97, 0x37, 0x8D, 0xC5, 0x5D, 0x26, 0xBB, 0xCE, 0x03, 0x20,
        0x8D, 0x7A, 0x18, 0xDE, 0x36, 0x5F, 0x18, 0xA6, 0x00, 0xA7,
        0x00, 0x08, 0x18, 0x08, 0x5C, 0xC1, 0x40, 0x25, 0xF3, 0xCE,
        0x03, 0x20,
    ])

    # Block 2: Interrupt vectors + init (156 bytes) — no runtime patching
    EXEC_BLOCK_2 = bytearray([
        0xF7, 0xEF, 0x06, 0x00, 0x10, 0x20, 0x3E, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x7E, 0x01, 0xCC, 0x7E,
        0x01, 0x90, 0x00, 0x00, 0x00, 0x7E, 0x01, 0x49, 0x7E, 0x01,
        0xC0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x8E,
        0x00, 0x4F, 0x0F, 0xB6, 0x18, 0x05, 0x8A, 0x08, 0xB7, 0x18,
        0x05, 0x9D, 0x27, 0x3C, 0x30, 0x86, 0x06, 0x97, 0x34, 0xCC,
        0xAA, 0x00, 0xED, 0x00, 0xC6, 0x02, 0x9D, 0x24, 0x38, 0x8E,
        0x00, 0x4F, 0xCE, 0x10, 0x00, 0x86, 0x04, 0xA7, 0x2D, 0xEC,
        0x2E, 0x4F, 0x97, 0x30, 0x1C, 0x2D, 0x02, 0x8D, 0x67, 0x81,
        0xF7, 0x26, 0xE8, 0x8D, 0x61, 0x80, 0x56, 0x25, 0xE2, 0x97,
        0x32, 0x8D, 0x59, 0x97, 0x33, 0x81, 0x06, 0x27, 0x1E, 0x81,
        0x10, 0x26, 0x78, 0x8D, 0x4D, 0x97, 0x35, 0x7A, 0x00, 0x32,
        0x8D, 0x46, 0x97, 0x36, 0x7A, 0x00,
    ])

    # Flash Info reader — reads manufacturer + device ID
    FLASH_INFO = bytearray([
        0xF7, 0xDE, 0x06, 0x02, 0x00, 0xC6, 0x48, 0xF7, 0x10, 0x00,
        0x9D, 0x1B, 0x86, 0xAA, 0xB7, 0x55, 0x55, 0x86, 0x55, 0xB7,
        0x2A, 0xAA, 0x86, 0x90, 0xB7, 0x55, 0x55, 0x9D, 0x27, 0xCE,
        0x03, 0x20, 0xB6, 0x20, 0x00, 0xA7, 0x00, 0x08, 0xB6, 0x20,
        0x01, 0xA7, 0x00, 0x08, 0x18, 0xCE, 0x20, 0x02, 0x8D, 0x52,
        0x18, 0xCE, 0x40, 0x02, 0x8D, 0x4C, 0x18, 0xCE, 0x80, 0x02,
        0x8D, 0x46, 0x18, 0xCE, 0xC0, 0x02, 0x8D, 0x40, 0xC6, 0x58,
        0xF7, 0x10, 0x00, 0x18, 0xCE, 0x80, 0x02, 0x8D, 0x35, 0x18,
        0xCE, 0xC0, 0x02, 0x8D, 0x2F, 0xC6, 0x50, 0xF7, 0x10, 0x00,
        0x18, 0xCE, 0x80, 0x02, 0x8D, 0x24, 0x18, 0xCE, 0xC0, 0x02,
        0x8D, 0x1E, 0x9D, 0x1B, 0xC6, 0xAA, 0xF7, 0x55, 0x55, 0xC6,
        0x55, 0xF7, 0x2A, 0xAA, 0xC6, 0xF0, 0xF7, 0x55, 0x55, 0x9D,
        0x27, 0xCE, 0x03, 0x20, 0xCC, 0x06, 0x0B, 0x97, 0x34, 0x9D,
        0x24, 0x39, 0x18, 0xA6, 0x00, 0xA7, 0x00, 0x08, 0x39,
    ])

    # Erase sector — byte[105]=bank, byte[106]=sector (patched at runtime)
    ERASE_SECTOR = bytearray([
        0xF7, 0xBF, 0x06, 0x02, 0x00, 0xF6, 0x02, 0x64, 0xF7, 0x10,
        0x00, 0x9D, 0x1B, 0x86, 0xAA, 0xB7, 0x55, 0x55, 0x86, 0x55,
        0xB7, 0x2A, 0xAA, 0x86, 0x80, 0xB7, 0x55, 0x55, 0x86, 0xAA,
        0xB7, 0x55, 0x55, 0x86, 0x55, 0xB7, 0x2A, 0xAA, 0x86, 0x30,
        0xFE, 0x02, 0x65, 0xA7, 0x00, 0x9D, 0x27, 0x9D, 0x1E, 0xFE,
        0x02, 0x65, 0xA6, 0x00, 0x2B, 0x20, 0x85, 0x20, 0x27, 0xF3,
        0x9D, 0x1B, 0xC6, 0xAA, 0xF7, 0x55, 0x55, 0xC6, 0x55, 0xF7,
        0x2A, 0xAA, 0xC6, 0xF0, 0xF7, 0x55, 0x55, 0x9D, 0x27, 0x86,
        0x06, 0x97, 0x34, 0xCC, 0x55, 0x00, 0x20, 0x07, 0x86, 0x06,
        0x97, 0x34, 0xCC, 0xAA, 0x00, 0x3C, 0x30, 0xED, 0x00, 0xC6,
        0x02, 0x9D, 0x24, 0x38, 0x39, 0x48, 0x40, 0x00,
    ])

    # Write bank setup — byte[157]=bank (patched at runtime)
    WRITE_BANK = bytearray([
        0xF7, 0xF1, 0x06, 0x02, 0x00, 0x3C, 0x30, 0x86, 0x06, 0x97,
        0x34, 0xCC, 0xAA, 0x00, 0xED, 0x00, 0xC6, 0x02, 0x9D, 0x24,
        0x38, 0x39, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xCE,
        0x03, 0x00, 0x86, 0x20, 0xB7, 0x03, 0x61, 0x18, 0xFE, 0x00,
        0x36, 0x4F, 0xF6, 0x02, 0x98, 0xF7, 0x10, 0x00, 0x9D, 0x1B,
        0xC6, 0xAA, 0xF7, 0x55, 0x55, 0xC6, 0x55, 0xF7, 0x2A, 0xAA,
        0xC6, 0xA0, 0xF7, 0x55, 0x55, 0xE6, 0x00, 0x18, 0xE7, 0x00,
        0x9D, 0x1E, 0x9D, 0x27, 0xE6, 0x00, 0x37, 0x18, 0xE8, 0x00,
        0x33, 0x2B, 0x0E, 0x18, 0xE6, 0x00, 0xE1, 0x00, 0x27, 0x2D,
        0x4C, 0x81, 0x0A, 0x23, 0xCB, 0x20, 0x19, 0xC5, 0x20, 0x27,
        0xE5, 0x3C, 0x9D, 0x1B, 0xC6, 0xAA, 0xF7, 0x55, 0x55, 0xC6,
        0x55, 0xF7, 0x2A, 0xAA, 0xC6, 0xF0, 0xF7, 0x55, 0x55, 0x9D,
        0x27, 0x38, 0x86, 0x10, 0x97, 0x34, 0xCC, 0x55, 0x00, 0xED,
        0x00, 0xC6, 0x02, 0x20, 0x13, 0x08, 0x18, 0x08, 0x7A, 0x03,
        0x61, 0x26, 0x9A, 0x86, 0x10, 0x97, 0x34, 0xCC, 0xAA, 0x00,
        0xED, 0x00, 0xC6, 0x02, 0x9D, 0x24, 0x39, 0x48,
    ])

    # Checksum verifier — computes checksum across all 3 banks
    CHECKSUM_BIN = bytearray([
        0xF7, 0xE1, 0x06, 0x02, 0x00, 0x86, 0x01, 0xB7, 0x03, 0x63,
        0x18, 0xCE, 0x03, 0xE8, 0xCE, 0x20, 0x00, 0xCC, 0x00, 0x00,
        0x37, 0xF6, 0x03, 0x63, 0xC1, 0x04, 0x33, 0x2C, 0x3B, 0x36,
        0x37, 0xB6, 0x03, 0x63, 0x81, 0x01, 0x26, 0x07, 0xC6, 0x48,
        0xF7, 0x10, 0x00, 0x20, 0x10, 0x81, 0x02, 0x26, 0x07, 0xC6,
        0x58, 0xF7, 0x10, 0x00, 0x20, 0x05, 0xC6, 0x50, 0xF7, 0x10,
        0x00, 0x33, 0x32, 0xEB, 0x00, 0x89, 0x00, 0x08, 0x26, 0x06,
        0x7C, 0x03, 0x63, 0xCE, 0x80, 0x00, 0x18, 0x09, 0x26, 0x06,
        0x9D, 0x1E, 0x18, 0xCE, 0x03, 0xE8, 0x20, 0xBC, 0x3C, 0xCE,
        0x40, 0x00, 0xE0, 0x00, 0x82, 0x00, 0x08, 0x8C, 0x40, 0x08,
        0x25, 0xF6, 0x37, 0x36, 0xFD, 0x03, 0x64, 0xB1, 0x40, 0x06,
        0x26, 0x09, 0xF1, 0x40, 0x07, 0x26, 0x04, 0x86, 0xAA, 0x20,
        0x02, 0x86, 0x55, 0x36, 0x86, 0x06, 0x97, 0x34, 0x30, 0xC6,
        0x04, 0x9D, 0x24, 0x32, 0x32, 0x33, 0x38, 0x39,
    ])

    # Cleanup / reset — sends 0xBB then clears RAM
    CLEANUP = bytearray([
        0xF7, 0x74, 0x06, 0x02, 0x00, 0x3C, 0x30, 0x86, 0x06, 0x97,
        0x34, 0xCC, 0xBB, 0x00, 0xED, 0x00, 0xC6, 0x02, 0x9D, 0x24,
        0x38, 0xCE, 0x01, 0xFF, 0x6F, 0x00, 0x09, 0x26, 0xFB, 0x6F,
        0x00, 0x20, 0xFE,
    ])

    @classmethod
    def get_exec_blocks(cls, high_speed: bool = False) -> list:
        """Return the 3 kernel blocks with high-speed patching applied."""
        b0 = bytearray(cls.EXEC_BLOCK_0)
        b1 = bytearray(cls.EXEC_BLOCK_1)
        b2 = bytearray(cls.EXEC_BLOCK_2)
        if high_speed:
            b0[21] = 0x81
            b1[166] = 0x80
        else:
            b0[21] = 0x41
            b1[166] = 0x40
        return [b0, b1, b2]

    @classmethod
    def get_erase_frame(cls, bank: int, sector: int) -> bytearray:
        """Return erase frame with bank/sector patched."""
        frame = bytearray(cls.ERASE_SECTOR)
        frame[105] = bank
        frame[106] = sector
        return frame

    @classmethod
    def get_write_bank_frame(cls, bank: int) -> bytearray:
        """Return write-bank-setup frame with bank patched."""
        frame = bytearray(cls.WRITE_BANK)
        frame[157] = bank
        return frame


# ═══════════════════════════════════════════════════════════════════════
# SECTION 5 — ALDL FRAME PROTOCOL ENGINE
# ═══════════════════════════════════════════════════════════════════════

class ALDLProtocol:
    """
    Low-level ALDL frame building, checksum, and parsing.
    All frames: [DeviceID] [Length] [Mode] [Data...] [Checksum]

    Length byte encoding (OSE convention):
        Frame[1] = actual_wire_byte_count + 82
        So wire bytes = Frame[1] - 82
        Checksum position = Frame[1] - 83  (index of checksum byte)
        Data payload length = Frame[1] - 85
    """

    @staticmethod
    def compute_checksum(frame: bytearray) -> int:
        """Compute ALDL checksum: 256 - (sum of all bytes before checksum) mod 256."""
        cs_pos = frame[1] - 83
        total = 0
        for i in range(cs_pos):
            total = (total + frame[i]) & 0xFF
        if total == 0:
            total = 256
        return (256 - total) & 0xFF

    @staticmethod
    def apply_checksum(frame: bytearray) -> bytearray:
        """Compute and write checksum into the frame. Returns the frame."""
        cs_pos = frame[1] - 83
        # Ensure frame is large enough
        while len(frame) <= cs_pos:
            frame.append(0)
        frame[cs_pos] = ALDLProtocol.compute_checksum(frame)
        return frame

    @staticmethod
    def verify_checksum(frame: bytearray) -> bool:
        """Verify received frame checksum. Sum of all bytes including checksum should be 0."""
        cs_pos = frame[1] - 83
        total = 0
        for i in range(cs_pos + 1):
            total = (total + frame[i]) & 0xFF
        return total == 0

    @staticmethod
    def wire_length(frame: bytearray) -> int:
        """Number of bytes to actually transmit on the wire."""
        return frame[1] - 82

    @staticmethod
    def build_simple_frame(device_id: int, mode: int, data: bytes = b"") -> bytearray:
        """Build a simple ALDL frame with mode and optional data payload."""
        payload_len = 1 + len(data)  # mode byte + data
        length_byte = ALDL_LENGTH_OFFSET + payload_len
        frame = bytearray(201)  # OSE-compatible buffer size
        frame[0] = device_id
        frame[1] = length_byte
        frame[2] = mode
        for i, b in enumerate(data):
            frame[3 + i] = b
        ALDLProtocol.apply_checksum(frame)
        return frame

    @staticmethod
    def build_mode1_request(device_id: int, message: int = 0) -> bytearray:
        """Build Mode 1 data stream request."""
        return ALDLProtocol.build_simple_frame(device_id, ALDLMode.MODE1_DATASTREAM, bytes([message]))

    @staticmethod
    def build_mode2_read(device_id: int, address: int, extended: bool = False) -> bytearray:
        """Build Mode 2 RAM read request (64 bytes at address)."""
        frame = bytearray(201)
        frame[0] = device_id
        if extended:
            frame[1] = 0x59  # 89
            frame[2] = ALDLMode.MODE2_READ_RAM
            frame[3] = (address >> 16) & 0xFF
            frame[4] = (address >> 8) & 0xFF
            frame[5] = address & 0xFF
        else:
            frame[1] = 0x58  # 88
            frame[2] = ALDLMode.MODE2_READ_RAM
            frame[3] = (address >> 8) & 0xFF
            frame[4] = address & 0xFF
        ALDLProtocol.apply_checksum(frame)
        return frame

    @staticmethod
    def build_seed_request(device_id: int) -> bytearray:
        """Build Mode 13 seed request."""
        return ALDLProtocol.build_simple_frame(
            device_id, ALDLMode.MODE13_SECURITY, bytes([0x01])
        )

    @staticmethod
    def build_key_response(device_id: int, key: int) -> bytearray:
        """Build Mode 13 key response."""
        key_hi = (key >> 8) & 0xFF
        key_lo = key & 0xFF
        frame = bytearray(201)
        frame[0] = device_id
        frame[1] = 0x59
        frame[2] = ALDLMode.MODE13_SECURITY
        frame[3] = 0x02
        frame[4] = key_hi
        frame[5] = key_lo
        ALDLProtocol.apply_checksum(frame)
        return frame

    @staticmethod
    def build_mode5_request(device_id: int) -> bytearray:
        """Build Mode 5 enter-programming request."""
        frame = bytearray(201)
        frame[0] = device_id
        frame[1] = 0x56
        frame[2] = ALDLMode.MODE5_ENTER_PROG
        ALDLProtocol.apply_checksum(frame)
        return frame

    @staticmethod
    def build_silence_frame(device_id: int) -> bytearray:
        """Build Mode 8 disable-chatter frame."""
        frame = bytearray(201)
        frame[0] = device_id
        frame[1] = 0x56
        frame[2] = ALDLMode.MODE8_SILENCE
        ALDLProtocol.apply_checksum(frame)
        return frame

    @staticmethod
    def build_unsilence_frame(device_id: int) -> bytearray:
        """Build Mode 9 enable-chatter frame."""
        frame = bytearray(201)
        frame[0] = device_id
        frame[1] = 0x56
        frame[2] = ALDLMode.MODE9_UNSILENCE
        ALDLProtocol.apply_checksum(frame)
        return frame

    @staticmethod
    def build_write_frame(device_id: int, address: int, data: bytes,
                          mode: int = ALDLMode.MODE16_FLASH_WRITE,
                          extended: bool = True) -> bytearray:
        """Build a flash write data frame (Mode 16 for flash, Mode 10/11/12 for NVRAM)."""
        frame = bytearray(201)
        frame[0] = device_id
        if extended:
            # 3-byte address for flash
            frame[1] = ALDL_LENGTH_OFFSET + len(data) + 4
            frame[2] = mode
            frame[3] = (address >> 16) & 0xFF
            frame[4] = (address >> 8) & 0xFF
            frame[5] = address & 0xFF
            for i, b in enumerate(data):
                frame[6 + i] = b
        else:
            # 2-byte address for EEPROM/RAM
            frame[1] = ALDL_LENGTH_OFFSET + len(data) + 3
            frame[2] = mode
            frame[3] = (address >> 8) & 0xFF
            frame[4] = address & 0xFF
            for i, b in enumerate(data):
                frame[5 + i] = b
        ALDLProtocol.apply_checksum(frame)
        return frame

    @staticmethod
    def compute_seed_key(seed_hi: int, seed_lo: int) -> int:
        """
        Compute seed→key for Mode 13 security unlock.
        OSE algorithm: key = 37709 - (seed_lo*256 + seed_hi)
        Note the SWAPPED byte order.
        """
        seed = seed_lo * 256 + seed_hi
        key = SEED_KEY_MAGIC - seed
        if key < 0:
            key += 65536
        return key & 0xFFFF

    @staticmethod
    def parse_mode1_response(data: bytes) -> Dict[str, float]:
        """Parse Mode 1 Message 0 response data into parameter dict."""
        result = {}
        for p in MODE1_MSG0_PARAMS:
            if p.pkt_offset + p.size <= len(data):
                if p.size == 1:
                    raw = data[p.pkt_offset]
                elif p.size == 2:
                    raw = (data[p.pkt_offset] << 8) | data[p.pkt_offset + 1]
                else:
                    continue
                value = raw * p.scale + p.offset_val
                result[p.name] = round(value, 3)
        return result


# ═══════════════════════════════════════════════════════════════════════
# SECTION 6 — TRANSPORT LAYER (Serial / D2XX / Loopback)
# ═══════════════════════════════════════════════════════════════════════

class TransportError(Exception):
    """Raised when transport fails."""

class BaseTransport:
    """Abstract base for all serial transports."""

    def open(self) -> None:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError

    def write(self, data: bytes) -> int:
        raise NotImplementedError

    def read(self, count: int, timeout_ms: int = 2000) -> bytes:
        raise NotImplementedError

    def flush_input(self) -> None:
        raise NotImplementedError

    def flush_output(self) -> None:
        raise NotImplementedError

    @property
    def is_open(self) -> bool:
        raise NotImplementedError

    @property
    def bytes_available(self) -> int:
        raise NotImplementedError


class PySerialTransport(BaseTransport):
    """PySerial (COM port / VCP) transport."""

    def __init__(self, port: str, baud: int = DEFAULT_BAUD):
        self.port = port
        self.baud = baud
        self._serial: Optional[serial.Serial] = None

    def open(self) -> None:
        if not SERIAL_AVAILABLE:
            raise TransportError("pyserial not installed — pip install pyserial")
        try:
            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baud,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1,
                write_timeout=1.0,
            )
            log.info("Opened %s at %d baud", self.port, self.baud)
        except serial.SerialException as e:
            raise TransportError(f"Failed to open {self.port}: {e}")

    def close(self) -> None:
        if self._serial and self._serial.is_open:
            self._serial.close()
            log.info("Closed %s", self.port)

    def write(self, data: bytes) -> int:
        if not self._serial or not self._serial.is_open:
            raise TransportError("Port not open")
        return self._serial.write(data)

    def read(self, count: int, timeout_ms: int = 2000) -> bytes:
        if not self._serial or not self._serial.is_open:
            raise TransportError("Port not open")
        self._serial.timeout = timeout_ms / 1000.0
        data = self._serial.read(count)
        return bytes(data)

    def flush_input(self) -> None:
        if self._serial and self._serial.is_open:
            self._serial.reset_input_buffer()

    def flush_output(self) -> None:
        if self._serial and self._serial.is_open:
            self._serial.reset_output_buffer()

    @property
    def is_open(self) -> bool:
        return self._serial is not None and self._serial.is_open

    @property
    def bytes_available(self) -> int:
        if self._serial and self._serial.is_open:
            return self._serial.in_waiting
        return 0

    @staticmethod
    def list_ports() -> List[str]:
        """List available serial ports."""
        if not SERIAL_AVAILABLE:
            return []
        return [p.device for p in serial.tools.list_ports.comports()]


class D2XXTransport(BaseTransport):
    """FTDI D2XX direct USB transport (lower latency)."""

    def __init__(self, device_index: int = 0, baud: int = DEFAULT_BAUD):
        self.device_index = device_index
        self.baud = baud
        self._device = None

    def open(self) -> None:
        if not D2XX_AVAILABLE:
            raise TransportError("ftd2xx not installed — pip install ftd2xx")
        try:
            self._device = ftd2xx.open(self.device_index)
            self._device.setBaudRate(self.baud)
            self._device.setDataCharacteristics(
                ftd2xx.defines.BITS_8,
                ftd2xx.defines.STOP_BITS_1,
                ftd2xx.defines.PARITY_NONE,
            )
            self._device.setTimeouts(200, 200)
            self._device.setLatencyTimer(2)
            self._device.purge(ftd2xx.defines.PURGE_RX | ftd2xx.defines.PURGE_TX)
            log.info("Opened FTDI D2XX device %d at %d baud", self.device_index, self.baud)
        except Exception as e:
            raise TransportError(f"Failed to open D2XX device {self.device_index}: {e}")

    def close(self) -> None:
        if self._device:
            try:
                self._device.close()
            except Exception:
                pass
            self._device = None

    def write(self, data: bytes) -> int:
        if not self._device:
            raise TransportError("D2XX device not open")
        return self._device.write(data)

    def read(self, count: int, timeout_ms: int = 2000) -> bytes:
        if not self._device:
            raise TransportError("D2XX device not open")
        self._device.setTimeouts(timeout_ms, timeout_ms)
        data = self._device.read(count)
        return bytes(data)

    def flush_input(self) -> None:
        if self._device:
            self._device.purge(ftd2xx.defines.PURGE_RX)

    def flush_output(self) -> None:
        if self._device:
            self._device.purge(ftd2xx.defines.PURGE_TX)

    @property
    def is_open(self) -> bool:
        return self._device is not None

    @property
    def bytes_available(self) -> int:
        if self._device:
            return self._device.getQueueStatus()
        return 0


class LoopbackTransport(BaseTransport):
    """
    In-memory loopback for testing without hardware.
    Simulates an ECU that responds to ALDL frames.

    If *bin_path* is provided ("Virtual ECU" mode), the simulated flash is
    loaded from a real 128KB .bin file so that Read ECU, Mode 1 sensors, and
    the disassembler all return realistic data.
    """

    def __init__(self, bin_path: Optional[str] = None):
        self._rx_buffer = bytearray()
        self._tx_log: List[bytes] = []
        self._opened = False
        self._unlocked = False
        self._vecu_mode = bin_path is not None
        self._bin_path = bin_path
        self._active_write_bank: int = FlashBank.BANK_72  # Track which bank is selected for writes
        self._write_bank_pcm_base: int = 0  # PCM base offset for current bank

        # Load the simulated flash image
        if bin_path and Path(bin_path).exists():
            raw = Path(bin_path).read_bytes()
            if len(raw) == 16384:  # 16KB cal → pad to 128KB
                padded = bytearray(b'\xFF' * 131072)
                padded[0x4000:0x4000 + 16384] = raw
                self._simulated_bin = padded
            elif len(raw) == 131072:
                self._simulated_bin = bytearray(raw)
            else:
                log.warning("Virtual ECU: unexpected bin size %d, using zeros", len(raw))
                self._simulated_bin = bytearray(131072)
            log.info("Virtual ECU loaded %d KB from %s", len(self._simulated_bin) // 1024, bin_path)
        else:
            self._simulated_bin = bytearray(131072)  # 128KB zeros

    # ── vEEPROM Management ─────────────────────────────────────────────

    def reset_flash(self) -> None:
        """Clear the virtual flash to all zeros (unloaded state)."""
        self._simulated_bin = bytearray(131072)
        log.info("vEEPROM: reset to all zeros (empty)")

    def erase_flash(self) -> None:
        """Erase the virtual flash to all 0xFF (simulates full chip erase)."""
        self._simulated_bin = bytearray(b'\xFF' * 131072)
        log.info("vEEPROM: erased to all 0xFF")

    def load_flash(self, bin_data: bytearray) -> bool:
        """Load a bin image into the virtual flash. Returns True on success."""
        if len(bin_data) == 131072:
            self._simulated_bin = bytearray(bin_data)
            log.info("vEEPROM: loaded 128KB image")
            return True
        elif len(bin_data) == 16384:
            self._simulated_bin = bytearray(b'\xFF' * 131072)
            self._simulated_bin[0x4000:0x4000 + 16384] = bin_data
            log.info("vEEPROM: loaded 16KB cal, padded to 128KB (0xFF fill)")
            return True
        else:
            log.error("vEEPROM: invalid bin size %d (expected 128KB or 16KB)", len(bin_data))
            return False

    def export_flash(self) -> bytearray:
        """Return a copy of the current virtual flash contents."""
        return bytearray(self._simulated_bin)

    def flash_info(self) -> dict:
        """Return diagnostic info about the virtual flash state."""
        import hashlib
        sector_size = 16384  # 16KB
        sectors = {}
        for i in range(8):
            start = i * sector_size
            end = start + sector_size
            sector_data = self._simulated_bin[start:end]
            if all(b == 0xFF for b in sector_data):
                sectors[i] = "erased"
            elif all(b == 0x00 for b in sector_data):
                sectors[i] = "empty"
            else:
                sectors[i] = "used"

        # Compute bin checksum (same as BinFile.compute_checksum)
        cs_sum = 0
        for addr in range(0x2000, 0x20000):
            if 0x4006 <= addr <= 0x4007:
                continue
            cs_sum = (cs_sum + self._simulated_bin[addr]) & 0xFFFF

        sha = hashlib.sha256(self._simulated_bin).hexdigest()

        return {
            "size": len(self._simulated_bin),
            "sectors": sectors,
            "sectors_used": sum(1 for s in sectors.values() if s == "used"),
            "sectors_erased": sum(1 for s in sectors.values() if s == "erased"),
            "checksum": cs_sum,
            "stored_checksum": (self._simulated_bin[0x4006] << 8) | self._simulated_bin[0x4007],
            "sha256": sha,
            "source_file": self._bin_path,
        }

    def open(self) -> None:
        self._opened = True
        # Pre-seed a heartbeat byte so detect_heartbeat() succeeds immediately
        # On a real bus the ECU broadcasts its device_id periodically — simulate that
        self._rx_buffer.extend(bytes([DeviceID.VX_VY_F7]))
        label = f"Virtual ECU ({Path(self._bin_path).name})" if self._vecu_mode else "Loopback"
        log.info("%s transport opened (simulation mode)", label)

    def close(self) -> None:
        self._opened = False

    def write(self, data: bytes) -> int:
        self._tx_log.append(bytes(data))
        # Simulate ECU response
        self._simulate_response(data)
        return len(data)

    def read(self, count: int, timeout_ms: int = 2000) -> bytes:
        result = bytes(self._rx_buffer[:count])
        self._rx_buffer = self._rx_buffer[count:]
        return result

    def flush_input(self) -> None:
        self._rx_buffer.clear()

    def flush_output(self) -> None:
        pass

    @property
    def is_open(self) -> bool:
        return self._opened

    @property
    def bytes_available(self) -> int:
        return len(self._rx_buffer)

    # Pre-built sector lookup — avoids rebuilding dict on every call (#14 fix)
    _SECTOR_OFFSET_MAP = {
        (FlashBank.BANK_72, FlashSector.SECTOR_0): 0x00000,
        (FlashBank.BANK_72, FlashSector.SECTOR_1): 0x04000,
        (FlashBank.BANK_72, FlashSector.SECTOR_2): 0x08000,
        (FlashBank.BANK_72, FlashSector.SECTOR_3): 0x0C000,
        (FlashBank.BANK_88, FlashSector.SECTOR_4): 0x10000,
        (FlashBank.BANK_88, FlashSector.SECTOR_5): 0x14000,
        (FlashBank.BANK_80, FlashSector.SECTOR_6): 0x18000,
        (FlashBank.BANK_80, FlashSector.SECTOR_7): 0x1C000,
    }

    def _sector_to_file_offset(self, bank: int, sector_byte: int) -> Optional[int]:
        """Map (bank, sector_byte) to flat file offset for sector erase.

        Each sector is 16KB. The sector_byte encodes the sector address within the bank
        (the high byte of the 16-bit base address within the 64KB bank window).

        Returns the flat 128KB file offset for the start of the sector, or None if invalid.
        """
        return self._SECTOR_OFFSET_MAP.get((bank, sector_byte))

    def _simulate_response(self, data: bytes) -> None:
        """Generate simulated ECU responses based on sent frames."""
        if len(data) < 3:
            return
        device_id = data[0]
        mode = data[2]

        if mode == ALDLMode.MODE8_SILENCE:
            # Echo silence frame back
            resp = bytearray([device_id, 0x56, ALDLMode.MODE8_SILENCE])
            cs = (256 - sum(resp) % 256) & 0xFF
            resp.append(cs)
            self._rx_buffer.extend(resp)

        elif mode == ALDLMode.MODE13_SECURITY:
            subcommand = data[3] if len(data) > 3 else 0
            if subcommand == 0x01:
                # Return seed
                resp = bytearray([device_id, 0x59, 0x0D, 0x01, 0x12, 0x34])
                cs = (256 - sum(resp) % 256) & 0xFF
                resp.append(cs)
                self._rx_buffer.extend(resp)
            elif subcommand == 0x02:
                # Accept key
                self._unlocked = True
                resp = bytearray([device_id, 0x58, 0x0D, 0x02, 0xAA])
                cs = (256 - sum(resp) % 256) & 0xFF
                resp.append(cs)
                self._rx_buffer.extend(resp)

        elif mode == ALDLMode.MODE5_ENTER_PROG:
            resp = bytearray([device_id, 0x57, 0x05, 0xAA])
            cs = (256 - sum(resp) % 256) & 0xFF
            resp.append(cs)
            self._rx_buffer.extend(resp)

        elif mode == ALDLMode.MODE6_UPLOAD:
            # Detect if this is an erase frame or write-bank-setup frame
            # Erase frame: length byte = 0xBF (191), bank at byte[105], sector at byte[106]
            # Write bank frame: length byte = 0xF1 (241), bank at byte[157]
            length_byte = data[1] if len(data) > 1 else 0
            if length_byte == 0xBF and len(data) >= 108:
                # Erase frame — simulate sector erase by setting 16KB to 0xFF
                bank = data[105]
                sector_byte = data[106]
                # Map (bank, sector_byte) to flat file offset
                # Sector addresses: 0x00=sector0, 0x40=sector1, 0x80=sector2/6, 0xC0=sector3/5/7
                sector_base = self._sector_to_file_offset(bank, sector_byte)
                if sector_base is not None:
                    for addr in range(sector_base, sector_base + 16384):
                        self._simulated_bin[addr] = 0xFF
                    log.debug("vEEPROM: erased sector at $%05X-$%05X (bank=0x%02X, sector=0x%02X)",
                              sector_base, sector_base + 16383, bank, sector_byte)
            elif length_byte == 0xF1 and len(data) >= 158:
                # Write bank setup — track the active write bank for Mode 16 remapping
                self._active_write_bank = data[157]
                # Determine PCM base offset for address remapping
                if self._active_write_bank == FlashBank.BANK_72:
                    self._write_bank_pcm_base = 0
                elif self._active_write_bank == FlashBank.BANK_88:
                    self._write_bank_pcm_base = 0x8000
                elif self._active_write_bank == FlashBank.BANK_80:
                    self._write_bank_pcm_base = 0x10000
                log.debug("vEEPROM: write bank set to 0x%02X (pcm_base=$%05X)",
                          self._active_write_bank, self._write_bank_pcm_base)
            resp = bytearray([device_id, 0x57, 0x06, 0xAA])
            cs = (256 - sum(resp) % 256) & 0xFF
            resp.append(cs)
            self._rx_buffer.extend(resp)

        elif mode == ALDLMode.MODE1_DATASTREAM:
            # Return 60 bytes of simulated sensor data
            sensor_data = bytearray(60)
            sensor_data[0] = 0x00  # RPM hi (800 RPM = 32 * 25)
            sensor_data[1] = 0x20  # RPM lo
            sensor_data[5] = 120   # ECT = 120*0.75-40 = 50°C
            sensor_data[29] = 140  # Battery = 14.0V
            sensor_data[42] = 30   # IAC = 30 steps
            resp = bytearray([device_id, 0x56 + 60, ALDLMode.MODE1_DATASTREAM])
            resp.extend(sensor_data)
            cs = (256 - sum(resp) % 256) & 0xFF
            resp.append(cs)
            self._rx_buffer.extend(resp)

        elif mode == ALDLMode.MODE2_READ_RAM:
            # Serve data from the simulated bin image
            extended = (data[1] == 0x59)  # 3-byte address vs 2-byte
            if extended and len(data) >= 6:
                address = (data[3] << 16) | (data[4] << 8) | data[5]
            elif len(data) >= 5:
                address = (data[3] << 8) | data[4]
            else:
                address = 0
            block_size = 64
            if address + block_size > len(self._simulated_bin):
                block_size = max(0, len(self._simulated_bin) - address)
            block = self._simulated_bin[address:address + block_size]
            # Response: [device_id, 0x55 + block_size + 1, mode, ...data..., checksum]
            resp = bytearray([device_id, 0x55 + len(block) + 1, ALDLMode.MODE2_READ_RAM])
            resp.extend(block)
            cs = (256 - sum(resp) % 256) & 0xFF
            resp.append(cs)
            self._rx_buffer.extend(resp)

        elif mode == ALDLMode.MODE9_UNSILENCE:
            # ACK unsilence — same frame format as silence ACK
            resp = bytearray([device_id, 0x56, ALDLMode.MODE9_UNSILENCE])
            cs = (256 - sum(resp) % 256) & 0xFF
            resp.append(cs)
            self._rx_buffer.extend(resp)

        elif mode == ALDLMode.MODE3_READ_BYTES:
            # Read N bytes from an address — similar to Mode 2 but variable length
            if len(data) >= 6:
                address = (data[3] << 8) | data[4]
                count = data[5] if data[5] > 0 else 1
            else:
                address = 0
                count = 1
            if address + count > len(self._simulated_bin):
                count = max(0, len(self._simulated_bin) - address)
            block = self._simulated_bin[address:address + count]
            resp = bytearray([device_id, 0x55 + len(block) + 1, ALDLMode.MODE3_READ_BYTES])
            resp.extend(block)
            cs = (256 - sum(resp) % 256) & 0xFF
            resp.append(cs)
            self._rx_buffer.extend(resp)

        elif mode == ALDLMode.MODE4_ACTUATOR:
            # ACK actuator test command
            resp = bytearray([device_id, 0x57, ALDLMode.MODE4_ACTUATOR, 0xAA])
            cs = (256 - sum(resp) % 256) & 0xFF
            resp.append(cs)
            self._rx_buffer.extend(resp)

        elif mode == ALDLMode.MODE10_WRITE_CAL:
            # ACK cal write (live tune RAM shadow write)
            resp = bytearray([device_id, 0x57, ALDLMode.MODE10_WRITE_CAL, 0xAA])
            cs = (256 - sum(resp) % 256) & 0xFF
            resp.append(cs)
            self._rx_buffer.extend(resp)

        elif mode == ALDLMode.MODE16_FLASH_WRITE:
            # Simulate write: parse address + data from frame, write to vEEPROM
            # Frame format: [device_id, length, 0x10, addr_hi, addr_mid, addr_lo, data..., checksum]
            if len(data) >= 7:
                pcm_addr = (data[3] << 16) | (data[4] << 8) | data[5]
                payload = data[6:-1]  # everything between address and checksum
                if len(payload) > 0:
                    # Reverse the address remapping to get flat file offset
                    # write_flash_data does: pcm_addr = file_addr - pcm_base_offset
                    # So: file_addr = pcm_addr + pcm_base_offset
                    flat_base = pcm_addr + self._write_bank_pcm_base
                    for i, b in enumerate(payload):
                        flat_addr = flat_base + i
                        if 0 <= flat_addr < len(self._simulated_bin):
                            # NOR flash AND rule: can only clear bits (1→0)
                            # Erased bytes are 0xFF, programming ANDs with new data
                            self._simulated_bin[flat_addr] &= b
                    log.debug("vEEPROM: wrote %d bytes at PCM $%05X → file $%05X (bank 0x%02X)",
                              len(payload), pcm_addr, flat_base, self._active_write_bank)
            # ACK
            resp = bytearray([device_id, 0x57, ALDLMode.MODE16_FLASH_WRITE, 0xAA])
            cs = (256 - sum(resp) % 256) & 0xFF
            resp.append(cs)
            self._rx_buffer.extend(resp)


# ═══════════════════════════════════════════════════════════════════════
# SECTION 7 — ECU COMMUNICATION ENGINE
# ═══════════════════════════════════════════════════════════════════════

class CommState(Enum):
    """Communication state machine."""
    DISCONNECTED = auto()
    CONNECTED = auto()
    SILENCED = auto()
    UNLOCKED = auto()
    PROGRAMMING = auto()
    KERNEL_LOADED = auto()
    FLASHING = auto()
    DATALOG = auto()
    LIVE_TUNE = auto()
    ERROR = auto()

@dataclass
class LogConfig:
    """Verbose event bus logging settings — toggle what gets logged.

    Each flag controls whether the event bus fires and the file logger records
    that category of event.  All default to True.  Stored in settings.json
    and toggled from the Options tab or the Tools → Logging menu.
    """
    # ── Frame-level (DEBUG) ──
    log_tx_frames: bool = True          # Every TX frame hex dump
    log_rx_frames: bool = True          # Every RX frame hex dump
    log_echo_bytes: bool = False        # Echo consume details (noisy)

    # ── Operation-level (INFO) ──
    log_state_changes: bool = True      # CommState transitions
    log_security: bool = True           # Seed/key exchange
    log_kernel_upload: bool = True      # Kernel block uploads
    log_erase_sectors: bool = True      # Per-sector erase start/done
    log_write_chunks: bool = True       # Per-chunk write progress
    log_verify: bool = True             # Checksum verify pass/fail
    log_flash_info: bool = True         # Flash chip ID reads
    log_chatter: bool = True            # Bus silence/unsilence
    log_progress: bool = True           # Progress bar updates

    # ── Error/Warning (WARNING+) ──
    log_retries: bool = True            # Every retry attempt
    log_timeouts: bool = True           # Frame timeouts
    log_checksum_errors: bool = True    # RX checksum failures

    # ── Session-level ──
    log_session_summary: bool = True    # Flash session summary box
    log_click_events: bool = False      # GUI button clicks (off by default)
    log_timestamps: bool = True         # Timestamps on every event


@dataclass
class CommConfig:
    """Communication configuration."""
    device_id: int = DeviceID.VX_VY_F7
    baud: int = DEFAULT_BAUD
    timeout_ms: int = DEFAULT_TIMEOUT_MS
    inter_frame_delay_ms: int = DEFAULT_INTER_FRAME_DELAY_MS
    max_retries: int = DEFAULT_MAX_RETRIES
    write_chunk_size: int = DEFAULT_WRITE_CHUNK_SIZE
    high_speed_read: bool = False
    ignore_echo: bool = True
    echo_byte_count: int = 0
    bcm_device_id: int = 0x08
    disable_bcm_chatter: bool = False   # Skip BCM silence — OFF by default (bench/virtual setups have no BCM)
    auto_checksum_fix: bool = True


# ── Settings Persistence ──

SETTINGS_FILE = Path(__file__).resolve().parent / "settings.json"

class SettingsManager:
    """Persist CommConfig + LogConfig to JSON.  Loads on startup, saves on change.

    Settings stored next to the script as settings.json.  If the file doesn't
    exist or is corrupt, defaults are used silently.
    """

    @staticmethod
    def save(comm: CommConfig, log_cfg: LogConfig, path: Path = None) -> None:
        """Write current settings to disk."""
        path = path or SETTINGS_FILE
        data = {
            "comm": {k: v for k, v in comm.__dict__.items()},
            "logging": {k: v for k, v in log_cfg.__dict__.items()},
        }
        try:
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
            tmp.replace(path)
            log.debug("Settings saved → %s", path)
        except Exception as e:
            log.error("Failed to save settings: %s", e)

    @staticmethod
    def load(path: Path = None) -> Tuple[CommConfig, LogConfig]:
        """Load settings from disk.  Returns defaults on any error."""
        path = path or SETTINGS_FILE
        comm = CommConfig()
        log_cfg = LogConfig()
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                for k, v in data.get("comm", {}).items():
                    if hasattr(comm, k):
                        setattr(comm, k, v)
                for k, v in data.get("logging", {}).items():
                    if hasattr(log_cfg, k):
                        setattr(log_cfg, k, v)
                log.debug("Settings loaded ← %s", path)
        except Exception as e:
            log.warning("Could not load settings (%s), using defaults", e)
        return comm, log_cfg


# ── Crash Recovery State ──

RECOVERY_STATE_FILE = Path(__file__).resolve().parent / "flash_recovery_state.json"

@dataclass
class RecoveryState:
    """Persisted to disk after every state change during flash operations.

    If the app crashes mid-flash, this file tells us exactly what happened:
    which sectors are erased, which are written, and where to resume.
    """
    session_id: str = ""
    timestamp: str = ""
    phase: str = "idle"             # idle, erasing, writing, verifying, complete
    backup_file: str = ""           # Path to pre-write backup .bin
    write_file: str = ""            # Path to .bin being written
    write_mode: str = "BIN"         # CAL / BIN / PROM
    sectors_erased: List[int] = field(default_factory=list)
    sectors_written: List[int] = field(default_factory=list)
    last_write_address: int = 0     # Last successfully written file offset
    total_bytes: int = 0
    bytes_written: int = 0
    checksum_verified: bool = False
    eeprom_written: bool = False

    def save(self, path: Path = None) -> None:
        """Atomic write to disk."""
        path = path or RECOVERY_STATE_FILE
        self.timestamp = datetime.now().isoformat()
        try:
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.__dict__, indent=2), encoding="utf-8")
            tmp.replace(path)
        except Exception as e:
            log.error("Failed to save recovery state: %s", e)

    @classmethod
    def load(cls, path: Path = None) -> Optional["RecoveryState"]:
        """Load from disk.  Returns None if no file or corrupt."""
        path = path or RECOVERY_STATE_FILE
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                state = cls()
                for k, v in data.items():
                    if hasattr(state, k):
                        setattr(state, k, v)
                return state
        except Exception:
            pass
        return None

    @staticmethod
    def clear(path: Path = None) -> None:
        """Delete the recovery file (normal completion)."""
        path = path or RECOVERY_STATE_FILE
        try:
            if path.exists():
                path.unlink()
        except Exception:
            pass

    @property
    def is_interrupted(self) -> bool:
        """True if a previous session was interrupted mid-flash."""
        return self.phase in ("erasing", "writing")

class ECUComm:
    """
    High-level ECU communication engine.
    Handles framing, echo detection, silence, retries, and state management.
    """

    def __init__(self, transport: BaseTransport, config: CommConfig = None,
                 log_cfg: LogConfig = None):
        self.transport = transport
        self.config = config or CommConfig()
        self.log_cfg = log_cfg or LogConfig()
        self.state = CommState.DISCONNECTED
        self._cancel = threading.Event()
        self._lock = threading.Lock()
        self._callbacks: Dict[str, List[Callable]] = {}
        self._rx_frame_log: List[Tuple[float, bytes]] = []
        self._tx_frame_log: List[Tuple[float, bytes]] = []

    # ── Event System ──

    def clear_callbacks(self, event: Optional[str] = None) -> None:
        """Remove registered callbacks. If *event* given, clear only that event; otherwise clear all."""
        if event:
            self._callbacks.pop(event, None)
        else:
            self._callbacks.clear()

    def on(self, event: str, callback: Callable) -> None:
        """Register an event callback. Events: log, progress, state, error, data, frame_tx, frame_rx, etc."""
        self._callbacks.setdefault(event, []).append(callback)

    def emit(self, event: str, **kwargs) -> None:
        """Emit an event to all registered callbacks."""
        # Add timestamp if logging timestamps enabled
        if self.log_cfg.log_timestamps and "ts" not in kwargs:
            kwargs["ts"] = time.monotonic()
        for cb in self._callbacks.get(event, []):
            try:
                cb(**kwargs)
            except Exception as e:
                log.error("Event callback error: %s", e)
        # Also fire wildcard subscribers
        for cb in self._callbacks.get("*", []):
            try:
                cb(event=event, **kwargs)
            except Exception:
                pass

    def cancel(self) -> None:
        """Cancel the current operation."""
        self._cancel.set()
        self.emit("log", msg="Operation cancelled by user", level="warning")

    def reset_cancel(self) -> None:
        """Reset the cancel flag."""
        self._cancel.clear()

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    # ── Low-Level Frame I/O ──

    def _tx_frame(self, frame: bytearray) -> bool:
        """Transmit an ALDL frame with echo handling and silence detection."""
        wire_len = ALDLProtocol.wire_length(frame)
        wire_bytes = bytes(frame[:wire_len])

        # Log TX
        self._tx_frame_log.append((time.monotonic(), wire_bytes))
        log.debug("TX [%d]: %s", wire_len, wire_bytes.hex(" "))
        if self.log_cfg.log_tx_frames:
            self.emit("frame_tx", frame_hex=wire_bytes.hex(" "), length=wire_len)

        # Wait for silence
        if not self._wait_silence():
            log.warning("Bus congestion — could not get clear slot")
            if self.log_cfg.log_timeouts:
                self.emit("log", msg="Bus congestion — could not get clear slot", level="warning")
            return False

        # Inter-frame delay
        time.sleep(self.config.inter_frame_delay_ms / 1000.0)

        # Flush and transmit
        self.transport.flush_input()
        self.transport.write(wire_bytes)

        # Consume echo if present
        if self.config.ignore_echo and self.config.echo_byte_count > 0:
            echo = self.transport.read(self.config.echo_byte_count, timeout_ms=ECHO_DETECT_TIMEOUT_MS)
            log.debug("Echo consumed [%d]: %s", len(echo), echo.hex(" ") if echo else "empty")
            if self.log_cfg.log_echo_bytes:
                self.emit("log", msg=f"Echo consumed [{len(echo)}]: {echo.hex(' ') if echo else 'empty'}", level="debug")

        return True

    def _rx_frame(self, timeout_ms: int = None) -> Optional[bytearray]:
        """Receive one ALDL frame. Returns None on timeout."""
        timeout_ms = timeout_ms or self.config.timeout_ms
        deadline = time.monotonic() + timeout_ms / 1000.0

        # Read device ID byte
        header = self.transport.read(1, timeout_ms=timeout_ms)
        if not header:
            return None

        # Read length byte
        remaining_time = max(1, int((deadline - time.monotonic()) * 1000))
        length_byte_raw = self.transport.read(1, timeout_ms=remaining_time)
        if not length_byte_raw:
            return None

        length_byte = length_byte_raw[0]
        if length_byte < 0x55:
            log.warning("Invalid length byte 0x%02X — discarding", length_byte)
            return None

        # Calculate remaining bytes to read
        wire_len = length_byte - 82
        remaining = wire_len - 2  # already read 2 bytes (device_id + length)

        if remaining <= 0 or remaining > 200:
            log.warning("Invalid frame length %d", remaining)
            return None

        remaining_time = max(1, int((deadline - time.monotonic()) * 1000))
        body = self.transport.read(remaining, timeout_ms=remaining_time)
        if len(body) < remaining:
            log.warning("Incomplete frame: expected %d more bytes, got %d", remaining, len(body))
            return None

        # Reconstruct full frame
        frame = bytearray(201)
        frame[0] = header[0]
        frame[1] = length_byte
        for i, b in enumerate(body):
            frame[2 + i] = b

        # Verify checksum
        if not ALDLProtocol.verify_checksum(frame):
            log.warning("Checksum error on RX frame: %s", bytes(frame[:wire_len]).hex(" "))
            if self.log_cfg.log_checksum_errors:
                self.emit("log", msg=f"Checksum error on RX: {bytes(frame[:wire_len]).hex(' ')}", level="warning")
            return None

        # Log RX
        self._rx_frame_log.append((time.monotonic(), bytes(frame[:wire_len])))
        log.debug("RX [%d]: %s", wire_len, bytes(frame[:wire_len]).hex(" "))
        if self.log_cfg.log_rx_frames:
            self.emit("frame_rx", frame_hex=bytes(frame[:wire_len]).hex(" "), length=wire_len, checksum_ok=True)

        return frame

    def _transact(self, frame: bytearray, timeout_ms: int = None,
                  retries: int = None) -> Optional[bytearray]:
        """Send a frame and wait for response, with retries.

        On each failed attempt the RX buffer is flushed and a short delay
        inserted so the bus can settle.  Without this, stale/shifted bytes
        from the previous response cause every subsequent retry to see the
        same garbage (wrong length byte, checksum errors, incomplete frames).
        """
        retries = retries if retries is not None else self.config.max_retries
        timeout_ms = timeout_ms or self.config.timeout_ms

        with self._lock:  # thread-safe serial access (#5 fix)
            for attempt in range(retries):
                if self.cancelled:
                    return None

                if not self._tx_frame(frame):
                    time.sleep(0.05)
                    continue

                resp = self._rx_frame(timeout_ms=timeout_ms)
                if resp is not None:
                    return resp

                # ── Failed: resync bus before next attempt ──
                self.transport.flush_input()
                time.sleep(INTER_RETRY_DELAY_MS / 1000.0)

                log.info("No response, retry %d/%d", attempt + 1, retries)
                if self.log_cfg.log_retries:
                    self.emit("log", msg=f"No response, retry {attempt+1}/{retries}", level="warning")
                    self.emit("retry", attempt=attempt + 1, max_retries=retries, reason="timeout")

        log.error("Transaction failed after %d retries", retries)
        if self.log_cfg.log_timeouts:
            self.emit("log", msg=f"Transaction failed after {retries} retries", level="error")
        return None

    def _wait_silence(self, wait_ms: int = None) -> bool:
        """Wait for bus silence before transmitting."""
        wait_ms = wait_ms or SILENCE_WAIT_MS
        deadline = time.monotonic() + self.config.timeout_ms / 1000.0

        while time.monotonic() < deadline:
            if self.cancelled:
                return False
            self.transport.flush_input()
            time.sleep(wait_ms / 1000.0)
            if self.transport.bytes_available == 0:
                return True
        return False

    # ── Echo Detection ──

    def detect_echo(self) -> bool:
        """Detect if the ALDL cable echoes transmitted bytes."""
        self.transport.flush_input()
        test = bytes([0xFF, 0x55])
        self.transport.write(test)
        time.sleep(0.1)
        response = self.transport.read(2, timeout_ms=ECHO_DETECT_TIMEOUT_MS)
        if response == test:
            self.config.ignore_echo = True
            self.config.echo_byte_count = 2  # Will be set properly per-frame
            self.emit("log", msg="Echo detected — will consume echo bytes", level="info")
            log.info("Echo detected")
            return True
        else:
            self.config.ignore_echo = False
            self.config.echo_byte_count = 0
            self.emit("log", msg="No echo detected", level="info")
            log.info("No echo detected")
            return False

    # ── High-Level Operations ──

    def detect_heartbeat(self) -> bool:
        """Listen for periodic ECM heartbeat frames on the ALDL bus.
        OSE waits for heartbeat to confirm ECU is alive before proceeding."""
        self.emit("log", msg="Listening for ECM heartbeat...", level="info")
        deadline = time.monotonic() + HEARTBEAT_TIMEOUT_MS / 1000.0
        while time.monotonic() < deadline:
            data = self.transport.read(1, timeout_ms=500)
            if data and data[0] == self.config.device_id:
                # Got a byte matching our device ID — likely a heartbeat frame
                self.emit("log", msg=f"Heartbeat detected (0x{data[0]:02X})", level="info")
                log.info(f"Heartbeat detected: 0x{data[0]:02X}")
                self.transport.flush_input()
                return True
        self.emit("log", msg="No heartbeat detected (ECU may be off or not responding)", level="warning")
        log.warning("No heartbeat detected")
        return False

    def connect(self) -> bool:
        """Open transport and establish initial connection."""
        try:
            self.transport.open()
        except TransportError as e:
            self.emit("log", msg=str(e), level="error")
            self.state = CommState.ERROR
            return False

        self.state = CommState.CONNECTED
        self.emit("state", state=self.state)
        self.emit("log", msg=f"Connected via {type(self.transport).__name__}", level="info")

        # Detect heartbeat (confirm ECU is alive)
        self.detect_heartbeat()

        # Detect echo
        has_echo = self.detect_echo()
        if has_echo:
            # Echo byte count set dynamically per-frame in _tx_frame
            pass

        return True

    def disconnect(self) -> None:
        """Close transport and reset state."""
        try:
            self.transport.close()
        except Exception:
            pass
        self.state = CommState.DISCONNECTED
        self.emit("state", state=self.state)

    def disable_chatter(self) -> bool:
        """Send Mode 8 to silence BCM and ECM chatter on the ALDL bus."""
        # Silence BCM first (if configured and enabled)
        if self.config.bcm_device_id and self.config.disable_bcm_chatter:
            frame = ALDLProtocol.build_silence_frame(self.config.bcm_device_id)
            if self.config.ignore_echo:
                self.config.echo_byte_count = ALDLProtocol.wire_length(frame)
            self._transact(frame, timeout_ms=1000, retries=2)
        elif not self.config.disable_bcm_chatter:
            self.emit("log", msg="BCM silence skipped (disabled in options)", level="info")

        # Silence ECM
        frame = ALDLProtocol.build_silence_frame(self.config.device_id)
        if self.config.ignore_echo:
            self.config.echo_byte_count = ALDLProtocol.wire_length(frame)
        resp = self._transact(frame, timeout_ms=2000, retries=5)
        if resp and resp[2] == ALDLMode.MODE8_SILENCE:
            self.state = CommState.SILENCED
            self.emit("state", state=self.state)
            self.emit("log", msg="Bus chatter disabled", level="info")
            return True

        self.emit("log", msg="Failed to disable chatter", level="error")
        return False

    def enable_chatter(self) -> bool:
        """Send Mode 9 to re-enable ALDL bus chatter.

        After a flash write or read the PCM needs time to stabilise before
        chatter restarts.  A too-fast re-enable after the last bank write was
        suspected of causing intermittent issues in the original OSE tool.
        We now wait POST_CHATTER_DELAY_MS after sending the Mode 9 frame.
        """
        frame = ALDLProtocol.build_unsilence_frame(self.config.device_id)
        if self.config.ignore_echo:
            self.config.echo_byte_count = ALDLProtocol.wire_length(frame)
        resp = self._transact(frame, timeout_ms=2000, retries=3)
        # Allow the PCM to settle before anything else touches the bus
        time.sleep(POST_CHATTER_DELAY_MS / 1000.0)
        self.state = CommState.CONNECTED
        self.emit("state", state=self.state)
        if resp is None:
            self.emit("log", msg="Bus chatter re-enable: no ACK (PCM may still be silent)", level="warning")
            return False
        self.emit("log", msg="Bus chatter re-enabled", level="info")
        return True

    def unlock_security(self) -> bool:
        """Mode 13 seed/key security unlock."""
        self.emit("log", msg="Requesting security seed...", level="info")

        # Request seed
        frame = ALDLProtocol.build_seed_request(self.config.device_id)
        if self.config.ignore_echo:
            self.config.echo_byte_count = ALDLProtocol.wire_length(frame)
        resp = self._transact(frame, timeout_ms=3000)
        if not resp:
            self.emit("log", msg="No seed response", level="error")
            return False

        seed_hi = resp[4]
        seed_lo = resp[5]
        log.info("Seed received: 0x%02X 0x%02X", seed_hi, seed_lo)

        if seed_hi == 0 and seed_lo == 0:
            self.emit("log", msg="Already unlocked (seed=0)", level="info")
            self.state = CommState.UNLOCKED
            self.emit("state", state=self.state)
            return True

        # Compute key
        key = ALDLProtocol.compute_seed_key(seed_hi, seed_lo)
        log.info("Key computed: 0x%04X (from seed 0x%02X%02X)", key, seed_hi, seed_lo)
        self.emit("log", msg=f"Key computed: 0x{key:04X}", level="info")

        # Send key
        frame = ALDLProtocol.build_key_response(self.config.device_id, key)
        if self.config.ignore_echo:
            self.config.echo_byte_count = ALDLProtocol.wire_length(frame)
        resp = self._transact(frame, timeout_ms=3000)
        if not resp:
            self.emit("log", msg="No key response", level="error")
            return False

        if len(resp) > 4 and resp[4] == 0xAA:
            self.state = CommState.UNLOCKED
            self.emit("state", state=self.state)
            self.emit("log", msg="Security unlocked!", level="info")
            return True
        else:
            result = resp[4] if len(resp) > 4 else 0xFF
            self.emit("log", msg=f"Key rejected (result=0x{result:02X})", level="error")
            return False

    def enter_programming(self) -> bool:
        """Mode 5 — enter programming mode."""
        self.emit("log", msg="Entering programming mode...", level="info")
        frame = ALDLProtocol.build_mode5_request(self.config.device_id)
        if self.config.ignore_echo:
            self.config.echo_byte_count = ALDLProtocol.wire_length(frame)
        resp = self._transact(frame, timeout_ms=MODE5_TIMEOUT_MS)
        if resp and len(resp) > 3 and resp[3] == 0xAA:
            self.state = CommState.PROGRAMMING
            self.emit("state", state=self.state)
            self.emit("log", msg="Programming mode active", level="info")
            return True

        result = resp[3] if resp and len(resp) > 3 else 0xFF
        if result != 0xAA:
            self.emit("log", msg="Mode 5 denied — vehicle may be moving", level="error")
        return False

    def upload_kernel(self) -> bool:
        """Mode 6 — upload the HC11 flash kernel to PCM RAM (3 blocks)."""
        self.emit("log", msg="Uploading flash kernel...", level="info")
        blocks = FlashKernel.get_exec_blocks(self.config.high_speed_read)

        for i, block in enumerate(blocks):
            self.emit("log", msg=f"  Kernel block {i}/2 ({len(block)} bytes)...", level="info")
            self.emit("progress", current=i, total=3, label="Uploading kernel")

            frame = bytearray(201)
            for j in range(len(block)):
                frame[j] = block[j]
            ALDLProtocol.apply_checksum(frame)

            if self.config.ignore_echo:
                self.config.echo_byte_count = ALDLProtocol.wire_length(frame)

            resp = self._transact(frame, timeout_ms=MODE6_UPLOAD_TIMEOUT_MS)
            if not resp or resp[3] != 0xAA:
                self.emit("log", msg=f"Kernel block {i} upload failed", level="error")
                return False

            if self.cancelled:
                return False

        self.state = CommState.KERNEL_LOADED
        self.emit("state", state=self.state)
        self.emit("log", msg="Flash kernel uploaded and running", level="info")
        return True

    def read_flash_info(self) -> Optional[Tuple[int, int]]:
        """Read flash chip manufacturer and device ID."""
        self.emit("log", msg="Reading flash chip info...", level="info")
        frame = bytearray(201)
        for i, b in enumerate(FlashKernel.FLASH_INFO):
            frame[i] = b
        ALDLProtocol.apply_checksum(frame)

        if self.config.ignore_echo:
            self.config.echo_byte_count = ALDLProtocol.wire_length(frame)

        resp = self._transact(frame, timeout_ms=MODE6_UPLOAD_TIMEOUT_MS)
        if not resp:
            self.emit("log", msg="No flash info response", level="error")
            return None

        manuf = resp[3]
        device = resp[4]
        self.emit("log", msg=f"Flash chip: Manufacturer=0x{manuf:02X}, Device=0x{device:02X}", level="info")

        if (manuf, device) == FLASH_AMD_29F010:
            self.emit("log", msg="  → AMD 29F010 (128KB) ✓", level="info")
        elif (manuf, device) == FLASH_AMD_29F040:
            self.emit("log", msg="  → AMD 29F040 (512KB)", level="info")
        elif (manuf, device) == FLASH_CAT_28F010:
            self.emit("log", msg="  → CAT28F010 (128KB)", level="info")
        else:
            self.emit("log", msg="  → Unknown flash chip!", level="warning")

        return (manuf, device)

    def erase_sectors(self, erase_map: List[Tuple[int, int]]) -> bool:
        """Erase specified flash sectors."""
        total = len(erase_map)
        for i, (bank, sector) in enumerate(erase_map):
            if self.cancelled:
                return False

            self.emit("log", msg=f"Erasing sector {i+1}/{total} (bank=0x{bank:02X}, sector=0x{sector:02X})...",
                       level="info")
            self.emit("progress", current=i, total=total, label="Erasing")

            frame = bytearray(201)
            erase_frame = FlashKernel.get_erase_frame(bank, sector)
            for j in range(len(erase_frame)):
                frame[j] = erase_frame[j]
            ALDLProtocol.apply_checksum(frame)

            if self.config.ignore_echo:
                self.config.echo_byte_count = ALDLProtocol.wire_length(frame)

            resp = self._transact(frame, timeout_ms=ERASE_TIMEOUT_MS, retries=3)
            if not resp or resp[3] != 0xAA:
                result = resp[3] if resp and len(resp) > 3 else 0xFF
                self.emit("log", msg=f"Erase sector {i+1} failed (result=0x{result:02X})", level="error")
                return False

            self.emit("log", msg=f"  Sector {i+1} erased ✓", level="info")

        self.emit("log", msg=f"All {total} sectors erased successfully", level="info")
        return True

    def write_flash_data(self, bin_data: bytes, start_offset: int, end_offset: int,
                         callback: Callable = None) -> bool:
        """
        Write data to flash via the uploaded kernel, bank by bank.

        OSE address remapping:
          Bank 72: file offsets map 1:1 to PCM addresses (no remap)
          Bank 88: file offsets $10000-$17FFF → remapped to PCM addresses $8000-$FFFF
          Bank 80: file offsets $18000-$1FFFF → remapped to PCM addresses $8000-$FFFF

        The kernel sees a $8000-$FFFF window. The bank register selects which physical
        flash bank is mapped there. OSE copies file data into a temp array at the
        windowed offset before writing; we achieve the same by subtracting pcm_base_offset.
        """
        self.state = CommState.FLASHING
        self.emit("state", state=self.state)

        chunk_size = self.config.write_chunk_size
        total_bytes = end_offset - start_offset + 1
        bytes_written = 0
        retries = 0
        start_time = time.monotonic()

        for bank_byte, bank_start, bank_end, pcm_base_offset in BANK_WRITE_MAP:
            # Determine intersection with requested write range
            w_start = max(start_offset, bank_start)
            w_end = min(end_offset, bank_end)
            if w_start > w_end:
                continue

            # Upload write-bank setup
            self.emit("log", msg=f"Setting up write for bank 0x{bank_byte:02X} "
                      f"(file ${w_start:05X}-${w_end:05X})...", level="info")
            frame = bytearray(201)
            wb_frame = FlashKernel.get_write_bank_frame(bank_byte)
            for j in range(len(wb_frame)):
                frame[j] = wb_frame[j]
            ALDLProtocol.apply_checksum(frame)

            if self.config.ignore_echo:
                self.config.echo_byte_count = ALDLProtocol.wire_length(frame)

            resp = self._transact(frame, timeout_ms=MODE6_UPLOAD_TIMEOUT_MS)
            if not resp or resp[3] != 0xAA:
                self.emit("log", msg=f"Write bank setup failed for 0x{bank_byte:02X}", level="error")
                return False

            # Write data in chunks
            file_addr = w_start
            while file_addr <= w_end:
                if self.cancelled:
                    return False

                end = min(file_addr + chunk_size - 1, w_end)
                data_chunk = bin_data[file_addr:end + 1]
                actual_chunk_size = len(data_chunk)

                # Remap file offset to PCM windowed address
                # Bank 72: pcm_addr = file_addr (direct)
                # Bank 88: file $10000 → pcm $8000 (subtract $8000)
                # Bank 80: file $18000 → pcm $8000 (subtract $10000)
                pcm_addr = file_addr - pcm_base_offset

                # Build write frame with the remapped PCM address
                write_frame = ALDLProtocol.build_write_frame(
                    self.config.device_id, pcm_addr, data_chunk,
                    mode=ALDLMode.MODE16_FLASH_WRITE, extended=True
                )

                if self.config.ignore_echo:
                    self.config.echo_byte_count = ALDLProtocol.wire_length(write_frame)

                resp = self._transact(write_frame, timeout_ms=WRITE_FRAME_TIMEOUT_MS, retries=1)
                if resp and len(resp) > 3 and resp[3] == 0xAA:
                    bytes_written += actual_chunk_size
                    retries = 0

                    # Progress reporting
                    elapsed = time.monotonic() - start_time
                    pct = (bytes_written / total_bytes) * 100 if total_bytes > 0 else 100
                    rate = bytes_written / elapsed if elapsed > 0 else 0
                    eta = (total_bytes - bytes_written) / rate if rate > 0 else 0

                    self.emit("progress", current=bytes_written, total=total_bytes,
                              label=f"Writing ${file_addr:05X}→PCM ${pcm_addr:04X}")
                    if callback:
                        callback(bytes_written, total_bytes, rate, eta)

                    file_addr += actual_chunk_size
                else:
                    retries += 1
                    # Flush stale data from the bus before retrying
                    self.transport.flush_input()
                    time.sleep(INTER_RETRY_DELAY_MS / 1000.0)
                    self.emit("log",
                              msg=f"Write error at ${file_addr:05X} (PCM ${pcm_addr:04X}), "
                                  f"retry {retries}/{self.config.max_retries}",
                              level="warning")
                    if retries >= self.config.max_retries:
                        # Roll back file_addr to the start of the current 16KB sector
                        sector_start = (file_addr // SECTOR_SIZE) * SECTOR_SIZE
                        self.emit("log",
                                  msg=f"Too many write retries — aborting at ${file_addr:05X} "
                                      f"(sector ${sector_start:05X})",
                                  level="error")
                        return False

        elapsed = time.monotonic() - start_time
        rate = bytes_written / elapsed if elapsed > 0 else 0
        self.emit("log",
                  msg=f"Write complete: {bytes_written} bytes in {elapsed:.1f}s ({rate:.0f} B/s)",
                  level="info")
        return True

    def verify_checksum(self, bin_data: bytes) -> bool:
        """Run on-PCM checksum verification."""
        self.emit("log", msg="Running on-PCM checksum verification...", level="info")

        frame = bytearray(201)
        for i, b in enumerate(FlashKernel.CHECKSUM_BIN):
            frame[i] = b
        ALDLProtocol.apply_checksum(frame)

        if self.config.ignore_echo:
            self.config.echo_byte_count = ALDLProtocol.wire_length(frame)

        resp = self._transact(frame, timeout_ms=CHECKSUM_TIMEOUT_MS)
        if not resp:
            self.emit("log", msg="No checksum response", level="error")
            return False

        result = resp[3]
        if result == 0xAA:
            self.emit("log", msg="Checksum PASSED ✓", level="info")
            return True
        else:
            ecu_cs_hi = resp[4] if len(resp) > 4 else 0
            ecu_cs_lo = resp[5] if len(resp) > 5 else 0
            expected_hi = bin_data[CHECKSUM_OFFSET_HI] if len(bin_data) > CHECKSUM_OFFSET_HI else 0
            expected_lo = bin_data[CHECKSUM_OFFSET_LO] if len(bin_data) > CHECKSUM_OFFSET_LO else 0
            self.emit("log",
                      msg=f"Checksum FAILED — ECU=0x{ecu_cs_hi:02X}{ecu_cs_lo:02X}, "
                          f"expected=0x{expected_hi:02X}{expected_lo:02X}",
                      level="error")
            return False

    def cleanup_and_reset(self) -> bool:
        """Upload cleanup routine to reset the PCM."""
        self.emit("log", msg="Resetting PCM...", level="info")

        frame = bytearray(201)
        for i, b in enumerate(FlashKernel.CLEANUP):
            frame[i] = b
        ALDLProtocol.apply_checksum(frame)

        if self.config.ignore_echo:
            self.config.echo_byte_count = ALDLProtocol.wire_length(frame)

        resp = self._transact(frame, timeout_ms=5000)
        time.sleep(CLEANUP_DELAY_MS / 1000.0)

        self.state = CommState.CONNECTED
        self.emit("state", state=self.state)
        self.emit("log", msg="PCM reset complete", level="info")
        return True

    def request_mode1(self, message: int = 0) -> Optional[Dict[str, float]]:
        """Request and parse Mode 1 data stream."""
        frame = ALDLProtocol.build_mode1_request(self.config.device_id, message)
        if self.config.ignore_echo:
            self.config.echo_byte_count = ALDLProtocol.wire_length(frame)

        resp = self._transact(frame, timeout_ms=1000, retries=2)
        if not resp:
            return None

        # Extract data payload (starts at byte 3)
        data_len = resp[1] - 85 - 1  # total payload - mode byte
        if data_len <= 0 or data_len > 100:
            return None

        data = bytes(resp[3:3 + data_len])
        return ALDLProtocol.parse_mode1_response(data)

    def read_ram(self, address: int, count: int = 64, extended: bool = False) -> Optional[bytes]:
        """Read RAM/ROM bytes via Mode 2."""
        frame = ALDLProtocol.build_mode2_read(self.config.device_id, address, extended=extended)
        if self.config.ignore_echo:
            self.config.echo_byte_count = ALDLProtocol.wire_length(frame)

        resp = self._transact(frame, timeout_ms=2000)
        if not resp:
            return None

        # Data starts at byte 3
        data_len = resp[1] - 85 - 1
        if data_len <= 0:
            return None
        return bytes(resp[3:3 + data_len])


# ═══════════════════════════════════════════════════════════════════════
# SECTION 8 — BIN FILE UTILITIES
# ═══════════════════════════════════════════════════════════════════════

class BinFile:
    """Utilities for working with 128KB PCM binary files."""

    BIN_SIZE = 131072  # 128KB

    CAL_SIZE = 16384  # 16KB calibration area
    CAL_OFFSET = 0x4000  # Cal starts at $4000 in the 128KB image

    @staticmethod
    def load(path: str, allow_cal_padding: bool = True) -> bytearray:
        """Load a .bin file, validate size. Pads 16KB cal files to 128KB (like OSE)."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Bin file not found: {path}")
        data = bytearray(p.read_bytes())
        if len(data) == BinFile.CAL_SIZE and allow_cal_padding:
            # Pad 16KB cal to full 128KB image: cal lives at $4000-$7FFF,
            # rest is filled with 0xFF (erased flash state). Same as OSE.
            padded = bytearray(b'\xFF' * BinFile.BIN_SIZE)
            padded[BinFile.CAL_OFFSET:BinFile.CAL_OFFSET + BinFile.CAL_SIZE] = data
            log.info(f"Padded 16KB cal file to 128KB (cal at ${BinFile.CAL_OFFSET:04X})")
            return padded
        if len(data) != BinFile.BIN_SIZE:
            raise ValueError(f"Invalid bin size: {len(data)} bytes "
                             f"(expected {BinFile.BIN_SIZE} or {BinFile.CAL_SIZE})")
        return data

    @staticmethod
    def save(path: str, data: bytearray) -> None:
        """Save a .bin file."""
        Path(path).write_bytes(bytes(data))

    @staticmethod
    def save_cal(path: str, data: bytearray, padded: bool = True) -> None:
        """
        Save calibration data from a 128KB bin.

        Args:
            path:   Output file path (.cal)
            data:   Full 128KB bin image
            padded: If True, saves 128KB file with cal at $4000 and zeros elsewhere
                    (TunerPro-compatible). If False, saves raw 16KB cal data only.
        """
        if padded:
            # 128KB file: zeros everywhere except $4000-$7FFF
            cal_out = bytearray(BinFile.BIN_SIZE)
            cal_out[BinFile.CAL_OFFSET:BinFile.CAL_OFFSET + BinFile.CAL_SIZE] = \
                data[BinFile.CAL_OFFSET:BinFile.CAL_OFFSET + BinFile.CAL_SIZE]
            Path(path).write_bytes(bytes(cal_out))
            log.info("Saved padded 128KB cal to %s (cal at $%04X-$%04X)",
                     path, BinFile.CAL_OFFSET, BinFile.CAL_OFFSET + BinFile.CAL_SIZE - 1)
        else:
            # Raw 16KB cal data only
            cal_data = data[BinFile.CAL_OFFSET:BinFile.CAL_OFFSET + BinFile.CAL_SIZE]
            Path(path).write_bytes(bytes(cal_data))
            log.info("Saved raw 16KB cal to %s", path)

    @staticmethod
    def compute_checksum(data: bytearray) -> int:
        """
        Compute the VXY checksum for a bin file.
        Sum all bytes from $2000 to $1FFFF across all 3 banks,
        skipping the checksum storage region $4000-$4007.
        Returns 16-bit checksum.
        """
        total = 0
        for addr in range(0x2000, 0x20000):
            if CHECKSUM_SKIP_START <= addr <= CHECKSUM_SKIP_END:
                continue
            if addr < len(data):
                total = (total + data[addr]) & 0xFFFF
        return total

    @staticmethod
    def fix_checksum(data: bytearray) -> Tuple[int, int]:
        """
        Compute and write the correct checksum into the bin at $4006-$4007.
        Returns (old_checksum, new_checksum).
        """
        old_cs = (data[CHECKSUM_OFFSET_HI] << 8) | data[CHECKSUM_OFFSET_LO]
        new_cs = BinFile.compute_checksum(data)
        data[CHECKSUM_OFFSET_HI] = (new_cs >> 8) & 0xFF
        data[CHECKSUM_OFFSET_LO] = new_cs & 0xFF
        return old_cs, new_cs

    @staticmethod
    def verify_checksum(data: bytearray) -> bool:
        """Check if the stored checksum matches the computed one."""
        stored = (data[CHECKSUM_OFFSET_HI] << 8) | data[CHECKSUM_OFFSET_LO]
        computed = BinFile.compute_checksum(data)
        return stored == computed

    @staticmethod
    def get_os_id(data: bytearray) -> str:
        """Extract the OS ID bytes from the bin."""
        if len(data) > 0x2001:
            return f"${data[0x2000]:02X}{data[0x2001]:02X}"
        return "????"

    @staticmethod
    def diff_sectors(old_data: bytearray, new_data: bytearray) -> List[int]:
        """
        Return list of sector indices that differ between two bins.
        Sector layout matches AMD 29F010 128KB: 8 × 16KB sectors.
        Sector 0 = $0000-$3FFF, Sector 1 = $4000-$7FFF, ..., Sector 7 = $1C000-$1FFFF.
        """
        sector_size = 0x4000  # 16KB
        changed = []
        for sector in range(8):
            start = sector * sector_size
            end = start + sector_size
            if old_data[start:end] != new_data[start:end]:
                changed.append(sector)
        return changed

    @staticmethod
    def read_table(data: bytearray, table: CalibrationTable) -> List[List[int]]:
        """Read a calibration table from the bin as a 2D list."""
        result = []
        offset = table.rom_offset
        for r in range(table.rows):
            row = []
            for c in range(table.cols):
                if table.element_size == 1:
                    row.append(data[offset])
                elif table.element_size == 2:
                    row.append((data[offset] << 8) | data[offset + 1])
                offset += table.element_size
            result.append(row)
        return result

    @staticmethod
    def write_table(data: bytearray, table: CalibrationTable, values: List[List[int]]) -> None:
        """Write a 2D calibration table into the bin."""
        offset = table.rom_offset
        for r in range(table.rows):
            for c in range(table.cols):
                val = values[r][c]
                if table.element_size == 1:
                    data[offset] = val & 0xFF
                elif table.element_size == 2:
                    data[offset] = (val >> 8) & 0xFF
                    data[offset + 1] = val & 0xFF
                offset += table.element_size


# ═══════════════════════════════════════════════════════════════════════
# SECTION 9 — FLASH OPERATIONS (HIGH-LEVEL SEQUENCES)
# ═══════════════════════════════════════════════════════════════════════

class FlashOp:
    """
    High-level flash operations: read, write, verify.
    Orchestrates the full sequence: silence → unlock → mode5 → kernel → erase → write → verify → cleanup
    """

    def __init__(self, comm: ECUComm):
        self.comm = comm
        self._backup_bin: Optional[bytearray] = None
        self._stats: Dict[str, Any] = {}

    def _log_session_summary(self) -> None:
        """Log a formatted summary of the completed flash operation."""
        s = self._stats
        if not s:
            return

        lines = [
            "╔══════════════════════════════════════════════════════════╗",
            "║              FLASH SESSION SUMMARY                      ║",
            "╠══════════════════════════════════════════════════════════╣",
        ]

        op = s.get("operation", "?")
        mode = s.get("mode", "?")
        lines.append(f"║  Operation:       {op} ({mode})")
        lines.append(f"║  Transport:       {s.get('transport', '?')}")
        lines.append(f"║  Baud Rate:       {s.get('baud_rate', '?')}")

        if "address_range" in s:
            lines.append(f"║  Address Range:   {s['address_range']}")
        if "sectors_erased" in s:
            lines.append(f"║  Sectors Erased:  {s['sectors_erased']}")

        lines.append(f"║  Bytes:           {s.get('bytes_transferred', 0):,}")

        if "read_block_size" in s:
            lines.append(f"║  Read Block Size: {s['read_block_size']} bytes")
        if "write_chunk_size" in s:
            lines.append(f"║  Write Chunk:     {s['write_chunk_size']} bytes")

        lines.append(f"║  Total Frames:    {s.get('total_frames', '?')}")
        if "successful_frames" in s:
            lines.append(f"║  Successful:      {s['successful_frames']}")
        if "failed_frames" in s and s["failed_frames"] > 0:
            lines.append(f"║  Failed:          {s['failed_frames']}  ⚠")
        if "write_retries" in s and s["write_retries"] > 0:
            lines.append(f"║  Write Retries:   {s['write_retries']}")

        elapsed = s.get("elapsed_seconds", 0)
        kbps = s.get("throughput_kbps", 0)
        eff = s.get("baud_efficiency_pct", 0)
        lines.append(f"║  Elapsed:         {elapsed:.2f}s")
        lines.append(f"║  Throughput:      {kbps:.2f} kbps")
        lines.append(f"║  Baud Efficiency: {eff:.1f}%")

        if s.get("high_speed"):
            lines.append(f"║  High-Speed Read: YES")
        if s.get("checksum_verified"):
            lines.append(f"║  Checksum:        VERIFIED ✓")

        if "failed_frames" in s and s["failed_frames"] > 0:
            lines.append("║")
            lines.append(f"║  ⚠  {s['failed_frames']} read failures during operation")

        lines.append("╚══════════════════════════════════════════════════════════╝")

        for line in lines:
            self.comm.emit("log", msg=line, level="info")
            log.info(line)

    def full_read(self) -> Optional[bytearray]:
        """Read the full 128KB bin from the ECU."""
        self.comm.emit("log", msg="═══ FULL READ STARTED ═══", level="info")
        start_time = time.monotonic()

        # Step 1: Silence bus
        if not self.comm.disable_chatter():
            return None

        # Step 2: Unlock
        if not self.comm.unlock_security():
            self.comm.enable_chatter()
            return None

        # Step 3: Enter programming
        if not self.comm.enter_programming():
            self.comm.enable_chatter()
            return None

        # Step 4: Upload kernel
        if not self.comm.upload_kernel():
            self.comm.enable_chatter()
            return None

        # Step 5: Read flash info
        flash_info = self.comm.read_flash_info()

        # Step 6: Read all data
        # The uploaded kernel handles bank switching internally based on the 3-byte
        # address — we just read sequentially from $0000 to $1FFFF.
        bin_data = bytearray(BinFile.BIN_SIZE)
        read_start = 0x0000
        read_end = BinFile.BIN_SIZE  # 0x20000
        read_block = 64  # bytes per Mode 2 read
        total_reads = (read_end - read_start) // read_block
        reads_done = 0

        address = read_start
        block_retries = 0  # per-block retry counter (local — #4 fix)
        while address < read_end:
            if self.comm.cancelled:
                self.comm.cleanup_and_reset()
                self.comm.enable_chatter()
                return None

            data = self.comm.read_ram(address, extended=True)
            if data:
                for i, b in enumerate(data):
                    if address + i < BinFile.BIN_SIZE:
                        bin_data[address + i] = b
                address += len(data)
                reads_done += 1
                block_retries = 0  # reset on success
                self.comm.emit("progress", current=reads_done, total=total_reads, label="Reading")
            else:
                block_retries += 1
                if block_retries < READ_BLOCK_MAX_RETRIES:
                    # Flush bus and retry the same block
                    self.comm.transport.flush_input()
                    time.sleep(INTER_RETRY_DELAY_MS / 1000.0)
                    self.comm.emit("log",
                                  msg=f"Read failed at ${address:05X}, retry {block_retries}/{READ_BLOCK_MAX_RETRIES}",
                                  level="warning")
                else:
                    # Exhausted retries — skip this block
                    self.comm.emit("log",
                                  msg=f"Read failed at ${address:05X} after {READ_BLOCK_MAX_RETRIES} retries — skipping",
                                  level="error")
                    block_retries = 0
                    address += read_block  # Skip ahead

        # Step 7: Cleanup
        self.comm.cleanup_and_reset()
        self.comm.enable_chatter()

        elapsed = time.monotonic() - start_time
        failed_reads = total_reads - reads_done
        bytes_read = BinFile.BIN_SIZE
        kbps = (bytes_read * 8 / 1000) / elapsed if elapsed > 0 else 0
        baud_efficiency = (kbps * 1000) / self.comm.config.baud * 100 if self.comm.config.baud else 0

        # ── Flash Session Summary ──
        self._stats = {
            "operation": "READ",
            "mode": "FULL",
            "bytes_transferred": bytes_read,
            "read_block_size": read_block,
            "total_frames": total_reads,
            "successful_frames": reads_done,
            "failed_frames": failed_reads,
            "baud_rate": self.comm.config.baud,
            "elapsed_seconds": round(elapsed, 2),
            "throughput_kbps": round(kbps, 2),
            "baud_efficiency_pct": round(baud_efficiency, 1),
            "transport": type(self.comm.transport).__name__,
            "high_speed": self.comm.config.high_speed_read,
        }
        self._log_session_summary()

        self.comm.emit("log", msg=f"═══ READ COMPLETE ({elapsed:.1f}s) ═══", level="info")
        return bin_data

    def full_write(self, bin_data: bytearray, mode: str = "BIN",
                   progress_callback: Callable = None) -> bool:
        """
        Write a bin to the ECU.
        mode: "CAL" (cal only), "BIN" (OS+cal), "PROM" (full recovery)
        """
        if len(bin_data) != BinFile.BIN_SIZE:
            self.comm.emit("log", msg=f"Invalid bin size: {len(bin_data)}", level="error")
            return False

        mode = mode.upper()
        if mode not in WRITE_RANGES:
            self.comm.emit("log", msg=f"Invalid write mode: {mode}", level="error")
            return False

        start_offset, end_offset = WRITE_RANGES[mode]

        # Select erase map
        if mode == "CAL":
            erase_map = ERASE_MAP_CAL
        elif mode == "BIN":
            erase_map = ERASE_MAP_BIN
        else:
            erase_map = ERASE_MAP_PROM

        self.comm.emit("log", msg=f"═══ {mode} WRITE STARTED ═══", level="info")
        self.comm.emit("log", msg=f"  Range: ${start_offset:05X}-${end_offset:05X} "
                       f"({end_offset - start_offset + 1} bytes)", level="info")
        self.comm.emit("log", msg=f"  Sectors to erase: {len(erase_map)}", level="info")
        start_time = time.monotonic()

        # Verify checksum in the bin
        if not BinFile.verify_checksum(bin_data):
            if self.comm.config.auto_checksum_fix:
                old_cs, new_cs = BinFile.fix_checksum(bin_data)
                self.comm.emit("log",
                              msg=f"Auto-fixed checksum: 0x{old_cs:04X} → 0x{new_cs:04X}",
                              level="warning")
            else:
                self.comm.emit("log", msg="Checksum mismatch in bin file!", level="error")
                return False

        # Step 1: Silence
        if not self.comm.disable_chatter():
            return False

        # Step 2: Unlock
        if not self.comm.unlock_security():
            self.comm.enable_chatter()
            return False

        # Step 3: Enter programming
        if not self.comm.enter_programming():
            self.comm.enable_chatter()
            return False

        # Step 4: Upload kernel
        if not self.comm.upload_kernel():
            self.comm.enable_chatter()
            return False

        # Step 5: Read flash info
        flash_info = self.comm.read_flash_info()

        # Step 5b: Pre-write backup read (#6 fix)
        # Read sectors that will be erased so recovery is possible on failure.
        self.comm.emit("log", msg="Backing up flash before erase...", level="info")
        self._backup_bin = bytearray(BinFile.BIN_SIZE)
        backup_ok = True
        for sector_num, bank, erase_byte, s_start, s_end, label in SECTOR_INFO:
            if (bank, erase_byte) in erase_map:
                for addr in range(s_start, s_end + 1, 64):
                    chunk = self.comm.read_ram(addr, extended=True)
                    if chunk:
                        for i, b in enumerate(chunk):
                            if addr + i <= s_end:
                                self._backup_bin[addr + i] = b
                    else:
                        backup_ok = False
                        break
                if not backup_ok:
                    break
        if backup_ok:
            self.comm.emit("log", msg="Backup complete — recovery data stored in memory", level="info")
        else:
            self.comm.emit("log",
                          msg="Backup incomplete — proceeding without full recovery data",
                          level="warning")

        # Step 6: Erase
        if not self.comm.erase_sectors(erase_map):
            self.comm.emit("log", msg="ERASE FAILED — PCM may be in erased state!", level="error")
            self.comm.emit("log", msg="WARNING: ECU flash is erased. Retry write or ECU is bricked!", level="error")
            self.comm.enable_chatter()
            return False

        # Step 7: Write (with full-operation retry on failure — erased ECU is bricked)
        write_attempts = 0
        max_write_attempts = 3
        write_ok = False
        while not write_ok and write_attempts < max_write_attempts:
            write_ok = self.comm.write_flash_data(bin_data, start_offset, end_offset,
                                                  callback=progress_callback)
            if not write_ok:
                write_attempts += 1
                self.comm.emit("log",
                              msg=f"WRITE FAILED (attempt {write_attempts}/{max_write_attempts}) "
                                  f"— retrying to prevent bricked ECU",
                              level="error")
                if write_attempts >= max_write_attempts:
                    self.comm.emit("log",
                                  msg="WRITE FAILED after all retries. ECU may need bench recovery.",
                                  level="error")
                    self.comm.enable_chatter()
                    return False

        # Step 8: Verify
        if not self.comm.verify_checksum(bin_data):
            self.comm.emit("log", msg="VERIFY FAILED — checksum mismatch on PCM", level="error")
            self.comm.enable_chatter()
            return False

        # Step 9: Cleanup
        self.comm.cleanup_and_reset()
        self.comm.enable_chatter()

        elapsed = time.monotonic() - start_time
        bytes_written = end_offset - start_offset + 1
        kbps = (bytes_written * 8 / 1000) / elapsed if elapsed > 0 else 0
        baud_efficiency = (kbps * 1000) / self.comm.config.baud * 100 if self.comm.config.baud else 0
        total_write_frames = (bytes_written + self.comm.config.write_chunk_size - 1) // self.comm.config.write_chunk_size

        # ── Flash Session Summary ──
        self._stats = {
            "operation": "WRITE",
            "mode": mode,
            "bytes_transferred": bytes_written,
            "write_chunk_size": self.comm.config.write_chunk_size,
            "address_range": f"${start_offset:05X}-${end_offset:05X}",
            "sectors_erased": len(erase_map),
            "total_frames": total_write_frames,
            "write_retries": write_attempts,
            "baud_rate": self.comm.config.baud,
            "elapsed_seconds": round(elapsed, 2),
            "throughput_kbps": round(kbps, 2),
            "baud_efficiency_pct": round(baud_efficiency, 1),
            "transport": type(self.comm.transport).__name__,
            "checksum_verified": True,
        }
        self._log_session_summary()

        self.comm.emit("log", msg=f"═══ {mode} WRITE COMPLETE ({elapsed:.1f}s) ═══", level="info")
        return True

    def custom_write(self, bin_data: bytearray, sectors: List[int],
                     progress_callback: Callable = None) -> bool:
        """
        Write selected sectors only.  For unbricking or partial OS repair.

        *sectors* is a list of sector indices 0-7.  Each sector is 16KB.
        The method erases only the listed sectors and writes only their
        corresponding file-offset ranges.
        """
        if len(bin_data) != BinFile.BIN_SIZE:
            self.comm.emit("log", msg=f"Invalid bin size: {len(bin_data)}", level="error")
            return False

        # Build erase map and write ranges from selected sectors
        erase_map = []
        write_ranges = []
        for sec_num in sorted(set(sectors)):
            if sec_num < 0 or sec_num >= len(SECTOR_INFO):
                self.comm.emit("log", msg=f"Invalid sector number: {sec_num}", level="error")
                return False
            _sn, bank, erase_byte, fs, fe, label = SECTOR_INFO[sec_num]
            erase_map.append((bank, erase_byte))
            write_ranges.append((fs, fe))
            self.comm.emit("log", msg=f"  Sector {sec_num}: {label} (${fs:05X}-${fe:05X})", level="info")

        total_bytes = sum(fe - fs + 1 for fs, fe in write_ranges)
        self.comm.emit("log", msg=f"═══ CUSTOM WRITE — {len(sectors)} sectors, "
                       f"{total_bytes:,} bytes ═══", level="info")
        start_time = time.monotonic()

        # Verify / fix checksum
        if not BinFile.verify_checksum(bin_data):
            if self.comm.config.auto_checksum_fix:
                old_cs, new_cs = BinFile.fix_checksum(bin_data)
                self.comm.emit("log",
                              msg=f"Auto-fixed checksum: 0x{old_cs:04X} → 0x{new_cs:04X}",
                              level="warning")
            else:
                self.comm.emit("log", msg="Checksum mismatch in bin file!", level="error")
                return False

        # Step 1: Silence
        if not self.comm.disable_chatter():
            return False

        # Step 2: Unlock
        if not self.comm.unlock_security():
            self.comm.enable_chatter()
            return False

        # Step 3: Enter programming
        if not self.comm.enter_programming():
            self.comm.enable_chatter()
            return False

        # Step 4: Upload kernel
        if not self.comm.upload_kernel():
            self.comm.enable_chatter()
            return False

        # Step 5: Read flash info
        self.comm.read_flash_info()

        # Step 6: Erase selected sectors
        if not self.comm.erase_sectors(erase_map):
            self.comm.emit("log", msg="ERASE FAILED — selected sectors may be wiped!", level="error")
            self.comm.enable_chatter()
            return False

        # Step 7: Write selected ranges
        for fs, fe in write_ranges:
            if not self.comm.write_flash_data(bin_data, fs, fe, callback=progress_callback):
                self.comm.emit("log", msg=f"WRITE FAILED at ${fs:05X}-${fe:05X}", level="error")
                self.comm.enable_chatter()
                return False

        # Step 8: Verify
        if not self.comm.verify_checksum(bin_data):
            self.comm.emit("log", msg="VERIFY FAILED — checksum mismatch on PCM", level="error")
            self.comm.enable_chatter()
            return False

        # Step 9: Cleanup
        self.comm.cleanup_and_reset()
        self.comm.enable_chatter()

        elapsed = time.monotonic() - start_time
        self.comm.emit("log",
                      msg=f"═══ CUSTOM WRITE COMPLETE — {len(sectors)} sectors in {elapsed:.1f}s ═══",
                      level="info")
        return True

    def custom_read(self, start_addr: int, end_addr: int) -> Optional[bytearray]:
        """
        Read a custom address range from the ECU.

        Returns the bytes read, or None on failure.  The returned buffer
        has length (end_addr - start_addr + 1).
        """
        byte_count = end_addr - start_addr + 1
        self.comm.emit("log", msg=f"═══ CUSTOM READ ${start_addr:05X}-${end_addr:05X} "
                       f"({byte_count:,} bytes) ═══", level="info")
        start_time = time.monotonic()

        # Step 1: Silence
        if not self.comm.disable_chatter():
            return None

        # Step 2: Unlock
        if not self.comm.unlock_security():
            self.comm.enable_chatter()
            return None

        # Step 3: Enter programming
        if not self.comm.enter_programming():
            self.comm.enable_chatter()
            return None

        # Step 4: Upload kernel
        if not self.comm.upload_kernel():
            self.comm.enable_chatter()
            return None

        # Step 5: Read data
        result = bytearray(byte_count)
        read_block = 64
        total_reads = (byte_count + read_block - 1) // read_block
        reads_done = 0
        address = start_addr

        while address <= end_addr:
            if self.comm.cancelled:
                self.comm.enable_chatter()
                return None

            chunk = self.comm.read_ram(address, count=read_block, extended=True)
            if chunk:
                offset = address - start_addr
                copy_len = min(len(chunk), end_addr - address + 1)
                result[offset:offset + copy_len] = chunk[:copy_len]
                reads_done += 1
                address += read_block

                pct = (reads_done / total_reads) * 100 if total_reads > 0 else 100
                self.comm.emit("progress", current=reads_done, total=total_reads,
                              label=f"Reading ${address:05X}")
            else:
                retries = getattr(self, '_cread_retries', 0) + 1
                self._cread_retries = retries
                if retries < READ_BLOCK_MAX_RETRIES:
                    self.comm.transport.flush_input()
                    time.sleep(INTER_RETRY_DELAY_MS / 1000.0)
                    self.comm.emit("log",
                                  msg=f"Read failed at ${address:05X}, retry {retries}/{READ_BLOCK_MAX_RETRIES}",
                                  level="warning")
                else:
                    self.comm.emit("log",
                                  msg=f"Read failed at ${address:05X} after {READ_BLOCK_MAX_RETRIES} retries",
                                  level="error")
                    self._cread_retries = 0
                    address += read_block

        # Step 6: Cleanup
        self.comm.cleanup_and_reset()
        self.comm.enable_chatter()

        elapsed = time.monotonic() - start_time
        self.comm.emit("log", msg=f"═══ CUSTOM READ COMPLETE ({elapsed:.1f}s) ═══", level="info")
        return result


# ═══════════════════════════════════════════════════════════════════════
# SECTION 10 — DATALOGGER
# ═══════════════════════════════════════════════════════════════════════

class DataLogger:
    """
    Continuous Mode 1 data stream logger.
    Records sensor data to CSV with timestamps.
    """

    def __init__(self, comm: ECUComm):
        self.comm = comm
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._data_buffer: deque = deque(maxlen=10000)
        self._csv_file = None
        self._csv_path: Optional[str] = None
        self._sample_count = 0
        self._start_time = 0.0
        self.on_data: Optional[Callable] = None
        self._params_to_log: List[str] = [
            "RPM", "ECT Temp", "IAT Temp", "TPS %", "MAF",
            "Spark Advance", "Knock Retard", "AFR", "LH O2", "RH O2",
            "LH STFT", "RH STFT", "LH LTFT", "RH LTFT",
            "Battery V", "IAC Steps", "Inj PW", "Run Time",
        ]

    def start(self, csv_path: str = None, params: List[str] = None) -> None:
        """Start logging in a background thread."""
        if self.running:
            return

        if params:
            self._params_to_log = params

        self._csv_path = csv_path or str(
            LOG_DIR / f"datalog_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        self._csv_file = open(self._csv_path, "w", encoding="utf-8", buffering=1)  # line-buffered (#11 fix)
        self._csv_file.write("Timestamp,Elapsed_s," + ",".join(self._params_to_log) + "\n")

        self.running = True
        self._sample_count = 0
        self._start_time = time.monotonic()
        self._thread = threading.Thread(target=self._log_loop, daemon=True)
        self._thread.start()

        self.comm.emit("log", msg=f"Datalog started → {self._csv_path}", level="info")

    def stop(self) -> None:
        """Stop logging."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        if self._csv_file:
            self._csv_file.close()
            self._csv_file = None

        self.comm.emit("log",
                      msg=f"Datalog stopped: {self._sample_count} samples in "
                          f"{time.monotonic() - self._start_time:.1f}s",
                      level="info")

    def _log_loop(self) -> None:
        """Main logging loop — runs in background thread."""
        while self.running and not self.comm.cancelled:
            data = self.comm.request_mode1(message=0)
            if data:
                self._sample_count += 1
                elapsed = time.monotonic() - self._start_time
                ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]

                # Write CSV row
                values = [str(data.get(p, "")) for p in self._params_to_log]
                if self._csv_file:
                    self._csv_file.write(f"{ts},{elapsed:.3f}," + ",".join(values) + "\n")
                    if self._sample_count % 10 == 0:
                        self._csv_file.flush()

                # Buffer and callback
                self._data_buffer.append(data)
                if self.on_data:
                    self.on_data(data)
            else:
                time.sleep(0.05)

    @property
    def latest(self) -> Optional[Dict[str, float]]:
        """Get the most recent data sample."""
        return self._data_buffer[-1] if self._data_buffer else None

    @property
    def sample_rate(self) -> float:
        """Samples per second."""
        elapsed = time.monotonic() - self._start_time
        return self._sample_count / elapsed if elapsed > 0 else 0


# ═══════════════════════════════════════════════════════════════════════
# SECTION 11 — LIVE TUNER (RAM shadow approach)
# ═══════════════════════════════════════════════════════════════════════

class LiveTuner:
    """
    Real-time calibration tuning via ALDL.
    Sends table cell updates to ECU RAM shadow over Mode 10.
    Requires a patched OS bin with RT_WRITE handler installed.
    """

    RT_FLAG = 0x80  # Bit 7 set = RT write (not malf clear)

    def __init__(self, comm: ECUComm, table: CalibrationTable):
        self.comm = comm
        self.table = table
        self.shadow = bytearray(table.byte_size)
        self.rom_values = bytearray(table.byte_size)  # Original ROM values for delta checking
        self.dirty_cells: set = set()
        self.active = False
        self._max_delta = 10  # max ±10 from ROM value per cell

        # Safety
        self.knock_history: deque = deque(maxlen=10)
        self.safety_reverted = False

    def load_from_bin(self, bin_data: bytearray) -> None:
        """Load table values from the bin file into the shadow."""
        offset = self.table.rom_offset
        for i in range(self.table.byte_size):
            self.shadow[i] = bin_data[offset + i]
            self.rom_values[i] = bin_data[offset + i]

    def set_cell(self, row: int, col: int, value: int) -> bool:
        """Set a cell value (with delta safety check)."""
        offset = row * self.table.cols + col
        if offset < 0 or offset >= self.table.byte_size:
            return False
        if value < 0 or value > 255:
            return False

        # Delta check
        rom_val = self.rom_values[offset]
        delta = abs(value - rom_val)
        if delta > self._max_delta:
            log.warning("Cell [%d,%d] delta %d exceeds max %d", row, col, delta, self._max_delta)
            self.comm.emit("log",
                          msg=f"Safety limit: cell [{row},{col}] delta {delta} > max {self._max_delta}",
                          level="warning")
            return False

        self.shadow[offset] = value
        self.dirty_cells.add(offset)
        return True

    def get_cell(self, row: int, col: int) -> int:
        """Get current shadow cell value."""
        offset = row * self.table.cols + col
        return self.shadow[offset] if 0 <= offset < self.table.byte_size else 0

    def send_updates(self) -> bool:
        """Send all dirty cells to ECU."""
        if not self.dirty_cells:
            return True

        cells = sorted(self.dirty_cells)
        runs = self._find_runs(cells)

        for start_offset, data in runs:
            target_addr = start_offset  # The patched OS knows the shadow base
            frame = ALDLProtocol.build_write_frame(
                self.comm.config.device_id,
                target_addr,
                data,
                mode=ALDLMode.MODE10_WRITE_CAL,
                extended=False,
            )
            # Add RT flag to distinguish from malf clear
            # (In the actual patched OS, the handler checks the sub-command byte)

            if self.comm.config.ignore_echo:
                self.comm.config.echo_byte_count = ALDLProtocol.wire_length(frame)

            resp = self.comm._transact(frame, timeout_ms=500, retries=1)
            if not resp:
                log.warning("RT write failed for offset $%04X", start_offset)
                return False

        self.dirty_cells.clear()
        return True

    def check_safety(self, sensor_data: Dict[str, float]) -> bool:
        """
        Check safety conditions from live sensor data.
        Returns True if safe, False if we should revert.
        """
        knock = sensor_data.get("Knock Retard", 0)
        self.knock_history.append(knock)

        # Knock retard watchdog: if >5° for 3 consecutive readings, revert
        if len(self.knock_history) >= 3:
            recent = list(self.knock_history)[-3:]
            if all(k > 5.0 for k in recent):
                log.warning("SAFETY: Knock retard >5° for 3 consecutive readings — reverting!")
                self.comm.emit("log",
                              msg="⚠ SAFETY: Knock retard detected — reverting to ROM values!",
                              level="error")
                self.revert_to_rom()
                return False

        # Temperature guard
        coolant = sensor_data.get("ECT Temp", 0)
        if coolant > 110:
            log.warning("SAFETY: Coolant temp %.1f°C > 110°C — refusing writes", coolant)
            return False

        # RPM guard
        rpm = sensor_data.get("RPM", 0)
        if rpm > 5500:
            log.warning("SAFETY: RPM %.0f > 5500 — refusing writes", rpm)
            return False

        return True

    def revert_to_rom(self) -> None:
        """Revert the shadow table back to original ROM values."""
        self.shadow = bytearray(self.rom_values)
        # Mark all cells dirty to send the revert
        self.dirty_cells = set(range(self.table.byte_size))
        self.safety_reverted = True
        self.send_updates()

    def _find_runs(self, offsets: list) -> List[Tuple[int, bytes]]:
        """Find contiguous runs of dirty cells for batched transfer."""
        if not offsets:
            return []
        runs = []
        start = offsets[0]
        end = offsets[0]
        for i in range(1, len(offsets)):
            if offsets[i] == end + 1 and (offsets[i] - start) < 50:
                end = offsets[i]
            else:
                runs.append((start, bytes(self.shadow[start:end + 1])))
                start = offsets[i]
                end = offsets[i]
        runs.append((start, bytes(self.shadow[start:end + 1])))
        return runs


# ═══════════════════════════════════════════════════════════════════════
# SECTION 12 — GUI (PySide6 Frontend)
# ═══════════════════════════════════════════════════════════════════════

if GUI_AVAILABLE:

    class LogWidget(QTextEdit):
        """Color-coded log output widget matching OSE's RichTextBox."""

        COLORS = {
            "info":    QColor(200, 200, 200),
            "warning": QColor(255, 165, 0),
            "error":   QColor(255, 80, 80),
            "debug":   QColor(120, 120, 120),
            "success": QColor(100, 255, 100),
        }

        def __init__(self, parent=None):
            super().__init__(parent)
            self.setReadOnly(True)
            self.setFont(QFont("Consolas", 9))
            self.setStyleSheet("""
                QTextEdit {
                    background-color: #1e1e1e;
                    color: #d4d4d4;
                    border: 1px solid #3c3c3c;
                    padding: 4px;
                }
            """)

        def append_log(self, msg: str, level: str = "info") -> None:
            color = self.COLORS.get(level, self.COLORS["info"])
            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            self.setTextColor(color)
            self.append(f"{ts}  {msg}")
            self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

    class SensorGaugeWidget(QFrame):
        """A single sensor gauge showing name, value, units, and bar."""

        def __init__(self, param: DataStreamParam, parent=None):
            super().__init__(parent)
            self.param = param
            self.value = 0.0
            self.setFrameShape(QFrame.StyledPanel)
            self.setStyleSheet("QFrame { background: #2d2d2d; border: 1px solid #444; border-radius: 4px; }")
            self.setFixedHeight(50)

            layout = QHBoxLayout(self)
            layout.setContentsMargins(8, 2, 8, 2)

            self.name_label = QLabel(param.name)
            self.name_label.setFixedWidth(120)
            self.name_label.setStyleSheet("color: #888;")

            self.value_label = QLabel("---")
            self.value_label.setFixedWidth(80)
            self.value_label.setStyleSheet("color: #4fc3f7; font-size: 14px; font-weight: bold;")
            self.value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

            self.unit_label = QLabel(param.units)
            self.unit_label.setFixedWidth(50)
            self.unit_label.setStyleSheet("color: #666;")

            layout.addWidget(self.name_label)
            layout.addStretch()
            layout.addWidget(self.value_label)
            layout.addWidget(self.unit_label)

        def update_value(self, val: float) -> None:
            self.value = val
            if self.param.conversion == "flags" or self.param.conversion == "hex":
                self.value_label.setText(f"0x{int(val):02X}")
            elif abs(val) > 1000:
                self.value_label.setText(f"{val:.0f}")
            elif abs(val) > 10:
                self.value_label.setText(f"{val:.1f}")
            else:
                self.value_label.setText(f"{val:.2f}")

    class DashboardWidget(QWidget):
        """Live sensor dashboard with gauge widgets."""

        DISPLAY_PARAMS = [
            "RPM", "ECT Temp", "IAT Temp", "TPS %", "MAF",
            "Spark Advance", "Knock Retard", "AFR",
            "LH O2", "RH O2", "LH STFT", "LH LTFT",
            "Battery V", "IAC Steps", "Inj PW", "Wheel Speed",
        ]

        def __init__(self, parent=None):
            super().__init__(parent)
            layout = QGridLayout(self)
            layout.setSpacing(4)

            self.gauges: Dict[str, SensorGaugeWidget] = {}
            for i, name in enumerate(self.DISPLAY_PARAMS):
                if name in PARAM_BY_NAME:
                    gauge = SensorGaugeWidget(PARAM_BY_NAME[name])
                    row, col = divmod(i, 2)
                    layout.addWidget(gauge, row, col)
                    self.gauges[name] = gauge

        def update_data(self, data: Dict[str, float]) -> None:
            for name, gauge in self.gauges.items():
                if name in data:
                    gauge.update_value(data[name])

    class TableEditorWidget(QWidget):
        """2D calibration table editor with cell highlighting."""

        cell_changed = Signal(int, int, int) if GUI_AVAILABLE else None

        def __init__(self, parent=None):
            super().__init__(parent)
            layout = QVBoxLayout(self)

            # Table selector
            selector_layout = QHBoxLayout()
            selector_layout.addWidget(QLabel("Table:"))
            self.table_combo = QComboBox()
            for key, table in CAL_TABLES.items():
                self.table_combo.addItem(f"{table.name} ({table.rows}×{table.cols})", key)
            self.table_combo.currentIndexChanged.connect(self._on_table_changed)
            selector_layout.addWidget(self.table_combo)
            layout.addLayout(selector_layout)

            # The table grid
            self.grid = QTableWidget()
            self.grid.setStyleSheet("""
                QTableWidget {
                    background-color: #1e1e1e;
                    color: #d4d4d4;
                    gridline-color: #3c3c3c;
                    font: 9pt Consolas;
                }
                QTableWidget::item {
                    padding: 2px;
                }
                QTableWidget::item:selected {
                    background-color: #264f78;
                }
            """)
            self.grid.cellChanged.connect(self._on_cell_edited)
            layout.addWidget(self.grid)

            self._current_table_key: Optional[str] = None
            self._rom_values: Optional[List[List[int]]] = None
            self._loading = False

        def load_table(self, table_key: str, bin_data: bytearray) -> None:
            """Load a table from bin data into the grid."""
            if table_key not in CAL_TABLES:
                return
            table = CAL_TABLES[table_key]
            self._current_table_key = table_key
            self._loading = True

            values = BinFile.read_table(bin_data, table)
            self._rom_values = [row[:] for row in values]  # deep copy

            self.grid.setRowCount(table.rows)
            self.grid.setColumnCount(table.cols)

            # Set axis labels if available
            if table.y_axis_values:
                self.grid.setVerticalHeaderLabels([str(v) for v in table.y_axis_values[:table.rows]])
            if table.x_axis_values:
                self.grid.setHorizontalHeaderLabels([str(v) for v in table.x_axis_values[:table.cols]])

            for r in range(table.rows):
                for c in range(table.cols):
                    item = QTableWidgetItem(str(values[r][c]))
                    item.setTextAlignment(Qt.AlignCenter)
                    self.grid.setItem(r, c, item)

            self._loading = False

        def highlight_cell(self, row: int, col: int) -> None:
            """Highlight the currently active cell (from live RPM/load position)."""
            for r in range(self.grid.rowCount()):
                for c in range(self.grid.columnCount()):
                    item = self.grid.item(r, c)
                    if item:
                        if r == row and c == col:
                            item.setBackground(QColor(0, 100, 0))  # Green for active
                        elif self._rom_values and item.text() != str(self._rom_values[r][c]):
                            item.setBackground(QColor(100, 60, 0))  # Orange for modified
                        else:
                            item.setBackground(QColor(30, 30, 30))  # Default

        def _on_table_changed(self, index: int) -> None:
            key = self.table_combo.itemData(index)
            if key:
                self.emit_log = True  # trigger a load on next bin load

        def _on_cell_edited(self, row: int, col: int) -> None:
            if self._loading:
                return
            item = self.grid.item(row, col)
            if item:
                try:
                    value = int(item.text())
                    if self.cell_changed:
                        self.cell_changed.emit(row, col, value)
                except ValueError:
                    pass

    class DisassemblerWidget(QWidget):
        """HC11 hex→asm disassembler with split input/output and event bus.

        Layout:
          ┌──────────────────────────────────┐
          │  [Base Addr: ____]  [Disassemble] [Clear]  [VY Annotate ☑]  │
          ├──────────────────────────────────┤
          │  Input   (hex bytes, scrollable)  │
          ├──────────────────────────────────┤
          │  Output  (disassembly, scrollable) │
          └──────────────────────────────────┘
        """

        # Event bus signal: emits (list_of_formatted_lines, base_addr)
        disassembly_done = Signal(list, int)

        def __init__(self, parent=None):
            super().__init__(parent)
            self._dis = None  # lazy import
            self._build_ui()

        def _get_disassembler(self):
            """Lazy-import the disassembler so the GUI loads fast even if the
            tools package isn't on the path."""
            if self._dis is None:
                try:
                    from tools.hc11_disassembler import HC11Disassembler
                    self._dis = HC11Disassembler(annotate_vy=True)
                except ImportError:
                    import sys, os
                    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                    from tools.hc11_disassembler import HC11Disassembler
                    self._dis = HC11Disassembler(annotate_vy=True)
            return self._dis

        def _build_ui(self) -> None:
            layout = QVBoxLayout(self)
            layout.setContentsMargins(4, 4, 4, 4)

            # ── Toolbar row ──
            toolbar = QHBoxLayout()
            toolbar.addWidget(QLabel("Base Addr:"))
            self.addr_input = QLineEdit("8000")
            self.addr_input.setFixedWidth(80)
            self.addr_input.setToolTip(
                "Starting ROM address in hex (e.g. 8000, C011).\n"
                "Branch targets and annotations are computed from this."
            )
            toolbar.addWidget(self.addr_input)

            self.btn_disasm = QPushButton("Disassemble")
            self.btn_disasm.setToolTip(
                "Decode the hex bytes in the input box into\n"
                "68HC11 assembly instructions with VY V6 annotations."
            )
            self.btn_disasm.setStyleSheet("background: #264f78; font-weight: bold;")
            self.btn_disasm.clicked.connect(self._on_disassemble)
            toolbar.addWidget(self.btn_disasm)

            self.btn_clear = QPushButton("Clear")
            self.btn_clear.setToolTip("Clear both input and output")
            self.btn_clear.clicked.connect(self._on_clear)
            toolbar.addWidget(self.btn_clear)

            self.chk_annotate = QCheckBox("VY V6 Annotate")
            self.chk_annotate.setChecked(True)
            self.chk_annotate.setToolTip(
                "Annotate known VY V6 $060A addresses:\n"
                "  • HC11 registers (PORTA, TCTL1, …)\n"
                "  • RAM variables (RPM, DWELL_RAM, …)\n"
                "  • Calibration scalars (Rev Limit, …)\n"
                "  • ISR entry points (TIC3_24X, …)"
            )
            toolbar.addWidget(self.chk_annotate)

            self.chk_description = QCheckBox("Show Descriptions")
            self.chk_description.setChecked(False)
            self.chk_description.setToolTip("Show opcode descriptions when no VY annotation")
            toolbar.addWidget(self.chk_description)

            toolbar.addStretch()

            self.stats_label = QLabel("")
            self.stats_label.setStyleSheet("color: #888; font-size: 11px;")
            toolbar.addWidget(self.stats_label)
            layout.addLayout(toolbar)

            # ── Horizontal splitter: Input (top) / Output (bottom) ──
            splitter = QSplitter(Qt.Vertical)

            # Input pane
            input_group = QGroupBox("Input — Hex Bytes")
            input_layout = QVBoxLayout(input_group)
            self.hex_input = QTextEdit()
            self.hex_input.setFont(QFont("Consolas", 10))
            self.hex_input.setPlaceholderText(
                "Paste hex bytes here — any format:\n"
                "  B6 77 DE 91 A4 26 05 39\n"
                "  B677DE91A4260539\n"
                "  0xB6, 0x77, 0xDE\n\n"
                "Then click Disassemble (or Ctrl+Enter)"
            )
            self.hex_input.setStyleSheet(
                "QTextEdit { background-color: #1a1a2e; color: #56d8b1; "
                "border: 1px solid #3c3c3c; padding: 4px; }"
            )
            self.hex_input.setAcceptRichText(False)
            input_layout.addWidget(self.hex_input)
            splitter.addWidget(input_group)

            # Output pane
            output_group = QGroupBox("Output — 68HC11 Disassembly")
            output_layout = QVBoxLayout(output_group)
            self.asm_output = QTextEdit()
            self.asm_output.setFont(QFont("Consolas", 10))
            self.asm_output.setReadOnly(True)
            self.asm_output.setStyleSheet(
                "QTextEdit { background-color: #1e1e1e; color: #d4d4d4; "
                "border: 1px solid #3c3c3c; padding: 4px; }"
            )
            output_layout.addWidget(self.asm_output)
            splitter.addWidget(output_group)

            # Default split: 30% input, 70% output
            splitter.setSizes([200, 500])
            layout.addWidget(splitter)

        def _on_disassemble(self) -> None:
            """Run disassembly on the input hex, write results to output."""
            hex_text = self.hex_input.toPlainText().strip()
            if not hex_text:
                return

            # Parse base address
            try:
                base_addr = int(self.addr_input.text().strip(), 16)
            except ValueError:
                base_addr = 0x8000

            dis = self._get_disassembler()
            dis.annotate_vy = self.chk_annotate.isChecked()
            show_desc = self.chk_description.isChecked()

            try:
                results = dis.disassemble_hex(hex_text, base_addr=base_addr)
            except Exception as exc:
                self.asm_output.setTextColor(QColor(255, 80, 80))
                self.asm_output.setText(f"Error: {exc}")
                return

            if not results:
                self.asm_output.setTextColor(QColor(255, 165, 0))
                self.asm_output.setText("No instructions decoded. Check hex input.")
                return

            # Build colorized output
            self.asm_output.clear()
            lines: list = []
            total_cycles = 0
            for r in results:
                line = r.format(show_description=show_desc)
                lines.append(line)
                total_cycles += r.cycles

                # Color code by instruction type
                if r.mnemonic == "DB":
                    color = QColor(255, 80, 80)    # data — red
                elif r.mnemonic in ("JSR", "BSR", "JMP", "RTS", "RTI", "SWI", "WAI"):
                    color = QColor(86, 216, 177)    # flow — teal
                elif r.mnemonic.startswith("B") and r.mode == "rel":
                    color = QColor(255, 214, 102)   # branch — gold
                elif r.comment:
                    color = QColor(130, 180, 255)   # annotated — blue
                else:
                    color = QColor(200, 200, 200)   # normal — grey

                self.asm_output.setTextColor(color)
                self.asm_output.append(line)

            # Stats
            n_bytes = sum(r.length for r in results)
            self.stats_label.setText(
                f"{len(results)} instructions | {n_bytes} bytes | "
                f"~{total_cycles} cycles"
            )

            # Emit event bus signal
            self.disassembly_done.emit(lines, base_addr)

        def _on_clear(self) -> None:
            self.hex_input.clear()
            self.asm_output.clear()
            self.stats_label.setText("")

        def keyPressEvent(self, event) -> None:
            """Ctrl+Enter triggers disassembly."""
            if (event.modifiers() & Qt.ControlModifier) and event.key() in (Qt.Key_Return, Qt.Key_Enter):
                self._on_disassemble()
            else:
                super().keyPressEvent(event)

    # ── Custom Flash Widget ──────────────────────────────────────────

    class CustomFlashWidget(QWidget):
        """
        Custom sector-level flash read/write for unbricking and partial recovery.

        Allows selecting individual 16KB sectors (0-7) by checkbox, or entering
        a custom hex address range.  Each operation has its own start button
        with a unique popup warning explaining the risk.

        Sector selection: comma or space separated (e.g. "3,4,5,7" or "3 4 5 7").
        """
        # Signals emitted to MainWindow for backend dispatch
        start_custom_write = Signal(list)    # list of sector ints
        start_custom_read = Signal(int, int) # start_addr, end_addr

        def __init__(self, parent=None):
            super().__init__(parent)
            self._build_ui()

        def _build_ui(self) -> None:
            outer = QVBoxLayout(self)
            outer.setContentsMargins(0, 0, 0, 0)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)

            content = QWidget()
            layout = QVBoxLayout(content)
            layout.setSpacing(12)
            layout.setContentsMargins(16, 16, 16, 16)

            # ── Info banner ──
            info = QLabel(
                "<b>Custom Flash — Sector-Level Recovery Tool</b><br>"
                "Select individual 16KB sectors to erase+write.  For unbricking a partially "
                "failed write, or replacing specific OS pages without touching the rest.<br><br>"
                "<b>⚠ Sector 7 is the boot sector.</b>  Erasing it without a bench programmer "
                "(T48/TL866) means permanent brick.  Only select sector 7 if you know what you're doing.<br><br>"
                "<b>Requires a loaded .bin file</b> — the tool writes data from the loaded bin into "
                "the selected sectors.  Make sure the bin matches the OS you want on the ECU."
            )
            info.setWordWrap(True)
            info.setStyleSheet("QLabel { background: #2a2a3a; padding: 12px; border-radius: 6px; }")
            layout.addWidget(info)

            # ── Sector checkboxes ──
            sector_group = QGroupBox("Select Sectors to Flash (16KB each)")
            sector_layout = QGridLayout(sector_group)

            self.sector_checks: List[QCheckBox] = []
            for i, (_sn, _bank, _erase, fs, fe, label) in enumerate(SECTOR_INFO):
                cb = QCheckBox(f"Sector {i}: {label}  (${fs:05X}-${fe:05X})")
                cb.setToolTip(
                    f"Sector {i} — {label}\n"
                    f"File offset: ${fs:05X} to ${fe:05X} (16,384 bytes)\n"
                    f"Bank: 0x{_bank:02X}\n\n"
                    + ("⚠ BOOT SECTOR — erasing this without a bench programmer = permanent brick!"
                       if i == 7 else
                       "Safe to erase and re-write from a matching bin file.")
                )
                if i == 7:
                    cb.setStyleSheet("QCheckBox { color: #ff5555; }")
                sector_layout.addWidget(cb, i // 2, i % 2)
                self.sector_checks.append(cb)

            layout.addWidget(sector_group)

            # ── Quick sector input ──
            quick_group = QGroupBox("Quick Sector Input")
            quick_layout = QHBoxLayout(quick_group)
            quick_layout.addWidget(QLabel("Sectors:"))
            self.sector_input = QLineEdit()
            self.sector_input.setPlaceholderText("e.g.  1,2,3  or  3 4 5 7")
            self.sector_input.setToolTip(
                "Type sector numbers separated by commas or spaces.\n"
                "Examples:  1,2,3   or   3 4 5 7   or   0-6\n"
                "This overrides the checkboxes above when non-empty."
            )
            quick_layout.addWidget(self.sector_input)
            self.btn_apply_input = QPushButton("Apply")
            self.btn_apply_input.setToolTip("Parse the text input and check the matching sector boxes")
            self.btn_apply_input.clicked.connect(self._apply_sector_input)
            quick_layout.addWidget(self.btn_apply_input)
            layout.addWidget(quick_group)

            # ── Start Custom Write ──
            write_group = QGroupBox("Custom Sector Write")
            write_layout = QVBoxLayout(write_group)
            write_layout.addWidget(QLabel(
                "Erases and writes ONLY the selected sectors from the loaded bin.\n"
                "Use this to repair a partial brick — e.g. if sectors 3-5 failed during a full write,\n"
                "select sectors 3,4,5 to re-flash just those without touching the rest."
            ))
            self.btn_custom_write = QPushButton("⚡  Start Custom Sector Write")
            self.btn_custom_write.setFixedHeight(40)
            self.btn_custom_write.setStyleSheet(
                "QPushButton { background: #8B4513; font-weight: bold; font-size: 14px; }"
                "QPushButton:hover { background: #A0522D; }"
            )
            self.btn_custom_write.setToolTip(
                "Erase + write only the checked sectors.\n"
                "The ECU must be powered and communicating.\n"
                "A loaded .bin file is required."
            )
            self.btn_custom_write.clicked.connect(self._on_custom_write)
            write_layout.addWidget(self.btn_custom_write)
            layout.addWidget(write_group)

            # ── Custom Address Range Read ──
            range_group = QGroupBox("Custom Address Range Read")
            range_layout = QFormLayout(range_group)

            self.start_addr_input = QLineEdit("0000")
            self.start_addr_input.setToolTip("Start address in hex (file offset, e.g. 4000)")
            range_layout.addRow("Start Address (hex):", self.start_addr_input)

            self.end_addr_input = QLineEdit("1FFFF")
            self.end_addr_input.setToolTip("End address in hex (file offset, e.g. 7FFF)")
            range_layout.addRow("End Address (hex):", self.end_addr_input)

            self.btn_custom_read = QPushButton("📖  Start Custom Address Read")
            self.btn_custom_read.setFixedHeight(40)
            self.btn_custom_read.setStyleSheet(
                "QPushButton { background: #2E5090; font-weight: bold; font-size: 14px; }"
                "QPushButton:hover { background: #3A65B0; }"
            )
            self.btn_custom_read.setToolTip(
                "Read a specific address range from ECU flash.\n"
                "Does NOT modify anything — safe to run at any time.\n"
                "The result is saved to a .bin file."
            )
            self.btn_custom_read.clicked.connect(self._on_custom_read)
            range_layout.addRow(self.btn_custom_read)
            layout.addWidget(range_group)

            # ── Custom Address Range Write ──
            range_write_group = QGroupBox("Custom Address Range Write")
            range_write_layout = QFormLayout(range_write_group)
            range_write_layout.addRow(QLabel(
                "Write a specific address range from the loaded bin.\n"
                "⚠ This erases ALL sectors that overlap the address range."
            ))

            self.write_start_addr_input = QLineEdit("4000")
            self.write_start_addr_input.setToolTip("Start address in hex (file offset)")
            range_write_layout.addRow("Start Address (hex):", self.write_start_addr_input)

            self.write_end_addr_input = QLineEdit("7FFF")
            self.write_end_addr_input.setToolTip("End address in hex (file offset)")
            range_write_layout.addRow("End Address (hex):", self.write_end_addr_input)

            self.btn_range_write = QPushButton("⚡  Start Address Range Write")
            self.btn_range_write.setFixedHeight(40)
            self.btn_range_write.setStyleSheet(
                "QPushButton { background: #8B0000; font-weight: bold; font-size: 14px; }"
                "QPushButton:hover { background: #B22222; }"
            )
            self.btn_range_write.setToolTip(
                "Erase overlapping sectors + write the specified address range.\n"
                "⚠ DANGEROUS — erases entire 16KB sectors even if you only write part of them.\n"
                "Make sure you have a backup."
            )
            self.btn_range_write.clicked.connect(self._on_range_write)
            range_write_layout.addRow(self.btn_range_write)
            layout.addWidget(range_write_group)

            layout.addStretch()
            scroll.setWidget(content)
            outer.addWidget(scroll)

        def _parse_sector_text(self, text: str) -> List[int]:
            """Parse sector input like '1,2,3' or '3 4 5 7' or '0-6' into a list."""
            sectors = []
            # Replace commas with spaces, then split
            text = text.replace(",", " ")
            for token in text.split():
                token = token.strip()
                if not token:
                    continue
                if "-" in token:
                    # Range: "3-5" → [3, 4, 5]
                    parts = token.split("-", 1)
                    try:
                        a, b = int(parts[0]), int(parts[1])
                        sectors.extend(range(a, b + 1))
                    except ValueError:
                        pass
                else:
                    try:
                        sectors.append(int(token))
                    except ValueError:
                        pass
            return [s for s in sectors if 0 <= s <= 7]

        def _apply_sector_input(self) -> None:
            """Parse text input and update checkboxes."""
            text = self.sector_input.text().strip()
            if not text:
                return
            selected = self._parse_sector_text(text)
            for i, cb in enumerate(self.sector_checks):
                cb.setChecked(i in selected)

        def _get_selected_sectors(self) -> List[int]:
            """Get sector indices from checkboxes, with text input override."""
            text = self.sector_input.text().strip()
            if text:
                return sorted(set(self._parse_sector_text(text)))
            return [i for i, cb in enumerate(self.sector_checks) if cb.isChecked()]

        def _on_custom_write(self) -> None:
            """Validate and emit start_custom_write with selected sectors."""
            sectors = self._get_selected_sectors()
            if not sectors:
                QMessageBox.warning(self, "No Sectors Selected",
                                    "Select at least one sector to write.\n\n"
                                    "Use the checkboxes or type sector numbers in the text input\n"
                                    "(e.g. 1,2,3 or 3 4 5 7).")
                return

            # Build warning message
            sector_desc = ", ".join(str(s) for s in sectors)
            total_kb = len(sectors) * 16
            has_boot = 7 in sectors

            msg = (f"You are about to ERASE and WRITE {len(sectors)} sector(s): [{sector_desc}]\n"
                   f"Total: {total_kb} KB\n\n")

            if has_boot:
                msg += ("⚠ SECTOR 7 (BOOT) IS SELECTED!\n"
                        "Erasing the boot sector without a bench programmer (T48/TL866)\n"
                        "means PERMANENT BRICK if the write fails.\n\n")

            msg += ("This will:\n"
                    "  1. Silence the bus (Mode 8)\n"
                    "  2. Unlock security (Mode 13)\n"
                    "  3. Enter programming (Mode 5)\n"
                    "  4. Upload flash kernel (Mode 6)\n"
                    "  5. ERASE the selected sectors — data gone forever\n"
                    "  6. Write data from the loaded bin into those sectors\n"
                    "  7. Verify checksum\n\n"
                    "Do NOT disconnect power during this operation.\n\n"
                    "Continue?")

            icon = QMessageBox.Critical if has_boot else QMessageBox.Warning
            reply = QMessageBox.question(self, "Custom Sector Write", msg,
                                         QMessageBox.Yes | QMessageBox.No,
                                         QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.start_custom_write.emit(sectors)

        def _on_custom_read(self) -> None:
            """Validate addresses and emit start_custom_read."""
            try:
                start = int(self.start_addr_input.text().strip(), 16)
                end = int(self.end_addr_input.text().strip(), 16)
            except ValueError:
                QMessageBox.warning(self, "Invalid Address",
                                    "Enter valid hex addresses (e.g. 4000 and 7FFF).")
                return

            if end <= start:
                QMessageBox.warning(self, "Invalid Range",
                                    "End address must be greater than start address.")
                return

            if end > 0x1FFFF:
                QMessageBox.warning(self, "Address Out of Range",
                                    "End address cannot exceed $1FFFF (128KB flash limit).")
                return

            byte_count = end - start + 1
            reply = QMessageBox.question(
                self, "Custom Address Read",
                f"Read ${start:05X} to ${end:05X} ({byte_count:,} bytes)\n\n"
                f"This is a READ — it does NOT modify flash.\n"
                f"Safe to run at any time.\n\n"
                f"The ECU must be powered and responding.\n"
                f"Continue?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.Yes:
                self.start_custom_read.emit(start, end)

        def _on_range_write(self) -> None:
            """Validate addresses and compute overlapping sectors for write."""
            try:
                start = int(self.write_start_addr_input.text().strip(), 16)
                end = int(self.write_end_addr_input.text().strip(), 16)
            except ValueError:
                QMessageBox.warning(self, "Invalid Address",
                                    "Enter valid hex addresses (e.g. 4000 and 7FFF).")
                return

            if end <= start:
                QMessageBox.warning(self, "Invalid Range",
                                    "End address must be greater than start address.")
                return

            if end > 0x1FFFF:
                QMessageBox.warning(self, "Address Out of Range",
                                    "End address cannot exceed $1FFFF.")
                return

            # Find overlapping sectors
            overlapping = []
            for sn, _bank, _erase, fs, fe, label in SECTOR_INFO:
                if start <= fe and end >= fs:
                    overlapping.append(sn)

            if not overlapping:
                QMessageBox.warning(self, "No Sectors",
                                    "Address range doesn't overlap any flash sectors.")
                return

            byte_count = end - start + 1
            sector_desc = ", ".join(str(s) for s in overlapping)
            has_boot = 7 in overlapping

            msg = (f"Write ${start:05X} to ${end:05X} ({byte_count:,} bytes)\n\n"
                   f"This will ERASE sectors: [{sector_desc}]\n"
                   f"({len(overlapping)} × 16KB = {len(overlapping) * 16} KB erased)\n\n")

            if has_boot:
                msg += "⚠ INCLUDES BOOT SECTOR 7 — brick risk!\n\n"

            msg += ("Entire 16KB sectors are erased even if the address range\n"
                    "only covers part of them.  Make sure the loaded bin has\n"
                    "valid data for ALL erased sectors.\n\n"
                    "Continue?")

            reply = QMessageBox.question(self, "Address Range Write", msg,
                                         QMessageBox.Yes | QMessageBox.No,
                                         QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.start_custom_write.emit(overlapping)

    # ── Chaos Test Widget ──────────────────────────────────────────

    class ChaosTestWidget(QWidget):
        """
        Automated stress-testing tab: read→write→read→verify loop until failure.

        Configurable parameters:
        - Number of cycles (0 = infinite)
        - Write mode (BIN / CAL)
        - Delay between cycles
        - Stop on first failure vs continue

        Logs every cycle result to the event bus.
        """
        start_chaos = Signal(dict)   # config dict
        stop_chaos = Signal()

        def __init__(self, parent=None):
            super().__init__(parent)
            self._build_ui()

        def _build_ui(self) -> None:
            outer = QVBoxLayout(self)
            outer.setContentsMargins(0, 0, 0, 0)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)

            content = QWidget()
            layout = QVBoxLayout(content)
            layout.setSpacing(12)
            layout.setContentsMargins(16, 16, 16, 16)

            # ── Info banner ──
            info = QLabel(
                "<b>Chaos Test — Automated Flash Stress Test</b><br>"
                "Runs a continuous read → write → read → compare loop to test transport "
                "reliability, flash chip endurance, and protocol stability.<br><br>"
                "<b>Each cycle:</b>  Read full bin → Write loaded bin → Read back → Compare bytes → Log result<br>"
                "<b>Stops on:</b>  Mismatch, comm failure, or user cancel<br><br>"
                "⚠ <b>THIS WILL WRITE TO YOUR ECU REPEATEDLY.</b>  Every cycle erases and re-writes flash sectors. "
                "Only use this for testing — not on a daily driver with a flash chip you care about."
            )
            info.setWordWrap(True)
            info.setStyleSheet("QLabel { background: #3a2a2a; padding: 12px; border-radius: 6px; }")
            layout.addWidget(info)

            # ── Config ──
            config_group = QGroupBox("Test Configuration")
            config_layout = QFormLayout(config_group)

            self.spin_cycles = QSpinBox()
            self.spin_cycles.setRange(0, 10000)
            self.spin_cycles.setValue(0)
            self.spin_cycles.setToolTip("Number of read→write→verify cycles. 0 = run until failure or cancel.")
            self.spin_cycles.setSpecialValueText("∞ (until failure)")
            config_layout.addRow("Cycles (0 = infinite):", self.spin_cycles)

            self.combo_write_mode = QComboBox()
            self.combo_write_mode.addItem("BIN — Full OS + Cal (104KB, sectors 0-6)", "BIN")
            self.combo_write_mode.addItem("CAL — Calibration only (16KB, sector 1)", "CAL")
            self.combo_write_mode.setToolTip(
                "CAL is faster per cycle (~30s) but only tests sector 1.\n"
                "BIN tests all 7 sectors (~3.5 min per cycle)."
            )
            config_layout.addRow("Write Mode:", self.combo_write_mode)

            self.spin_delay = QSpinBox()
            self.spin_delay.setRange(0, 60)
            self.spin_delay.setValue(5)
            self.spin_delay.setSuffix(" sec")
            self.spin_delay.setToolTip("Cooldown delay between cycles (lets flash chip and bus settle)")
            config_layout.addRow("Inter-cycle delay:", self.spin_delay)

            self.chk_stop_on_fail = QCheckBox("Stop on first failure")
            self.chk_stop_on_fail.setChecked(True)
            self.chk_stop_on_fail.setToolTip(
                "If unchecked, logs the failure and continues to the next cycle.\n"
                "If checked, stops immediately on any read/write/verify failure."
            )
            config_layout.addRow(self.chk_stop_on_fail)

            self.chk_compare_bytes = QCheckBox("Byte-level compare after each cycle")
            self.chk_compare_bytes.setChecked(True)
            self.chk_compare_bytes.setToolTip(
                "After write→read, compare every byte of the readback against\n"
                "the source bin.  Logs first mismatch address and byte values."
            )
            config_layout.addRow(self.chk_compare_bytes)

            layout.addWidget(config_group)

            # ── Results ──
            results_group = QGroupBox("Results")
            results_layout = QVBoxLayout(results_group)

            self.results_label = QLabel("No tests run yet")
            self.results_label.setStyleSheet("QLabel { font-size: 14px; padding: 8px; }")
            results_layout.addWidget(self.results_label)

            layout.addWidget(results_group)

            # ── Start / Stop ──
            btn_row = QHBoxLayout()

            self.btn_start = QPushButton("🔥  Start Chaos Test")
            self.btn_start.setFixedHeight(44)
            self.btn_start.setStyleSheet(
                "QPushButton { background: #B22222; font-weight: bold; font-size: 15px; }"
                "QPushButton:hover { background: #DC143C; }"
            )
            self.btn_start.setToolTip(
                "Start the automated stress test loop.\n"
                "Requires a loaded .bin file and active ECU connection."
            )
            self.btn_start.clicked.connect(self._on_start)
            btn_row.addWidget(self.btn_start)

            self.btn_stop = QPushButton("⏹  Stop")
            self.btn_stop.setFixedHeight(44)
            self.btn_stop.setEnabled(False)
            self.btn_stop.setStyleSheet(
                "QPushButton { font-weight: bold; font-size: 15px; }"
            )
            self.btn_stop.clicked.connect(self._on_stop)
            btn_row.addWidget(self.btn_stop)

            layout.addLayout(btn_row)
            layout.addStretch()
            scroll.setWidget(content)
            outer.addWidget(scroll)

        def _on_start(self) -> None:
            cycles = self.spin_cycles.value()
            mode = self.combo_write_mode.currentData()

            desc = f"{cycles} cycles" if cycles > 0 else "infinite cycles"
            reply = QMessageBox.question(
                self, "Start Chaos Test",
                f"⚠ CHAOS TEST — REPEATED FLASH WRITES\n\n"
                f"Mode: {mode}\n"
                f"Cycles: {desc}\n"
                f"Inter-cycle delay: {self.spin_delay.value()}s\n\n"
                f"This will repeatedly erase and write flash sectors.\n"
                f"Every cycle = 1 full erase + write + readback.\n\n"
                f"Flash chips have finite erase/write endurance (~10,000-100,000 cycles).\n"
                f"Use on test ECUs only.\n\n"
                f"Do NOT disconnect power during the test.\n\n"
                f"Continue?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

            if reply == QMessageBox.Yes:
                self.btn_start.setEnabled(False)
                self.btn_stop.setEnabled(True)
                config = {
                    "cycles": cycles,
                    "mode": mode,
                    "delay": self.spin_delay.value(),
                    "stop_on_fail": self.chk_stop_on_fail.isChecked(),
                    "compare_bytes": self.chk_compare_bytes.isChecked(),
                }
                self.start_chaos.emit(config)

        def _on_stop(self) -> None:
            self.btn_start.setEnabled(True)
            self.btn_stop.setEnabled(False)
            self.stop_chaos.emit()

        def update_results(self, cycle: int, passed: int, failed: int, msg: str = "") -> None:
            """Update the results label from the main window."""
            text = f"Cycle: {cycle}  |  Passed: {passed}  |  Failed: {failed}"
            if msg:
                text += f"\nLast: {msg}"
            self.results_label.setText(text)

    # ── Transport Settings Widget ────────────────────────────────

    class TransportSettingsWidget(QWidget):
        """
        Dedicated transport configuration tab.

        Top half: PySerial settings (port, baud, timeouts, flow ctrl)
        Bottom half (scrollable): FTDI D2XX low-level settings
        (latency timer, USB buffer, read/write timeouts, VID/PID)
        plus timing offset sliders for real-hardware tuning.

        Status: UNTESTED — implemented from OSE analysis + FTDI specs.
                 Could have problems on some adapters. Treat timing values
                 as starting points, not guarantees.
        """
        config_changed = Signal()

        def __init__(self, config: CommConfig, parent=None):
            super().__init__(parent)
            self._config = config
            self._build_ui()
            self._load_from_config(config)

        def _build_ui(self) -> None:
            outer = QVBoxLayout(self)
            outer.setContentsMargins(0, 0, 0, 0)

            splitter = QSplitter(Qt.Vertical)

            # ══════════ TOP: PySerial ══════════
            pyserial_widget = QWidget()
            py_layout = QVBoxLayout(pyserial_widget)
            py_layout.setContentsMargins(16, 12, 16, 8)

            py_header = QLabel("<b>PySerial (VCP) Settings</b>")
            py_header.setStyleSheet("QLabel { font-size: 14px; }")
            py_layout.addWidget(py_header)

            py_group = QGroupBox("Serial Port Configuration")
            py_form = QFormLayout(py_group)

            self.spin_py_read_timeout = QSpinBox()
            self.spin_py_read_timeout.setRange(50, 10000)
            self.spin_py_read_timeout.setSuffix(" ms")
            self.spin_py_read_timeout.setValue(100)
            self.spin_py_read_timeout.setSingleStep(50)
            self.spin_py_read_timeout.setToolTip(
                "PySerial read timeout per serial.Serial(timeout=).\n"
                "OSE default: 300ms × 5 = 1500ms.\n"
                "Lower = faster response detection, but may miss slow ECUs.\n"
                "100ms is good for most adapters. Try 200-500ms if reads fail."
            )
            py_form.addRow("Read Timeout:", self.spin_py_read_timeout)

            self.spin_py_write_timeout = QSpinBox()
            self.spin_py_write_timeout.setRange(100, 10000)
            self.spin_py_write_timeout.setSuffix(" ms")
            self.spin_py_write_timeout.setValue(1000)
            self.spin_py_write_timeout.setSingleStep(100)
            self.spin_py_write_timeout.setToolTip(
                "PySerial write timeout.\n"
                "OSE default: 1500ms. 1000ms is safe for most adapters."
            )
            py_form.addRow("Write Timeout:", self.spin_py_write_timeout)

            self.spin_py_read_buffer = QSpinBox()
            self.spin_py_read_buffer.setRange(256, 65536)
            self.spin_py_read_buffer.setSuffix(" bytes")
            self.spin_py_read_buffer.setValue(1000)
            self.spin_py_read_buffer.setSingleStep(256)
            self.spin_py_read_buffer.setToolTip(
                "PySerial input buffer hint (OS may override).\n"
                "OSE uses 1000 bytes. Increase if you see buffer overruns."
            )
            py_form.addRow("Read Buffer Size:", self.spin_py_read_buffer)

            self.chk_py_rtscts = QCheckBox("RTS/CTS hardware flow control")
            self.chk_py_rtscts.setChecked(False)
            self.chk_py_rtscts.setToolTip(
                "Enable RTS/CTS handshaking.\n"
                "ALDL does NOT use flow control — leave OFF.\n"
                "Only enable if you have a custom adapter that requires it."
            )
            py_form.addRow(self.chk_py_rtscts)

            self.chk_py_dsrdtr = QCheckBox("DSR/DTR flow control")
            self.chk_py_dsrdtr.setChecked(False)
            self.chk_py_dsrdtr.setToolTip(
                "Enable DSR/DTR handshaking.\n"
                "ALDL does NOT use this — leave OFF."
            )
            py_form.addRow(self.chk_py_dsrdtr)

            self.chk_py_xonxoff = QCheckBox("XON/XOFF software flow control")
            self.chk_py_xonxoff.setChecked(False)
            self.chk_py_xonxoff.setToolTip("Software flow control — never used on ALDL.")
            py_form.addRow(self.chk_py_xonxoff)

            py_layout.addWidget(py_group)
            splitter.addWidget(pyserial_widget)

            # ══════════ BOTTOM: FTDI D2XX (scrollable) ══════════
            d2xx_scroll = QScrollArea()
            d2xx_scroll.setWidgetResizable(True)
            d2xx_scroll.setFrameShape(QFrame.NoFrame)

            d2xx_widget = QWidget()
            d2xx_layout = QVBoxLayout(d2xx_widget)
            d2xx_layout.setContentsMargins(16, 12, 16, 16)

            d2xx_header = QLabel("<b>FTDI D2XX (Direct USB) Settings</b>")
            d2xx_header.setStyleSheet("QLabel { font-size: 14px; }")
            d2xx_layout.addWidget(d2xx_header)

            d2xx_status = QLabel(
                "Status: <span style='color:#ff9900'>UNTESTED</span> — "
                "Implemented from OSE V1.5.1 analysis and FTDI datasheet.\n"
                "May need tuning on real hardware. Treat values as starting points."
            )
            d2xx_status.setWordWrap(True)
            d2xx_status.setStyleSheet("QLabel { background: #2a2a3a; padding: 8px; border-radius: 4px; }")
            d2xx_layout.addWidget(d2xx_status)

            # Latency timer
            lat_group = QGroupBox("FTDI Latency Timer")
            lat_form = QFormLayout(lat_group)

            self.spin_d2xx_latency = QSpinBox()
            self.spin_d2xx_latency.setRange(1, 255)
            self.spin_d2xx_latency.setSuffix(" ms")
            self.spin_d2xx_latency.setValue(2)
            self.spin_d2xx_latency.setToolTip(
                "FTDI USB latency timer — how long the chip waits\n"
                "before sending a partial USB packet to the host.\n\n"
                "Default: 16ms (FTDI factory). OSE never changes it.\n"
                "Setting to 1-2ms gives ~30%% speed boost on reads.\n\n"
                "1ms = fastest (may overwhelm slow CPUs)\n"
                "2ms = recommended (good balance)\n"
                "16ms = FTDI default (safe but slow)"
            )
            lat_form.addRow("Latency Timer:", self.spin_d2xx_latency)

            lat_info = QLabel(
                "💡  OSE uses default 16ms. Setting to 1-2ms is the single\n"
                "    biggest speed improvement (~30%% faster reads)."
            )
            lat_info.setStyleSheet("QLabel { color: #88cc88; padding: 4px; }")
            lat_form.addRow(lat_info)
            d2xx_layout.addWidget(lat_group)

            # USB timeouts
            timeout_group = QGroupBox("D2XX Read/Write Timeouts")
            timeout_form = QFormLayout(timeout_group)

            self.spin_d2xx_read_timeout = QSpinBox()
            self.spin_d2xx_read_timeout.setRange(50, 30000)
            self.spin_d2xx_read_timeout.setSuffix(" ms")
            self.spin_d2xx_read_timeout.setValue(200)
            self.spin_d2xx_read_timeout.setSingleStep(50)
            self.spin_d2xx_read_timeout.setToolTip(
                "D2XX read timeout (ftd2xx.setTimeouts read_ms).\n"
                "200ms is aggressive — increase to 500-1000ms if reads fail."
            )
            timeout_form.addRow("Read Timeout:", self.spin_d2xx_read_timeout)

            self.spin_d2xx_write_timeout = QSpinBox()
            self.spin_d2xx_write_timeout.setRange(50, 30000)
            self.spin_d2xx_write_timeout.setSuffix(" ms")
            self.spin_d2xx_write_timeout.setValue(200)
            self.spin_d2xx_write_timeout.setSingleStep(50)
            self.spin_d2xx_write_timeout.setToolTip(
                "D2XX write timeout (ftd2xx.setTimeouts write_ms).\n"
                "200ms is fine for 8192 baud."
            )
            timeout_form.addRow("Write Timeout:", self.spin_d2xx_write_timeout)

            d2xx_layout.addWidget(timeout_group)

            # Timing offsets
            timing_group = QGroupBox("Timing Offsets (Real Hardware Tuning)")
            timing_form = QFormLayout(timing_group)

            timing_info = QLabel(
                "Adjust these if real-hardware comms are unreliable.\n"
                "Positive values make the tool SLOWER but more tolerant.\n"
                "Start at 0 and increase by 5-10ms if you see retries/timeouts."
            )
            timing_info.setWordWrap(True)
            timing_info.setStyleSheet("QLabel { color: #aaa; padding: 4px; }")
            timing_form.addRow(timing_info)

            self.spin_silence_offset = QSpinBox()
            self.spin_silence_offset.setRange(-50, 500)
            self.spin_silence_offset.setSuffix(" ms")
            self.spin_silence_offset.setValue(0)
            self.spin_silence_offset.setSingleStep(5)
            self.spin_silence_offset.setToolTip(
                "Extra delay added to WaitForSilence (bus-quiet detection).\n"
                "OSE default silence wait: 25ms.\n"
                "If your adapter is slow to flush, add 10-25ms here."
            )
            timing_form.addRow("Silence Wait Offset:", self.spin_silence_offset)

            self.spin_tx_delay_offset = QSpinBox()
            self.spin_tx_delay_offset.setRange(-20, 500)
            self.spin_tx_delay_offset.setSuffix(" ms")
            self.spin_tx_delay_offset.setValue(0)
            self.spin_tx_delay_offset.setSingleStep(5)
            self.spin_tx_delay_offset.setToolTip(
                "Extra delay added AFTER each TX frame before reading response.\n"
                "Helps slow adapters or long USB cables.\n"
                "OSE inter-frame delay: 10ms (VR/VS), 4ms (VT, bench).\n"
                "Try +10ms if you see echo-related failures."
            )
            timing_form.addRow("TX Post-Delay Offset:", self.spin_tx_delay_offset)

            self.spin_retry_delay_offset = QSpinBox()
            self.spin_retry_delay_offset.setRange(-50, 500)
            self.spin_retry_delay_offset.setSuffix(" ms")
            self.spin_retry_delay_offset.setValue(0)
            self.spin_retry_delay_offset.setSingleStep(10)
            self.spin_retry_delay_offset.setToolTip(
                "Extra delay between retry attempts.\n"
                "Base retry delay: 50ms.\n"
                "Increase if the bus needs more time to settle after errors."
            )
            timing_form.addRow("Retry Delay Offset:", self.spin_retry_delay_offset)

            self.spin_erase_timeout_offset = QSpinBox()
            self.spin_erase_timeout_offset.setRange(-1000, 10000)
            self.spin_erase_timeout_offset.setSuffix(" ms")
            self.spin_erase_timeout_offset.setValue(0)
            self.spin_erase_timeout_offset.setSingleStep(500)
            self.spin_erase_timeout_offset.setToolTip(
                "Extra time added to sector erase timeout.\n"
                "Base erase timeout: 5000ms per sector.\n"
                "Some flash chips are slower — add 2000-5000ms if erase fails."
            )
            timing_form.addRow("Erase Timeout Offset:", self.spin_erase_timeout_offset)

            self.spin_cleanup_delay_offset = QSpinBox()
            self.spin_cleanup_delay_offset.setRange(-500, 5000)
            self.spin_cleanup_delay_offset.setSuffix(" ms")
            self.spin_cleanup_delay_offset.setValue(0)
            self.spin_cleanup_delay_offset.setSingleStep(100)
            self.spin_cleanup_delay_offset.setToolTip(
                "Extra delay after cleanup/reset before re-enabling chatter.\n"
                "Base cleanup delay: 750ms.\n"
                "Increase if ECU doesn't respond after a write session."
            )
            timing_form.addRow("Cleanup Delay Offset:", self.spin_cleanup_delay_offset)

            d2xx_layout.addWidget(timing_group)

            # Presets
            preset_group = QGroupBox("Vehicle Timing Presets")
            preset_layout = QVBoxLayout(preset_group)
            preset_info = QLabel(
                "Quick presets from OSE V1.5.1 — sets inter-frame delay\n"
                "and timing offsets to values used by the original tool."
            )
            preset_info.setWordWrap(True)
            preset_info.setStyleSheet("QLabel { color: #aaa; }")
            preset_layout.addWidget(preset_info)

            preset_row = QHBoxLayout()
            self.combo_preset = QComboBox()
            self.combo_preset.addItem("Custom", None)
            self.combo_preset.addItem("VR Auto/Manual (10ms IFD)", {"ifd": 10, "silence": 0, "tx": 0})
            self.combo_preset.addItem("VS Auto/Manual (10ms IFD)", {"ifd": 10, "silence": 0, "tx": 0})
            self.combo_preset.addItem("VT In-Car (4ms IFD)", {"ifd": 4, "silence": 0, "tx": 0})
            self.combo_preset.addItem("Flash PCM Bench (4ms IFD)", {"ifd": 4, "silence": 0, "tx": 0})
            self.combo_preset.addItem("ALDL Logger (1ms IFD)", {"ifd": 1, "silence": 0, "tx": 0})
            self.combo_preset.addItem("Slow/Reliable (+25ms all)", {"ifd": 15, "silence": 25, "tx": 10})
            self.combo_preset.setToolTip("Select a preset or use Custom to set values manually")
            self.combo_preset.currentIndexChanged.connect(self._on_preset_changed)
            preset_row.addWidget(QLabel("Preset:"))
            preset_row.addWidget(self.combo_preset)
            preset_row.addStretch()
            preset_layout.addLayout(preset_row)
            d2xx_layout.addWidget(preset_group)

            # Apply / Reset
            btn_row = QHBoxLayout()
            self.apply_btn = QPushButton("Apply Transport Settings")
            self.apply_btn.setToolTip("Apply these transport settings to the active connection")
            self.apply_btn.clicked.connect(self._on_apply)
            btn_row.addWidget(self.apply_btn)

            self.reset_btn = QPushButton("Reset to Defaults")
            self.reset_btn.setToolTip("Reset all transport settings to factory defaults")
            self.reset_btn.clicked.connect(self._on_reset)
            btn_row.addWidget(self.reset_btn)
            btn_row.addStretch()
            d2xx_layout.addLayout(btn_row)

            d2xx_layout.addStretch()
            d2xx_scroll.setWidget(d2xx_widget)
            splitter.addWidget(d2xx_scroll)

            # Set splitter sizes (top 40%, bottom 60%)
            splitter.setSizes([300, 500])
            outer.addWidget(splitter)

        def _load_from_config(self, config: CommConfig) -> None:
            """Populate widgets from config (using defaults for transport-specific values)."""
            # PySerial defaults
            self.spin_py_read_timeout.setValue(100)
            self.spin_py_write_timeout.setValue(1000)
            self.spin_py_read_buffer.setValue(1000)
            self.chk_py_rtscts.setChecked(False)
            self.chk_py_dsrdtr.setChecked(False)
            self.chk_py_xonxoff.setChecked(False)
            # D2XX defaults
            self.spin_d2xx_latency.setValue(2)
            self.spin_d2xx_read_timeout.setValue(200)
            self.spin_d2xx_write_timeout.setValue(200)
            # Timing offsets start at 0
            self.spin_silence_offset.setValue(0)
            self.spin_tx_delay_offset.setValue(0)
            self.spin_retry_delay_offset.setValue(0)
            self.spin_erase_timeout_offset.setValue(0)
            self.spin_cleanup_delay_offset.setValue(0)

        def _on_preset_changed(self, index: int) -> None:
            data = self.combo_preset.currentData()
            if data and isinstance(data, dict):
                if "ifd" in data:
                    self._config.inter_frame_delay_ms = data["ifd"]
                if "silence" in data:
                    self.spin_silence_offset.setValue(data["silence"])
                if "tx" in data:
                    self.spin_tx_delay_offset.setValue(data["tx"])

        def get_transport_settings(self) -> dict:
            """Return all transport settings as a dict for use by transports."""
            return {
                "pyserial": {
                    "read_timeout_ms": self.spin_py_read_timeout.value(),
                    "write_timeout_ms": self.spin_py_write_timeout.value(),
                    "read_buffer_size": self.spin_py_read_buffer.value(),
                    "rtscts": self.chk_py_rtscts.isChecked(),
                    "dsrdtr": self.chk_py_dsrdtr.isChecked(),
                    "xonxoff": self.chk_py_xonxoff.isChecked(),
                },
                "d2xx": {
                    "latency_timer_ms": self.spin_d2xx_latency.value(),
                    "read_timeout_ms": self.spin_d2xx_read_timeout.value(),
                    "write_timeout_ms": self.spin_d2xx_write_timeout.value(),
                },
                "timing_offsets": {
                    "silence_offset_ms": self.spin_silence_offset.value(),
                    "tx_delay_offset_ms": self.spin_tx_delay_offset.value(),
                    "retry_delay_offset_ms": self.spin_retry_delay_offset.value(),
                    "erase_timeout_offset_ms": self.spin_erase_timeout_offset.value(),
                    "cleanup_delay_offset_ms": self.spin_cleanup_delay_offset.value(),
                },
            }

        def _on_apply(self) -> None:
            self.config_changed.emit()

        def _on_reset(self) -> None:
            self._load_from_config(self._config)
            self.config_changed.emit()

    class OptionsWidget(QWidget):
        """Scrollable options/settings tab for CommConfig + LogConfig parameters."""
        config_changed = Signal()

        def __init__(self, config: CommConfig, log_cfg: LogConfig = None, parent=None):
            super().__init__(parent)
            self._config = config
            self._log_cfg = log_cfg or LogConfig()
            self._build_ui()
            self._load_from_config(config)
            self._load_log_config(self._log_cfg)

        def _build_ui(self) -> None:
            outer = QVBoxLayout(self)
            outer.setContentsMargins(0, 0, 0, 0)

            # Scroll area
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)
            scroll.setStyleSheet("QScrollArea { background: transparent; }")

            content = QWidget()
            layout = QVBoxLayout(content)
            layout.setSpacing(12)
            layout.setContentsMargins(16, 16, 16, 16)

            # ── Connection Settings ──
            conn_group = QGroupBox("Connection Settings")
            conn_layout = QFormLayout(conn_group)

            self.spin_baud = QSpinBox()
            self.spin_baud.setRange(300, 115200)
            self.spin_baud.setSingleStep(100)
            self.spin_baud.setToolTip("ALDL baud rate (standard: 8192)")
            conn_layout.addRow("Baud Rate:", self.spin_baud)

            self.combo_device_id = QComboBox()
            self.combo_device_id.addItem("F7 — VX/VY", 0xF7)
            self.combo_device_id.addItem("F5 — VS/VT", 0xF5)
            self.combo_device_id.addItem("F4 — VR", 0xF4)
            self.combo_device_id.setToolTip("ALDL device ID for the target ECU")
            conn_layout.addRow("Device ID:", self.combo_device_id)

            layout.addWidget(conn_group)

            # ── Timing Settings ──
            timing_group = QGroupBox("Timing Settings")
            timing_layout = QFormLayout(timing_group)

            self.spin_timeout = QSpinBox()
            self.spin_timeout.setRange(100, 30000)
            self.spin_timeout.setSuffix(" ms")
            self.spin_timeout.setSingleStep(100)
            self.spin_timeout.setToolTip("Response timeout for each ALDL transaction")
            timing_layout.addRow("Timeout:", self.spin_timeout)

            self.spin_inter_frame = QSpinBox()
            self.spin_inter_frame.setRange(0, 1000)
            self.spin_inter_frame.setSuffix(" ms")
            self.spin_inter_frame.setSingleStep(5)
            self.spin_inter_frame.setToolTip("Delay between consecutive frames (helps slow adapters)")
            timing_layout.addRow("Inter-frame Delay:", self.spin_inter_frame)

            layout.addWidget(timing_group)

            # ── Retry & Write Settings ──
            retry_group = QGroupBox("Retry & Write Settings")
            retry_layout = QFormLayout(retry_group)

            self.spin_retries = QSpinBox()
            self.spin_retries.setRange(0, 100)
            self.spin_retries.setToolTip("Max retry count for failed transactions")
            retry_layout.addRow("Max Retries:", self.spin_retries)

            self.spin_chunk = QSpinBox()
            self.spin_chunk.setRange(1, 128)
            self.spin_chunk.setSuffix(" bytes")
            self.spin_chunk.setToolTip("Flash write chunk size per frame (OSE default: 32)")
            retry_layout.addRow("Write Chunk Size:", self.spin_chunk)

            layout.addWidget(retry_group)

            # ── Flash Behaviour ──
            flash_group = QGroupBox("Flash Behaviour")
            flash_layout = QVBoxLayout(flash_group)

            self.chk_auto_checksum = QCheckBox("Auto-fix checksum before write")
            self.chk_auto_checksum.setToolTip("Automatically compute and fix the bin checksum before flashing")
            flash_layout.addWidget(self.chk_auto_checksum)

            self.chk_verify_write = QCheckBox("Verify checksum after write")
            self.chk_verify_write.setToolTip("Read back and verify the ECU checksum after each write operation")
            flash_layout.addWidget(self.chk_verify_write)

            self.chk_high_speed = QCheckBox("High-speed read mode")
            self.chk_high_speed.setToolTip(
                "Patch kernel for faster reads (byte 21 = 0x81).\n"
                "May not work with all ALDL adapters."
            )
            flash_layout.addWidget(self.chk_high_speed)

            self.chk_ignore_echo = QCheckBox("Ignore echo bytes")
            self.chk_ignore_echo.setToolTip(
                "Strip TX echo from received data.\n"
                "Required for most half-duplex ALDL cables."
            )
            flash_layout.addWidget(self.chk_ignore_echo)

            self.chk_disable_bcm = QCheckBox("Silence BCM chatter (Mode 8)")
            self.chk_disable_bcm.setChecked(False)
            self.chk_disable_bcm.setToolTip(
                "Send Mode 8 silence to the BCM before flash operations.\n"
                "OFF by default — bench and virtual setups have no BCM.\n"
                "Only enable this if flashing in-car with the BCM connected.\n"
                "Not needed for VATS-disabled ECUs or standalone bench rigs."
            )
            flash_layout.addWidget(self.chk_disable_bcm)

            layout.addWidget(flash_group)

            # ── Event Bus Logging ── (toggles what goes to the Log tab & file log)
            log_group = QGroupBox("Event Bus Logging")
            log_outer = QVBoxLayout(log_group)

            # Combo: preset profiles
            profile_row = QHBoxLayout()
            profile_row.addWidget(QLabel("Preset:"))
            self.log_profile_combo = QComboBox()
            self.log_profile_combo.addItem("Normal (default)")
            self.log_profile_combo.addItem("Verbose (all on)")
            self.log_profile_combo.addItem("Quiet (errors only)")
            self.log_profile_combo.addItem("Frames only")
            self.log_profile_combo.addItem("Custom")
            self.log_profile_combo.setToolTip("Quick preset — select 'Custom' to pick individual channels")
            self.log_profile_combo.currentIndexChanged.connect(self._on_log_profile_changed)
            profile_row.addWidget(self.log_profile_combo)
            profile_row.addStretch()
            log_outer.addLayout(profile_row)

            # Debug-level frame logging
            frame_group = QGroupBox("Frame-Level (DEBUG)")
            frame_layout = QVBoxLayout(frame_group)
            self.chk_log_tx_frames = QCheckBox("TX frames (hex dump)")
            self.chk_log_rx_frames = QCheckBox("RX frames (hex dump)")
            self.chk_log_echo_bytes = QCheckBox("Echo consume details (noisy)")
            for w in (self.chk_log_tx_frames, self.chk_log_rx_frames, self.chk_log_echo_bytes):
                frame_layout.addWidget(w)
            log_outer.addWidget(frame_group)

            # Operation-level logging
            op_group = QGroupBox("Operation-Level (INFO)")
            op_layout = QVBoxLayout(op_group)
            self.chk_log_state_changes = QCheckBox("State transitions")
            self.chk_log_security = QCheckBox("Seed/key exchange")
            self.chk_log_kernel_upload = QCheckBox("Kernel upload")
            self.chk_log_erase_sectors = QCheckBox("Sector erase progress")
            self.chk_log_write_chunks = QCheckBox("Write chunk progress")
            self.chk_log_verify = QCheckBox("Checksum verify")
            self.chk_log_flash_info = QCheckBox("Flash chip info")
            self.chk_log_chatter = QCheckBox("Bus silence/unsilence")
            self.chk_log_progress = QCheckBox("Progress bar updates")
            for w in (self.chk_log_state_changes, self.chk_log_security,
                      self.chk_log_kernel_upload, self.chk_log_erase_sectors,
                      self.chk_log_write_chunks, self.chk_log_verify,
                      self.chk_log_flash_info, self.chk_log_chatter,
                      self.chk_log_progress):
                op_layout.addWidget(w)
            log_outer.addWidget(op_group)

            # Error/Warning level
            err_group = QGroupBox("Error / Warning")
            err_layout = QVBoxLayout(err_group)
            self.chk_log_retries = QCheckBox("Retry attempts")
            self.chk_log_timeouts = QCheckBox("Frame timeouts")
            self.chk_log_checksum_errors = QCheckBox("RX checksum failures")
            for w in (self.chk_log_retries, self.chk_log_timeouts, self.chk_log_checksum_errors):
                err_layout.addWidget(w)
            log_outer.addWidget(err_group)

            # Session-level
            sess_group = QGroupBox("Session / UI")
            sess_layout = QVBoxLayout(sess_group)
            self.chk_log_session_summary = QCheckBox("Flash session summary box")
            self.chk_log_click_events = QCheckBox("GUI button click events")
            self.chk_log_timestamps = QCheckBox("Timestamps on every event")
            for w in (self.chk_log_session_summary, self.chk_log_click_events, self.chk_log_timestamps):
                sess_layout.addWidget(w)
            log_outer.addWidget(sess_group)

            # Second event bus toggle
            bus2_group = QGroupBox("Debug Event Bus (secondary)")
            bus2_layout = QVBoxLayout(bus2_group)
            self.chk_debug_bus_enabled = QCheckBox("Enable secondary debug event bus")
            self.chk_debug_bus_enabled.setToolTip(
                "When enabled, raw frame TX/RX events are also emitted\n"
                "to a second 'debug' bus that can be viewed in the Log tab\n"
                "with a [DEBUG] prefix. Useful for protocol debugging."
            )
            bus2_layout.addWidget(self.chk_debug_bus_enabled)

            self.combo_debug_bus_output = QComboBox()
            self.combo_debug_bus_output.addItem("Log Tab only")
            self.combo_debug_bus_output.addItem("File only (debug.log)")
            self.combo_debug_bus_output.addItem("Both Log Tab + File")
            self.combo_debug_bus_output.setToolTip("Where should debug bus events go?")
            bus2_layout.addWidget(QLabel("Debug bus output:"))
            bus2_layout.addWidget(self.combo_debug_bus_output)
            log_outer.addWidget(bus2_group)

            layout.addWidget(log_group)

            # ── Persistence ──
            persist_group = QGroupBox("Settings Persistence")
            persist_layout = QVBoxLayout(persist_group)
            self.chk_persist_on_close = QCheckBox("Save settings to disk on exit")
            self.chk_persist_on_close.setChecked(True)
            self.chk_persist_on_close.setToolTip("Persist CommConfig + LogConfig to settings.json on close")
            persist_layout.addWidget(self.chk_persist_on_close)
            layout.addWidget(persist_group)

            # ── Apply / Reset buttons ──
            btn_row = QHBoxLayout()
            self.apply_btn = QPushButton("Apply")
            self.apply_btn.setToolTip("Apply current settings to the active configuration")
            self.apply_btn.clicked.connect(self._on_apply)
            btn_row.addWidget(self.apply_btn)

            self.reset_btn = QPushButton("Reset to Defaults")
            self.reset_btn.setToolTip("Reset all settings to factory defaults")
            self.reset_btn.clicked.connect(self._on_reset)
            btn_row.addWidget(self.reset_btn)
            btn_row.addStretch()
            layout.addLayout(btn_row)

            layout.addStretch()
            scroll.setWidget(content)
            outer.addWidget(scroll)

        def _load_from_config(self, config: CommConfig) -> None:
            """Populate widgets from a CommConfig."""
            self.spin_baud.setValue(config.baud)
            # Set device ID combo
            for i in range(self.combo_device_id.count()):
                if self.combo_device_id.itemData(i) == config.device_id:
                    self.combo_device_id.setCurrentIndex(i)
                    break
            self.spin_timeout.setValue(config.timeout_ms)
            self.spin_inter_frame.setValue(config.inter_frame_delay_ms)
            self.spin_retries.setValue(config.max_retries)
            self.spin_chunk.setValue(config.write_chunk_size)
            self.chk_auto_checksum.setChecked(config.auto_checksum_fix)
            self.chk_verify_write.setChecked(True)
            self.chk_high_speed.setChecked(config.high_speed_read)
            self.chk_ignore_echo.setChecked(config.ignore_echo)
            self.chk_disable_bcm.setChecked(config.disable_bcm_chatter)

        def _load_log_config(self, cfg: LogConfig) -> None:
            """Populate logging checkboxes from a LogConfig."""
            self.chk_log_tx_frames.setChecked(cfg.log_tx_frames)
            self.chk_log_rx_frames.setChecked(cfg.log_rx_frames)
            self.chk_log_echo_bytes.setChecked(cfg.log_echo_bytes)
            self.chk_log_state_changes.setChecked(cfg.log_state_changes)
            self.chk_log_security.setChecked(cfg.log_security)
            self.chk_log_kernel_upload.setChecked(cfg.log_kernel_upload)
            self.chk_log_erase_sectors.setChecked(cfg.log_erase_sectors)
            self.chk_log_write_chunks.setChecked(cfg.log_write_chunks)
            self.chk_log_verify.setChecked(cfg.log_verify)
            self.chk_log_flash_info.setChecked(cfg.log_flash_info)
            self.chk_log_chatter.setChecked(cfg.log_chatter)
            self.chk_log_progress.setChecked(cfg.log_progress)
            self.chk_log_retries.setChecked(cfg.log_retries)
            self.chk_log_timeouts.setChecked(cfg.log_timeouts)
            self.chk_log_checksum_errors.setChecked(cfg.log_checksum_errors)
            self.chk_log_session_summary.setChecked(cfg.log_session_summary)
            self.chk_log_click_events.setChecked(cfg.log_click_events)
            self.chk_log_timestamps.setChecked(cfg.log_timestamps)

        def apply_log_config(self, cfg: LogConfig) -> None:
            """Write checkbox states into a LogConfig."""
            cfg.log_tx_frames = self.chk_log_tx_frames.isChecked()
            cfg.log_rx_frames = self.chk_log_rx_frames.isChecked()
            cfg.log_echo_bytes = self.chk_log_echo_bytes.isChecked()
            cfg.log_state_changes = self.chk_log_state_changes.isChecked()
            cfg.log_security = self.chk_log_security.isChecked()
            cfg.log_kernel_upload = self.chk_log_kernel_upload.isChecked()
            cfg.log_erase_sectors = self.chk_log_erase_sectors.isChecked()
            cfg.log_write_chunks = self.chk_log_write_chunks.isChecked()
            cfg.log_verify = self.chk_log_verify.isChecked()
            cfg.log_flash_info = self.chk_log_flash_info.isChecked()
            cfg.log_chatter = self.chk_log_chatter.isChecked()
            cfg.log_progress = self.chk_log_progress.isChecked()
            cfg.log_retries = self.chk_log_retries.isChecked()
            cfg.log_timeouts = self.chk_log_timeouts.isChecked()
            cfg.log_checksum_errors = self.chk_log_checksum_errors.isChecked()
            cfg.log_session_summary = self.chk_log_session_summary.isChecked()
            cfg.log_click_events = self.chk_log_click_events.isChecked()
            cfg.log_timestamps = self.chk_log_timestamps.isChecked()

        def _on_log_profile_changed(self, index: int) -> None:
            """Apply a logging preset profile."""
            if index == 0:    # Normal
                self._load_log_config(LogConfig())
            elif index == 1:  # Verbose
                cfg = LogConfig()
                for f in fields(cfg):
                    if f.name.startswith("log_"):
                        setattr(cfg, f.name, True)
                self._load_log_config(cfg)
            elif index == 2:  # Quiet
                cfg = LogConfig()
                for f in fields(cfg):
                    if f.name.startswith("log_"):
                        setattr(cfg, f.name, False)
                cfg.log_retries = True
                cfg.log_timeouts = True
                cfg.log_checksum_errors = True
                cfg.log_session_summary = True
                self._load_log_config(cfg)
            elif index == 3:  # Frames only
                cfg = LogConfig()
                for f in fields(cfg):
                    if f.name.startswith("log_"):
                        setattr(cfg, f.name, False)
                cfg.log_tx_frames = True
                cfg.log_rx_frames = True
                cfg.log_timestamps = True
                self._load_log_config(cfg)
            # index == 4 is Custom — don't change anything

        def apply_to_config(self, config: CommConfig) -> None:
            """Write widget values into a CommConfig."""
            config.baud = self.spin_baud.value()
            config.device_id = self.combo_device_id.currentData()
            config.timeout_ms = self.spin_timeout.value()
            config.inter_frame_delay_ms = self.spin_inter_frame.value()
            config.max_retries = self.spin_retries.value()
            config.write_chunk_size = self.spin_chunk.value()
            config.auto_checksum_fix = self.chk_auto_checksum.isChecked()
            config.high_speed_read = self.chk_high_speed.isChecked()
            config.ignore_echo = self.chk_ignore_echo.isChecked()
            config.disable_bcm_chatter = self.chk_disable_bcm.isChecked()

        def _on_apply(self) -> None:
            self.apply_to_config(self._config)
            self.apply_log_config(self._log_cfg)
            self.config_changed.emit()

        def _on_reset(self) -> None:
            defaults = CommConfig()
            default_log = LogConfig()
            self._load_from_config(defaults)
            self._load_log_config(default_log)
            self.apply_to_config(self._config)
            self.apply_log_config(self._log_cfg)
            self.config_changed.emit()

    class FlashWorker(QObject):
        """Background worker for flash operations (runs in QThread)."""
        progress = Signal(int, int, str)
        log_message = Signal(str, str)
        finished = Signal(bool)
        read_data = Signal(bytearray)   # Emitted with 128KB data after a successful read
        state_changed = Signal(str)

        def __init__(self, comm: ECUComm, parent=None):
            super().__init__(parent)
            self.comm = comm
            self._op = FlashOp(comm)
            self._task: Optional[str] = None
            self._bin_data: Optional[bytearray] = None
            self._mode: str = "BIN"

        def setup_write(self, bin_data: bytearray, mode: str = "BIN") -> None:
            self._task = "write"
            self._bin_data = bin_data
            self._mode = mode

        def setup_read(self) -> None:
            self._task = "read"

        def setup_custom_write(self, bin_data: bytearray, sectors: list) -> None:
            self._task = "custom_write"
            self._bin_data = bin_data
            self._sectors = sectors

        def setup_custom_read(self, start_addr: int, end_addr: int) -> None:
            self._task = "custom_read"
            self._custom_start = start_addr
            self._custom_end = end_addr

        def setup_chaos(self, config: dict, bin_data: bytearray) -> None:
            self._task = "chaos"
            self._bin_data = bin_data
            self._chaos_cfg = config

        @Slot()
        def run(self) -> None:
            # Clear stale callbacks to prevent accumulation across operations
            self.comm.clear_callbacks()
            # Wire up event callbacks
            self.comm.on("log", lambda msg, level="info", **_: self.log_message.emit(msg, level))
            self.comm.on("progress", lambda current, total, label="", **_: self.progress.emit(current, total, label))
            self.comm.on("state", lambda state, **_: self.state_changed.emit(state.name))

            # Clear stale cancel flag so a previous cancel doesn't
            # abort this operation immediately (bug #3: reset_cancel never called)
            self.comm.reset_cancel()

            try:
                if self._task == "write" and self._bin_data:
                    result = self._op.full_write(self._bin_data, self._mode)
                    self.finished.emit(result)
                elif self._task == "read":
                    data = self._op.full_read()
                    if data is not None:
                        self.read_data.emit(data)
                    self.finished.emit(data is not None)
                elif self._task == "custom_write" and self._bin_data:
                    result = self._op.custom_write(self._bin_data, self._sectors)
                    self.finished.emit(result)
                elif self._task == "custom_read":
                    data = self._op.custom_read(self._custom_start, self._custom_end)
                    if data is not None:
                        self.read_data.emit(bytearray(data))
                    self.finished.emit(data is not None)
                elif self._task == "chaos" and self._bin_data:
                    result = self._run_chaos()
                    self.finished.emit(result)
                else:
                    self.finished.emit(False)
            except Exception as e:
                self.log_message.emit(f"Exception: {e}", "error")
                log.exception("Flash worker exception")
                self.finished.emit(False)

        def _run_chaos(self) -> bool:
            """Run the chaos test loop (read→write→readback→compare)."""
            cfg = self._chaos_cfg
            max_cycles = cfg.get("cycles", 0)  # 0 = infinite
            mode = cfg.get("mode", "BIN")
            delay = cfg.get("delay", 5)
            stop_on_fail = cfg.get("stop_on_fail", True)
            compare_bytes = cfg.get("compare_bytes", True)

            cycle = 0
            passed = 0
            failed = 0

            while True:
                cycle += 1
                if max_cycles > 0 and cycle > max_cycles:
                    break
                if self.comm.cancelled:
                    self.log_message.emit(f"Chaos test cancelled after {cycle - 1} cycles", "warning")
                    break

                self.log_message.emit(f"\n═══ CHAOS CYCLE {cycle} ═══", "info")

                # Step 1: Write the loaded bin
                self.log_message.emit(f"  [{cycle}] Writing {mode}...", "info")
                write_ok = self._op.full_write(self._bin_data, mode)
                if not write_ok:
                    failed += 1
                    self.log_message.emit(f"  [{cycle}] WRITE FAILED", "error")
                    if stop_on_fail:
                        break
                    time.sleep(delay)
                    continue

                # Step 2: Read back
                self.log_message.emit(f"  [{cycle}] Reading back...", "info")
                readback = self._op.full_read()
                if readback is None:
                    failed += 1
                    self.log_message.emit(f"  [{cycle}] READBACK FAILED", "error")
                    if stop_on_fail:
                        break
                    time.sleep(delay)
                    continue

                # Step 3: Compare
                if compare_bytes:
                    start_off, end_off = WRITE_RANGES.get(mode, (0x2000, 0x1BFFF))
                    mismatch = False
                    for addr in range(start_off, end_off + 1):
                        if readback[addr] != self._bin_data[addr]:
                            self.log_message.emit(
                                f"  [{cycle}] MISMATCH at ${addr:05X}: "
                                f"expected 0x{self._bin_data[addr]:02X}, "
                                f"got 0x{readback[addr]:02X}",
                                "error"
                            )
                            mismatch = True
                            break
                    if mismatch:
                        failed += 1
                        if stop_on_fail:
                            break
                    else:
                        passed += 1
                        self.log_message.emit(f"  [{cycle}] VERIFY OK ✓", "info")
                else:
                    passed += 1

                self.log_message.emit(
                    f"  Cycle {cycle} done — Passed: {passed}, Failed: {failed}", "info"
                )

                if delay > 0 and not self.comm.cancelled:
                    time.sleep(delay)

            self.log_message.emit(
                f"\n═══ CHAOS TEST COMPLETE — {cycle} cycles, {passed} passed, {failed} failed ═══",
                "info" if failed == 0 else "warning"
            )
            return failed == 0

    class MainWindow(QMainWindow):
        """Main application window."""

        def __init__(self):
            super().__init__()
            self.setWindowTitle(f"{__app_name__} v{__version__}")
            self.setMinimumSize(1100, 750)
            self._apply_dark_theme()

            # Backend instances — load persisted settings if available
            saved_comm, saved_log_cfg = SettingsManager.load()
            self._transport: Optional[BaseTransport] = None
            self._comm: Optional[ECUComm] = None
            self._config = saved_comm
            self._log_cfg = saved_log_cfg
            self._bin_data: Optional[bytearray] = None
            self._bin_path: Optional[str] = None
            self._logger: Optional[DataLogger] = None
            self._live_tuner: Optional[LiveTuner] = None
            self._flash_thread: Optional[QThread] = None
            self._flash_active: bool = False   # True while a read/write op is running
            self._flash_task: Optional[str] = None  # "read" or "write" — to gate disconnect severity
            self._verify_after_write: bool = True
            self._vecu_bin_path: Optional[str] = None  # Virtual ECU .bin path
            self._persist_on_close: bool = True  # Save settings on exit

            self._build_ui()
            self._connect_signals()
            self._refresh_ports()

        def _apply_dark_theme(self) -> None:
            self.setStyleSheet("""
                QMainWindow, QWidget { background-color: #1e1e1e; color: #d4d4d4; }
                QGroupBox { border: 1px solid #3c3c3c; border-radius: 4px; margin-top: 8px;
                            padding-top: 14px; color: #ccc; font-weight: bold; }
                QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
                QPushButton { background: #3c3c3c; border: 1px solid #555; border-radius: 3px;
                              padding: 6px 16px; color: #ddd; min-height: 24px; }
                QPushButton:hover { background: #4c4c4c; }
                QPushButton:pressed { background: #2a2a2a; }
                QPushButton:disabled { background: #2a2a2a; color: #666; }
                QPushButton#connectBtn { background: #1a5c1a; }
                QPushButton#connectBtn:hover { background: #2a7c2a; }
                QPushButton#writeBtn { background: #8b4513; }
                QPushButton#writeBtn:hover { background: #a0522d; }
                QPushButton#readBtn { background: #1a3c6c; }
                QPushButton#readBtn:hover { background: #2a5c9c; }
                QComboBox { background: #3c3c3c; border: 1px solid #555; border-radius: 3px;
                            padding: 4px; color: #ddd; }
                QProgressBar { background: #111111; border: 1px solid #3c3c3c; border-radius: 3px;
                               text-align: center; color: #ffffff; font-weight: bold; }
                QProgressBar::chunk { background: #00c853; border-radius: 2px; }
                QTabWidget::pane { border: 1px solid #3c3c3c; }
                QTabBar::tab { background: #2d2d2d; border: 1px solid #3c3c3c; padding: 6px 16px;
                               color: #aaa; }
                QTabBar::tab:selected { background: #3c3c3c; color: #fff; border-bottom: 2px solid #4fc3f7; }
                QStatusBar { background: #1e1e1e; color: #888; }
            """)

        def _build_ui(self) -> None:
            central = QWidget()
            self.setCentralWidget(central)
            main_layout = QVBoxLayout(central)
            main_layout.setSpacing(6)
            main_layout.setContentsMargins(8, 8, 8, 8)

            # ── Menu bar ──
            self._build_menu_bar()

            # ── Top toolbar ──
            toolbar = QHBoxLayout()

            # Port selection
            port_group = QGroupBox("Connection")
            port_layout = QHBoxLayout(port_group)
            self.port_combo = QComboBox()
            self.port_combo.setMinimumWidth(120)
            self.port_combo.setToolTip("Select the serial port connected to your ALDL cable")
            port_layout.addWidget(QLabel("Port:"))
            port_layout.addWidget(self.port_combo)

            self.transport_combo = QComboBox()
            self.transport_combo.addItem("PySerial (COM)", "pyserial")
            if D2XX_AVAILABLE:
                self.transport_combo.addItem("FTDI D2XX", "d2xx")
            self.transport_combo.addItem("Loopback (Test)", "loopback")
            self.transport_combo.addItem("━━ Virtual ECU ━━", "vecu")
            self.transport_combo.setToolTip(
                "PySerial: standard COM port via VCP driver\n"
                "FTDI D2XX: direct FTDI driver (lower latency)\n"
                "Loopback: basic offline testing (zeros)\n"
                "Virtual ECU: load a .bin file as a simulated ECU\n"
                "  → Read ECU returns real bin data\n"
                "  → Dashboard shows simulated sensors"
            )
            self.transport_combo.currentIndexChanged.connect(self._on_transport_changed)
            port_layout.addWidget(self.transport_combo)

            self.refresh_btn = QPushButton("↻")
            self.refresh_btn.setFixedWidth(32)
            self.refresh_btn.setStyleSheet(
                "QPushButton { background: #3c3c3c; border: 1px solid #555; "
                "border-radius: 3px; font-size: 14px; color: #ddd; min-height: 24px; }"
                "QPushButton:hover { background: #4c4c4c; }"
            )
            self.refresh_btn.setToolTip("Refresh serial port list")
            port_layout.addWidget(self.refresh_btn)

            self.connect_btn = QPushButton("Connect")
            self.connect_btn.setObjectName("connectBtn")
            self.connect_btn.setToolTip(
                "Connect to ECU via the selected port.\n"
                "Performs echo detection, silences bus chatter, and identifies the PCM."
            )
            port_layout.addWidget(self.connect_btn)

            toolbar.addWidget(port_group)

            # File operations
            file_group = QGroupBox("Bin File")
            file_layout = QHBoxLayout(file_group)
            self.file_label = QLabel("No file loaded")
            self.file_label.setStyleSheet("color: #888;")
            file_layout.addWidget(self.file_label)

            self.load_btn = QPushButton("Load .bin")
            self.load_btn.setToolTip(
                "Load a .bin or .cal file from disk.\n"
                "16KB cal files are auto-padded to 128KB.\n"
                "Checksum is verified on load."
            )
            file_layout.addWidget(self.load_btn)

            self.save_btn = QPushButton("Save .bin")
            self.save_btn.setEnabled(False)
            self.save_btn.setToolTip("Save the current bin to disk (checksum auto-fixed)")
            file_layout.addWidget(self.save_btn)

            toolbar.addWidget(file_group)

            # Flash operations
            flash_group = QGroupBox("Flash")
            flash_layout = QHBoxLayout(flash_group)

            self.read_btn = QPushButton("Read ECU")
            self.read_btn.setObjectName("readBtn")
            self.read_btn.setEnabled(False)
            self.read_btn.setToolTip(
                "Read the full 128KB flash contents from the ECU.\n"
                "The bin is saved to disk after a successful read.\n"
                "This does NOT modify the ECU."
            )
            flash_layout.addWidget(self.read_btn)

            self.write_mode_combo = QComboBox()
            self.write_mode_combo.addItem("BIN", "BIN")
            self.write_mode_combo.addItem("CAL", "CAL")
            self.write_mode_combo.setToolTip(
                "BIN: Full binary write — erases sectors 0-6 and writes\n"
                "     the entire OS + calibration (104KB). Use for OS changes.\n\n"
                "CAL: Calibration-only write — erases sector 1 ($4000-$7FFF)\n"
                "     and writes only the 16KB calibration area.\n"
                "     Cal files are always padded to 128KB automatically.\n"
                "     Faster and safer for tune-only changes."
            )
            flash_layout.addWidget(self.write_mode_combo)

            self.write_btn = QPushButton("Write ECU")
            self.write_btn.setObjectName("writeBtn")
            self.write_btn.setEnabled(False)
            self.write_btn.setToolTip(
                "⚠ WARNING: Writes the loaded bin to the ECU flash chip.\n"
                "This ERASES and REPROGRAMS the flash.\n\n"
                "DO NOT disconnect power or the ALDL cable during write!\n"
                "A failed write can brick the PCM — keep a backup bin!"
            )
            flash_layout.addWidget(self.write_btn)

            self.cancel_btn = QPushButton("Cancel")
            self.cancel_btn.setEnabled(False)
            self.cancel_btn.setToolTip(
                "Cancel the current flash operation.\n"
                "⚠ Cancelling during erase/write may leave the\n"
                "PCM in an unrecoverable state!"
            )
            flash_layout.addWidget(self.cancel_btn)

            toolbar.addWidget(flash_group)
            main_layout.addLayout(toolbar)

            # ── Progress bar ──
            self.progress_bar = QProgressBar()
            self.progress_bar.setMaximum(100)
            self.progress_bar.setFixedHeight(20)
            main_layout.addWidget(self.progress_bar)

            # ── Main content area (tabs) ──
            self.tabs = QTabWidget()

            # Tab 1: Dashboard (live sensors)
            self.dashboard = DashboardWidget()
            self.tabs.addTab(self.dashboard, "Dashboard")

            # Tab 2: Table Editor
            self.table_editor = TableEditorWidget()
            self.tabs.addTab(self.table_editor, "Table Editor")

            # Tab 3: Disassembler
            self.disassembler_tab = DisassemblerWidget()
            self.tabs.addTab(self.disassembler_tab, "Disassembler")

            # Tab 4: Log
            self.log_widget = LogWidget()
            self.tabs.addTab(self.log_widget, "Log")

            # Tab 5: Options
            self.options_tab = OptionsWidget(self._config, self._log_cfg)
            self.options_tab.config_changed.connect(self._on_options_changed)
            self.tabs.addTab(self.options_tab, "Options")

            # Tab 6: Custom Flash (sector-level brick recovery)
            self.custom_flash_tab = CustomFlashWidget()
            self.custom_flash_tab.start_custom_write.connect(self._on_custom_write)
            self.custom_flash_tab.start_custom_read.connect(self._on_custom_read)
            self.tabs.addTab(self.custom_flash_tab, "Custom Flash")

            # Tab 7: Chaos Test (automated stress test)
            self.chaos_tab = ChaosTestWidget()
            self.chaos_tab.start_chaos.connect(self._on_start_chaos)
            self.chaos_tab.stop_chaos.connect(self._on_stop_chaos)
            self.tabs.addTab(self.chaos_tab, "Chaos Test")

            # Tab 8: Transport Settings (PySerial / D2XX tuning)
            self.transport_tab = TransportSettingsWidget(self._config)
            self.transport_tab.config_changed.connect(self._on_options_changed)
            self.tabs.addTab(self.transport_tab, "Transport")

            main_layout.addWidget(self.tabs)

            # ── Status bar ──
            self.status_bar = QStatusBar()
            self.setStatusBar(self.status_bar)
            self.state_label = QLabel("DISCONNECTED")
            self.state_label.setStyleSheet("color: #f44; font-weight: bold;")
            self.rate_label = QLabel("")
            self.veeprom_status_label = QLabel("")
            self.veeprom_status_label.setStyleSheet("color: #888;")
            self.status_bar.addWidget(self.state_label)
            self.status_bar.addPermanentWidget(self.veeprom_status_label)
            self.status_bar.addPermanentWidget(self.rate_label)

            # ── Dashboard update timer ──
            self.dash_timer = QTimer()
            self.dash_timer.setInterval(200)
            self.dash_timer.timeout.connect(self._update_dashboard)

        def _build_menu_bar(self) -> None:
            """Build the application menu bar with all actions."""
            menu_bar = self.menuBar()

            # ── File menu ──
            file_menu = menu_bar.addMenu("&File")

            self.action_load = QAction("&Load .bin", self)
            self.action_load.setShortcut("Ctrl+O")
            self.action_load.setStatusTip("Open a .bin or .cal file (16KB cal auto-padded to 128KB)")
            file_menu.addAction(self.action_load)

            self.action_save = QAction("&Save .bin", self)
            self.action_save.setShortcut("Ctrl+S")
            self.action_save.setStatusTip("Save the current bin to disk with checksum auto-fixed")
            self.action_save.setEnabled(False)
            file_menu.addAction(self.action_save)

            self.action_save_as = QAction("Save .bin &As...", self)
            self.action_save_as.setShortcut("Ctrl+Shift+S")
            self.action_save_as.setStatusTip("Save the current bin to a new file")
            self.action_save_as.setEnabled(False)
            file_menu.addAction(self.action_save_as)

            self.action_save_cal = QAction("Save .&cal...", self)
            self.action_save_cal.setStatusTip("Save calibration area ($4000-$7FFF) as .cal file")
            self.action_save_cal.setEnabled(False)
            file_menu.addAction(self.action_save_cal)

            file_menu.addSeparator()

            self.action_exit = QAction("E&xit", self)
            self.action_exit.setShortcut("Alt+F4")
            self.action_exit.setStatusTip("Exit the application")
            self.action_exit.triggered.connect(self.close)
            file_menu.addAction(self.action_exit)

            # ── Connection menu ──
            conn_menu = menu_bar.addMenu("&Connection")

            self.action_connect = QAction("&Connect", self)
            self.action_connect.setShortcut("Ctrl+K")
            self.action_connect.setStatusTip("Connect/disconnect from the ECU")
            conn_menu.addAction(self.action_connect)

            self.action_refresh_ports = QAction("&Refresh Ports", self)
            self.action_refresh_ports.setShortcut("F5")
            self.action_refresh_ports.setStatusTip("Refresh the list of available serial ports")
            conn_menu.addAction(self.action_refresh_ports)

            conn_menu.addSeparator()

            # ── vEEPROM submenu (Virtual ECU flash image management) ──
            self.veeprom_menu = conn_menu.addMenu("v&EEPROM")
            self.veeprom_menu.setStatusTip("Virtual EEPROM management — only available in Virtual ECU mode")

            self.action_veeprom_load = QAction("&Load .bin to vEEPROM...", self)
            self.action_veeprom_load.setShortcut("Ctrl+Shift+L")
            self.action_veeprom_load.setStatusTip(
                "Load a .bin file into the virtual flash image. "
                "If connected to vECU, hot-reloads immediately. If not, stores path for next connect."
            )
            self.veeprom_menu.addAction(self.action_veeprom_load)

            self.action_veeprom_unload = QAction("&Unload vEEPROM", self)
            self.action_veeprom_unload.setShortcut("Ctrl+Shift+U")
            self.action_veeprom_unload.setStatusTip("Clear vEEPROM to all zeros (empty, no data)")
            self.action_veeprom_unload.setEnabled(False)
            self.veeprom_menu.addAction(self.action_veeprom_unload)

            self.action_veeprom_erase = QAction("&Erase vEEPROM", self)
            self.action_veeprom_erase.setShortcut("Ctrl+Shift+E")
            self.action_veeprom_erase.setStatusTip(
                "Erase vEEPROM to all 0xFF — simulates a full chip erase. "
                "Data can be programmed after erase (NOR flash: can only clear bits 1→0)."
            )
            self.action_veeprom_erase.setEnabled(False)
            self.veeprom_menu.addAction(self.action_veeprom_erase)

            self.action_veeprom_export = QAction("E&xport vEEPROM to .bin...", self)
            self.action_veeprom_export.setShortcut("Ctrl+Shift+X")
            self.action_veeprom_export.setStatusTip(
                "Save the current vEEPROM contents to a .bin file — "
                "captures whatever has been written/patched since loading."
            )
            self.action_veeprom_export.setEnabled(False)
            self.veeprom_menu.addAction(self.action_veeprom_export)

            self.veeprom_menu.addSeparator()

            self.action_veeprom_info = QAction("vEEPROM &Info", self)
            self.action_veeprom_info.setStatusTip(
                "Show vEEPROM diagnostics: sectors used/erased, checksum, SHA-256, source file"
            )
            self.action_veeprom_info.setEnabled(False)
            self.veeprom_menu.addAction(self.action_veeprom_info)

            # ── Flash menu ──
            flash_menu = menu_bar.addMenu("F&lash")

            self.action_read_ecu = QAction("&Read ECU", self)
            self.action_read_ecu.setShortcut("Ctrl+R")
            self.action_read_ecu.setStatusTip("Read the full 128KB flash from the ECU (does not modify ECU)")
            self.action_read_ecu.setEnabled(False)
            flash_menu.addAction(self.action_read_ecu)

            flash_menu.addSeparator()

            self.action_write_bin = QAction("Write &BIN (Full)", self)
            self.action_write_bin.setShortcut("Ctrl+W")
            self.action_write_bin.setStatusTip("Write full BIN to ECU — erases sectors 0-6, writes OS + calibration")
            self.action_write_bin.setEnabled(False)
            flash_menu.addAction(self.action_write_bin)

            self.action_write_cal = QAction("Write &CAL (Partial)", self)
            self.action_write_cal.setShortcut("Ctrl+Shift+W")
            self.action_write_cal.setStatusTip("Write calibration only — erases sector 1, writes 16KB cal area")
            self.action_write_cal.setEnabled(False)
            flash_menu.addAction(self.action_write_cal)

            flash_menu.addSeparator()

            self.action_cancel = QAction("C&ancel Operation", self)
            self.action_cancel.setShortcut("Escape")
            self.action_cancel.setStatusTip("Cancel the current flash operation (WARNING: may brick if mid-write!)")
            self.action_cancel.setEnabled(False)
            flash_menu.addAction(self.action_cancel)

            flash_menu.addSeparator()

            # ── Flash option checkboxes ──
            self.action_auto_checksum = QAction("Auto-fix &Checksum Before Write", self)
            self.action_auto_checksum.setCheckable(True)
            self.action_auto_checksum.setChecked(True)
            self.action_auto_checksum.setStatusTip("Automatically fix the bin checksum before writing to ECU")
            self.action_auto_checksum.toggled.connect(self._on_toggle_auto_checksum)
            flash_menu.addAction(self.action_auto_checksum)

            self.action_verify_after_write = QAction("&Verify After Write", self)
            self.action_verify_after_write.setCheckable(True)
            self.action_verify_after_write.setChecked(True)
            self.action_verify_after_write.setStatusTip("Read-back and verify checksum after writing to ECU")
            self.action_verify_after_write.toggled.connect(self._on_toggle_verify_write)
            flash_menu.addAction(self.action_verify_after_write)

            self.action_high_speed_read = QAction("&High-Speed Read", self)
            self.action_high_speed_read.setCheckable(True)
            self.action_high_speed_read.setChecked(False)
            self.action_high_speed_read.setStatusTip(
                "Use high-speed kernel mode for faster flash reads "
                "(patches kernel byte 21 to 0x81 — may not work on all adapters)"
            )
            self.action_high_speed_read.toggled.connect(self._on_toggle_high_speed)
            flash_menu.addAction(self.action_high_speed_read)

            self.action_ignore_echo = QAction("Ignore &Echo", self)
            self.action_ignore_echo.setCheckable(True)
            self.action_ignore_echo.setChecked(True)
            self.action_ignore_echo.setStatusTip(
                "Strip echo bytes from received data (required for most ALDL cables)"
            )
            self.action_ignore_echo.toggled.connect(self._on_toggle_ignore_echo)
            flash_menu.addAction(self.action_ignore_echo)

            # ── Tools menu ──
            tools_menu = menu_bar.addMenu("&Tools")

            self.action_checksum = QAction("Verify/Fix &Checksum", self)
            self.action_checksum.setStatusTip("Verify and auto-fix the bin file checksum")
            self.action_checksum.setEnabled(False)
            tools_menu.addAction(self.action_checksum)

            self.action_ecu_info = QAction("ECU &Info", self)
            self.action_ecu_info.setStatusTip("Read and display ECU sensor data via Mode 1")
            self.action_ecu_info.setEnabled(False)
            tools_menu.addAction(self.action_ecu_info)

            tools_menu.addSeparator()

            self.action_options = QAction("&Options...", self)
            self.action_options.setStatusTip("Configure comm settings, retries, timeouts")
            tools_menu.addAction(self.action_options)

            # ── View menu ──
            view_menu = menu_bar.addMenu("&View")

            self.action_view_dash = QAction("&Dashboard", self)
            self.action_view_dash.setShortcut("Ctrl+1")
            self.action_view_dash.setStatusTip("Switch to the live sensor dashboard tab")
            view_menu.addAction(self.action_view_dash)

            self.action_view_tables = QAction("&Table Editor", self)
            self.action_view_tables.setShortcut("Ctrl+2")
            self.action_view_tables.setStatusTip("Switch to the calibration table editor")
            view_menu.addAction(self.action_view_tables)

            self.action_view_disasm = QAction("&Disassembler", self)
            self.action_view_disasm.setShortcut("Ctrl+3")
            self.action_view_disasm.setStatusTip("Switch to the HC11 hex-to-asm disassembler")
            view_menu.addAction(self.action_view_disasm)

            self.action_view_log = QAction("&Log", self)
            self.action_view_log.setShortcut("Ctrl+4")
            self.action_view_log.setStatusTip("Switch to the log output tab")
            view_menu.addAction(self.action_view_log)

            self.action_view_options = QAction("&Options", self)
            self.action_view_options.setShortcut("Ctrl+5")
            self.action_view_options.setStatusTip("Switch to the settings/options tab")
            view_menu.addAction(self.action_view_options)

            self.action_view_custom_flash = QAction("Custom &Flash", self)
            self.action_view_custom_flash.setShortcut("Ctrl+6")
            self.action_view_custom_flash.setStatusTip("Switch to the custom sector flash tab")
            view_menu.addAction(self.action_view_custom_flash)

            self.action_view_chaos = QAction("C&haos Test", self)
            self.action_view_chaos.setShortcut("Ctrl+7")
            self.action_view_chaos.setStatusTip("Switch to the chaos test tab")
            view_menu.addAction(self.action_view_chaos)

            self.action_view_transport = QAction("&Transport", self)
            self.action_view_transport.setShortcut("Ctrl+8")
            self.action_view_transport.setStatusTip("Switch to the transport settings tab")
            view_menu.addAction(self.action_view_transport)

            # ── Help menu ──
            help_menu = menu_bar.addMenu("&Help")

            self.action_about = QAction("&About", self)
            self.action_about.setStatusTip(f"{__app_name__} v{__version__}")
            help_menu.addAction(self.action_about)

        def _connect_signals(self) -> None:
            # Toolbar buttons
            self.refresh_btn.clicked.connect(self._refresh_ports)
            self.connect_btn.clicked.connect(self._toggle_connect)
            self.load_btn.clicked.connect(self._load_bin)
            self.save_btn.clicked.connect(self._save_bin)
            self.read_btn.clicked.connect(self._read_ecu)
            self.write_btn.clicked.connect(self._write_ecu)
            self.cancel_btn.clicked.connect(self._cancel_op)

            # Menu actions → same handlers as buttons
            self.action_load.triggered.connect(self._load_bin)
            self.action_save.triggered.connect(self._save_bin)
            self.action_save_as.triggered.connect(self._save_bin)
            self.action_save_cal.triggered.connect(self._save_cal)
            self.action_connect.triggered.connect(self._toggle_connect)
            self.action_refresh_ports.triggered.connect(self._refresh_ports)
            self.action_read_ecu.triggered.connect(self._read_ecu)
            self.action_write_bin.triggered.connect(lambda: self._write_ecu_mode("BIN"))
            self.action_write_cal.triggered.connect(lambda: self._write_ecu_mode("CAL"))
            self.action_cancel.triggered.connect(self._cancel_op)
            self.action_checksum.triggered.connect(self._verify_checksum)
            self.action_ecu_info.triggered.connect(self._show_ecu_info)
            self.action_options.triggered.connect(self._show_options)
            self.action_view_dash.triggered.connect(lambda: self.tabs.setCurrentIndex(0))
            self.action_view_tables.triggered.connect(lambda: self.tabs.setCurrentIndex(1))
            self.action_view_disasm.triggered.connect(lambda: self.tabs.setCurrentIndex(2))
            self.action_view_log.triggered.connect(lambda: self.tabs.setCurrentIndex(3))
            self.action_view_options.triggered.connect(lambda: self.tabs.setCurrentIndex(4))
            self.action_view_custom_flash.triggered.connect(lambda: self.tabs.setCurrentIndex(5))
            self.action_view_chaos.triggered.connect(lambda: self.tabs.setCurrentIndex(6))
            self.action_view_transport.triggered.connect(lambda: self.tabs.setCurrentIndex(7))

            # Disassembler event bus → log
            self.disassembler_tab.disassembly_done.connect(
                lambda lines, addr: self.log_widget.append_log(
                    f"Disassembled {len(lines)} instructions from ${addr:04X}", "info"
                )
            )
            self.action_about.triggered.connect(self._show_about)

            # ── vEEPROM menu actions ──
            self.action_veeprom_load.triggered.connect(self._veeprom_load)
            self.action_veeprom_unload.triggered.connect(self._veeprom_unload)
            self.action_veeprom_erase.triggered.connect(self._veeprom_erase)
            self.action_veeprom_export.triggered.connect(self._veeprom_export)
            self.action_veeprom_info.triggered.connect(self._veeprom_info)

        def _refresh_ports(self) -> None:
            self.port_combo.clear()
            transport_type = self.transport_combo.currentData()
            if transport_type in ("loopback", "vecu"):
                label = "(virtual)" if transport_type == "loopback" else "(Virtual ECU)"
                self.port_combo.addItem(label)
                return
            ports = PySerialTransport.list_ports() if SERIAL_AVAILABLE else []
            for p in ports:
                self.port_combo.addItem(p)
            if not ports:
                self.port_combo.addItem("(no ports found)")

        def _on_transport_changed(self, _index: int) -> None:
            """Update port combo and vEEPROM menu when transport type changes."""
            self._refresh_ports()
            self._update_veeprom_menu_state()

        def _toggle_connect(self) -> None:
            if self._comm and self._comm.transport.is_open:
                self._disconnect()
            else:
                self._connect()

        def _connect(self) -> None:
            transport_type = self.transport_combo.currentData()
            port = self.port_combo.currentText()

            if transport_type == "pyserial":
                self._transport = PySerialTransport(port, DEFAULT_BAUD)
            elif transport_type == "d2xx":
                self._transport = D2XXTransport(0, DEFAULT_BAUD)
            elif transport_type == "loopback":
                self._transport = LoopbackTransport()
            elif transport_type == "vecu":
                # Ask for a .bin file to simulate
                bin_path = self._vecu_bin_path
                if not bin_path:
                    bin_path, _ = QFileDialog.getOpenFileName(
                        self, "Select ECU Binary for Virtual ECU", "",
                        "Bin Files (*.bin);;Cal Files (*.cal);;All Files (*)"
                    )
                if not bin_path:
                    self.log_widget.append_log("Virtual ECU: no bin selected", "warning")
                    return
                self._vecu_bin_path = bin_path
                self._transport = LoopbackTransport(bin_path=bin_path)
                self.log_widget.append_log(
                    f"Virtual ECU loaded: {Path(bin_path).name}", "success"
                )
            else:
                return

            self._comm = ECUComm(self._transport, self._config, self._log_cfg)
            self._comm.clear_callbacks()  # fresh comm — ensure no stale listeners
            self._comm.on("log", lambda msg, level="info", **_: self.log_widget.append_log(msg, level))

            if self._comm.connect():
                self.connect_btn.setText("Disconnect")
                self.connect_btn.setStyleSheet("background: #8b1a1a;")
                self.connect_btn.setToolTip("Disconnect from the ECU")
                self.read_btn.setEnabled(True)
                self.write_btn.setEnabled(self._bin_data is not None)
                self._update_state("CONNECTED")
                self._update_menu_state(True)
                self.dash_timer.start()
            else:
                self.log_widget.append_log("Connection failed", "error")

        def _disconnect(self) -> None:
            # ── Safety gate: prevent disconnect during an active WRITE ──
            if self._flash_active and self._flash_task == "write":
                reply = QMessageBox.warning(
                    self, "⚠ WRITE IN PROGRESS — DANGER",
                    "A flash WRITE is active right now.\n\n"
                    "Disconnecting during a write can PERMANENTLY BRICK the PCM.\n"
                    "The ECU will be left in an unrecoverable state — " 
                    "it won't start, it won't respond, it's dead.\n\n"
                    "DO NOT disconnect the ALDL cable.\n"
                    "DO NOT turn off the ignition.\n"
                    "DO NOT touch anything.\n\n"
                    "If you are absolutely certain, click Yes to force disconnect.\n"
                    "Otherwise click No and let the write finish.",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if reply != QMessageBox.Yes:
                    return
                # User forced it — cancel the operation first
                self.log_widget.append_log(
                    "USER FORCED DISCONNECT DURING WRITE — ECU may need bench recovery",
                    "error"
                )
                log.error("User forced disconnect during active write operation")
                if self._comm:
                    self._comm.cancel()

            # ── During a READ, just cancel cleanly — reads don't harm the PCM ──
            if self._flash_active and self._flash_task == "read":
                self.log_widget.append_log("Read cancelled by disconnect", "warning")
                if self._comm:
                    self._comm.cancel()

            self.dash_timer.stop()
            if self._logger and self._logger.running:
                self._logger.stop()
            if self._comm:
                self._comm.disconnect()
            self.connect_btn.setText("Connect")
            self.connect_btn.setStyleSheet("")
            self.connect_btn.setToolTip(
                "Connect to ECU via the selected port.\n"
                "Performs echo detection, silences bus chatter, and identifies the PCM."
            )
            self.read_btn.setEnabled(False)
            self.write_btn.setEnabled(False)
            self._update_state("DISCONNECTED")
            self._update_menu_state(False)

        def _load_bin(self) -> None:
            path, _ = QFileDialog.getOpenFileName(self, "Open Bin File", "",
                                                   "Bin Files (*.bin);;All Files (*)")
            if not path:
                return
            try:
                self._bin_data = BinFile.load(path)
                self._bin_path = path
                fname = Path(path).name
                os_id = BinFile.get_os_id(self._bin_data)
                cs_ok = BinFile.verify_checksum(self._bin_data)
                cs_str = "✓" if cs_ok else "✗ (will auto-fix)"
                self.file_label.setText(f"{fname} | OS:{os_id} | CS:{cs_str}")
                self.file_label.setStyleSheet("color: #4fc3f7;")
                self.save_btn.setEnabled(True)
                if self._comm and self._comm.transport.is_open:
                    self.write_btn.setEnabled(True)
                self._update_menu_state(self._comm is not None and self._comm.transport.is_open if self._comm else False)

                # Load default table into editor
                self.table_editor.load_table("spark_hi_oct", self._bin_data)

                self.log_widget.append_log(f"Loaded: {fname} ({os_id}, checksum {'OK' if cs_ok else 'MISMATCH'})",
                                           "info")
            except Exception as e:
                self.log_widget.append_log(f"Failed to load bin: {e}", "error")

        def _save_bin(self) -> None:
            if not self._bin_data:
                return
            path, _ = QFileDialog.getSaveFileName(self, "Save Bin File",
                                                   self._bin_path or "",
                                                   "Bin Files (*.bin);;All Files (*)")
            if path:
                BinFile.fix_checksum(self._bin_data)
                BinFile.save(path, self._bin_data)
                self.log_widget.append_log(f"Saved: {Path(path).name}", "info")

        def _save_cal(self) -> None:
            """Save calibration data ($4000-$7FFF) as a .cal file."""
            if not self._bin_data:
                return
            default_name = ""
            if self._bin_path:
                default_name = str(Path(self._bin_path).with_suffix(".cal"))
            path, _ = QFileDialog.getSaveFileName(
                self, "Save Calibration File",
                default_name,
                "Cal Files (*.cal);;Bin Files (*.bin);;All Files (*)"
            )
            if not path:
                return

            # Ask padded vs raw
            reply = QMessageBox.question(
                self, "CAL File Format",
                "Pad calibration to 128KB?\n\n"
                "YES = 128KB file with cal at $4000 (TunerPro compatible)\n"
                "NO  = Raw 16KB calibration data only",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,  # default to padded
            )
            padded = (reply == QMessageBox.Yes)
            BinFile.save_cal(path, self._bin_data, padded=padded)
            size_str = "128KB padded" if padded else "16KB raw"
            self.log_widget.append_log(f"Saved cal ({size_str}): {Path(path).name}", "info")

        def _read_ecu(self) -> None:
            if not self._comm:
                return
            self._start_flash_op("read")

        def _write_ecu(self) -> None:
            if not self._comm or not self._bin_data:
                return
            mode = self.write_mode_combo.currentData() or self.write_mode_combo.currentText()
            self._write_ecu_mode(mode)

        def _write_ecu_mode(self, mode: str) -> None:
            """Write with a specific mode, used by both toolbar button and menu actions."""
            if not self._comm or not self._bin_data:
                self.log_widget.append_log("Cannot write: no connection or no bin loaded", "error")
                return

            if mode == "BIN":
                desc = (
                    "FULL BIN WRITE\n\n"
                    "This will ERASE sectors 0-6 and write the entire OS + calibration (104KB).\n\n"
                )
            else:
                desc = (
                    "CAL-ONLY WRITE\n\n"
                    "This will ERASE sector 1 ($4000-$7FFF) and write the 16KB calibration area only.\n"
                    "Cal data is always padded to 128KB automatically.\n\n"
                )

            reply = QMessageBox.warning(
                self, f"⚠ Confirm {mode} Write",
                f"{desc}"
                f"⚠ DO NOT disconnect power or the ALDL cable during this operation!\n"
                f"⚠ A failed write can BRICK the PCM — ensure you have a backup!\n\n"
                f"Proceed with {mode} write?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,  # default to No for safety
            )
            if reply != QMessageBox.Yes:
                return

            self._start_flash_op("write", mode)

        # ── UI lock/unlock helpers (#10 fix — deduplicate) ──────────

        def _lock_ui_for_flash(self, task: str) -> None:
            """Lock the entire UI during a flash operation."""
            self._flash_active = True
            self._flash_task = task

            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("")

            self.cancel_btn.setEnabled(True)
            self.action_cancel.setEnabled(True)
            self.read_btn.setEnabled(False)
            self.write_btn.setEnabled(False)
            self.action_read_ecu.setEnabled(False)
            self.action_write_bin.setEnabled(False)
            self.action_write_cal.setEnabled(False)
            self.options_tab.apply_btn.setEnabled(False)
            self.options_tab.reset_btn.setEnabled(False)

            # Switch to Log tab, disable all others
            log_tab_idx = 3
            self.tabs.setCurrentIndex(log_tab_idx)
            for i in range(self.tabs.count()):
                if i != log_tab_idx:
                    self.tabs.setTabEnabled(i, False)

            # View shortcuts
            self.action_view_dash.setEnabled(False)
            self.action_view_tables.setEnabled(False)
            self.action_view_disasm.setEnabled(False)
            self.action_view_options.setEnabled(False)
            self.action_view_custom_flash.setEnabled(False)
            self.action_view_chaos.setEnabled(False)
            self.action_view_transport.setEnabled(False)

            # Flash-menu toggles
            self.action_auto_checksum.setEnabled(False)
            self.action_verify_after_write.setEnabled(False)
            self.action_high_speed_read.setEnabled(False)
            self.action_ignore_echo.setEnabled(False)

            # File menu
            self.action_load.setEnabled(False)
            self.action_save.setEnabled(False)
            self.action_save_as.setEnabled(False)
            self.action_save_cal.setEnabled(False)
            self.action_checksum.setEnabled(False)
            self.action_ecu_info.setEnabled(False)
            self.load_btn.setEnabled(False)
            self.save_btn.setEnabled(False)

        def _unlock_ui_after_flash(self) -> None:
            """Unlock the UI after a flash operation completes."""
            self._flash_active = False
            self._flash_task = None

            self.cancel_btn.setEnabled(False)
            self.action_cancel.setEnabled(False)
            self.read_btn.setEnabled(True)
            self.write_btn.setEnabled(self._bin_data is not None)
            self._update_menu_state(True)
            self.options_tab.apply_btn.setEnabled(True)
            self.options_tab.reset_btn.setEnabled(True)

            # Unlock all tabs
            for i in range(self.tabs.count()):
                self.tabs.setTabEnabled(i, True)
            self.action_view_dash.setEnabled(True)
            self.action_view_tables.setEnabled(True)
            self.action_view_disasm.setEnabled(True)
            self.action_view_options.setEnabled(True)
            self.action_view_custom_flash.setEnabled(True)
            self.action_view_chaos.setEnabled(True)
            self.action_view_transport.setEnabled(True)

            # Flash-menu toggles
            self.action_auto_checksum.setEnabled(True)
            self.action_verify_after_write.setEnabled(True)
            self.action_high_speed_read.setEnabled(True)
            self.action_ignore_echo.setEnabled(True)

            # File menu
            self.load_btn.setEnabled(True)
            self.save_btn.setEnabled(self._bin_data is not None)
            self.action_load.setEnabled(True)

        def _start_flash_thread(self, worker: 'FlashWorker') -> None:
            """Wire up signals and start the flash worker thread (#8 fix — deleteLater)."""
            self._flash_thread = QThread()
            self._flash_worker = worker

            worker.moveToThread(self._flash_thread)
            self._flash_thread.started.connect(worker.run)
            worker.finished.connect(self._on_flash_finished)
            worker.read_data.connect(self._on_read_data)
            worker.progress.connect(self._on_flash_progress)
            worker.log_message.connect(lambda msg, lvl: self.log_widget.append_log(msg, lvl))
            worker.state_changed.connect(self._update_state)
            worker.finished.connect(self._flash_thread.quit)
            # Clean up Qt objects when thread finishes (#8 fix)
            self._flash_thread.finished.connect(worker.deleteLater)
            self._flash_thread.finished.connect(self._flash_thread.deleteLater)

            self._flash_thread.start()

        def _start_flash_op(self, task: str, mode: str = "BIN") -> None:
            self._lock_ui_for_flash(task)

            worker = FlashWorker(self._comm)
            if task == "write":
                worker.setup_write(self._bin_data, mode)
            else:
                worker.setup_read()

            self._start_flash_thread(worker)

        def _on_read_data(self, data: bytearray) -> None:
            """Store read-back data so the user can save it."""
            self._bin_data = data
            os_id = BinFile.get_os_id(data)
            cs_ok = BinFile.verify_checksum(data)
            cs_str = "\u2713" if cs_ok else "\u2717"
            self.file_label.setText(f"Read from ECU | OS:{os_id} | CS:{cs_str}")
            self.file_label.setStyleSheet("color: #4fc3f7;")
            self.save_btn.setEnabled(True)
            self.log_widget.append_log(
                f"Read data stored: {len(data)} bytes, OS={os_id}, "
                f"checksum {'OK' if cs_ok else 'MISMATCH'}",
                "info",
            )

        def _on_flash_finished(self, success: bool) -> None:
            self._unlock_ui_after_flash()
            self.progress_bar.setValue(100 if success else 0)

            if success:
                self.log_widget.append_log("Operation completed successfully!", "success")
            else:
                self.log_widget.append_log("Operation failed!", "error")

            # Reset chaos tab buttons if chaos test just finished
            self.chaos_tab.btn_start.setEnabled(True)
            self.chaos_tab.btn_stop.setEnabled(False)

        def _on_flash_progress(self, current: int, total: int, label: str) -> None:
            if total > 0:
                pct = int((current / total) * 100)
                self.progress_bar.setValue(pct)
                self.progress_bar.setFormat(f"{label} — {pct}%")

        def _cancel_op(self) -> None:
            if self._comm:
                self._comm.cancel()

        def _update_state(self, state_name: str) -> None:
            self.state_label.setText(state_name)
            colors = {
                "DISCONNECTED": "#f44",
                "CONNECTED": "#4fc3f7",
                "SILENCED": "#ff9800",
                "UNLOCKED": "#ffeb3b",
                "PROGRAMMING": "#ff5722",
                "KERNEL_LOADED": "#e040fb",
                "FLASHING": "#f44336",
                "DATALOG": "#4caf50",
                "LIVE_TUNE": "#76ff03",
                "ERROR": "#ff0000",
            }
            self.state_label.setStyleSheet(f"color: {colors.get(state_name, '#888')}; font-weight: bold;")

        def _update_dashboard(self) -> None:
            if self._logger and self._logger.latest:
                self.dashboard.update_data(self._logger.latest)
                self.rate_label.setText(f"{self._logger.sample_rate:.1f} Hz")

        def _verify_checksum(self) -> None:
            """Verify and optionally fix the loaded bin's checksum."""
            if not self._bin_data:
                self.log_widget.append_log("No bin loaded to verify", "warning")
                return
            ok = BinFile.verify_checksum(self._bin_data)
            if ok:
                self.log_widget.append_log("Checksum OK — no fix needed", "success")
            else:
                old, new = BinFile.fix_checksum(self._bin_data)
                self.log_widget.append_log(
                    f"Checksum fixed: 0x{old:04X} → 0x{new:04X}", "warning"
                )

        def _show_ecu_info(self) -> None:
            """Read and display ECU info via Mode 1."""
            if not self._comm:
                return
            self.log_widget.append_log("Reading ECU info...", "info")
            data = self._comm.request_mode1(message=0)
            if not data:
                self.log_widget.append_log("ECU info: no response from PCM", "error")
                return

            # Build info string from the returned parameter dict
            lines = []
            key_params = [
                "RPM", "ECT Temp", "IAT Temp", "TPS %", "MAF",
                "Spark Advance", "Battery V", "IAC Steps", "Run Time",
            ]
            for name in key_params:
                if name in data:
                    lines.append(f"  {name}: {data[name]}")

            info_text = "\n".join(lines) if lines else "  (no parameters decoded)"
            self.log_widget.append_log(f"ECU Info:\n{info_text}", "info")

            QMessageBox.information(
                self, "ECU Info (Mode 1)",
                f"<pre>{info_text}</pre>",
            )

        def _show_options(self) -> None:
            """Switch to the Options tab."""
            self.tabs.setCurrentIndex(4)  # Options tab

        def _on_options_changed(self) -> None:
            """Called when options tab values change."""
            self.options_tab.apply_to_config(self._config)
            self.options_tab.apply_log_config(self._log_cfg)
            # Push updated log_cfg into the live ECUComm if connected
            if self._comm:
                self._comm.log_cfg = self._log_cfg
            self._persist_on_close = self.options_tab.chk_persist_on_close.isChecked()
            self.log_widget.append_log("Options updated", "info")

        # ── Custom Flash handlers ──

        def _on_custom_write(self, sectors: list) -> None:
            """Handle custom sector write from CustomFlashWidget."""
            if not self._comm:
                QMessageBox.warning(self, "Not Connected", "Connect to an ECU first.")
                return
            if self._bin_data is None:
                QMessageBox.warning(self, "No Bin Loaded", "Load a .bin file first.")
                return
            if self._flash_active:
                QMessageBox.warning(self, "Busy", "A flash operation is already running.")
                return

            sector_desc = ", ".join(str(s) for s in sectors)
            self.log_widget.append_log(f"Custom write: sectors [{sector_desc}]", "info")
            self._start_custom_flash_op("custom_write", sectors=sectors)

        def _on_custom_read(self, start_addr: int, end_addr: int) -> None:
            """Handle custom address range read from CustomFlashWidget."""
            if not self._comm:
                QMessageBox.warning(self, "Not Connected", "Connect to an ECU first.")
                return
            if self._flash_active:
                QMessageBox.warning(self, "Busy", "A flash operation is already running.")
                return

            self.log_widget.append_log(
                f"Custom read: ${start_addr:05X}-${end_addr:05X}", "info"
            )
            self._start_custom_flash_op("custom_read", start_addr=start_addr, end_addr=end_addr)

        def _on_start_chaos(self, config: dict) -> None:
            """Handle chaos test start from ChaosTestWidget."""
            if not self._comm:
                QMessageBox.warning(self, "Not Connected", "Connect to an ECU first.")
                return
            if self._bin_data is None:
                QMessageBox.warning(self, "No Bin Loaded", "Load a .bin file first.")
                return
            if self._flash_active:
                QMessageBox.warning(self, "Busy", "A flash operation is already running.")
                return

            self.log_widget.append_log(
                f"Chaos test started: {config.get('cycles', 0)} cycles, mode={config.get('mode', 'BIN')}",
                "warning"
            )
            self._start_custom_flash_op("chaos", chaos_cfg=config)

        def _on_stop_chaos(self) -> None:
            """Handle chaos test stop request."""
            if self._comm:
                self._comm.cancel()
                self.log_widget.append_log("Chaos test cancel requested", "warning")

        def _start_custom_flash_op(self, task: str, sectors: list = None,
                                    start_addr: int = 0, end_addr: int = 0,
                                    chaos_cfg: dict = None) -> None:
            """Start a custom flash operation (custom write/read or chaos test)."""
            self._lock_ui_for_flash(task)

            worker = FlashWorker(self._comm)
            if task == "custom_write":
                worker.setup_custom_write(self._bin_data, sectors)
            elif task == "custom_read":
                worker.setup_custom_read(start_addr, end_addr)
            elif task == "chaos":
                worker.setup_chaos(chaos_cfg, self._bin_data)

            self._start_flash_thread(worker)

        def _on_toggle_auto_checksum(self, checked: bool) -> None:
            self._config.auto_checksum_fix = checked
            self.log_widget.append_log(
                f"Auto-fix checksum: {'ON' if checked else 'OFF'}", "info"
            )

        def _on_toggle_verify_write(self, checked: bool) -> None:
            self._verify_after_write = checked
            self.log_widget.append_log(
                f"Verify after write: {'ON' if checked else 'OFF'}", "info"
            )

        def _on_toggle_high_speed(self, checked: bool) -> None:
            self._config.high_speed_read = checked
            self.log_widget.append_log(
                f"High-speed read: {'ON' if checked else 'OFF'}", "info"
            )

        def _on_toggle_ignore_echo(self, checked: bool) -> None:
            self._config.ignore_echo = checked
            self.log_widget.append_log(
                f"Ignore echo: {'ON' if checked else 'OFF'}", "info"
            )

        def _show_about(self) -> None:
            """Show the about dialog."""
            QMessageBox.about(
                self,
                f"About {__app_name__}",
                f"<h3>{__app_name__} v{__version__}</h3>"
                f"<p>VY V6 In-Car Flash Tool</p>"
                f"<p>Target: {__target_ecm__}</p>"
                f"<p>Python reimplementation of OSE Enhanced Flash Tool V1.5.1</p>"
                f"<p>&copy; 2026 Jason King (pcmhacking.net: kingaustraliagg)</p>"
                f"<p>MIT License</p>"
            )

        def _update_menu_state(self, connected: bool) -> None:
            """Sync menu action enabled state with connection status."""
            self.action_read_ecu.setEnabled(connected)
            has_bin = self._bin_data is not None
            self.action_write_bin.setEnabled(connected and has_bin)
            self.action_write_cal.setEnabled(connected and has_bin)
            self.action_save.setEnabled(has_bin)
            self.action_save_as.setEnabled(has_bin)
            self.action_save_cal.setEnabled(has_bin)
            self.action_checksum.setEnabled(has_bin)
            self.action_ecu_info.setEnabled(connected)
            self._update_veeprom_menu_state()

        def _update_veeprom_menu_state(self) -> None:
            """Enable/disable vEEPROM menu items based on transport mode and connection state."""
            is_vecu = (self.transport_combo.currentData() == "vecu")
            is_connected_vecu = (
                is_vecu and self._comm is not None
                and self._comm.transport.is_open
                and isinstance(self._comm.transport, LoopbackTransport)
            )
            has_flash = (
                is_connected_vecu
                and hasattr(self._comm.transport, '_simulated_bin')
                and not all(b == 0x00 for b in self._comm.transport._simulated_bin[:256])
            )

            # "Load .bin to vEEPROM" — always enabled when in vECU mode (can pre-load before connect)
            self.action_veeprom_load.setEnabled(is_vecu)

            # These require an active vECU connection with data loaded
            self.action_veeprom_unload.setEnabled(is_connected_vecu and has_flash)
            self.action_veeprom_erase.setEnabled(is_connected_vecu and has_flash)
            self.action_veeprom_export.setEnabled(is_connected_vecu and has_flash)
            self.action_veeprom_info.setEnabled(is_connected_vecu)

            # Grey out entire submenu when not in vECU mode
            self.veeprom_menu.setEnabled(is_vecu)
            if not is_vecu:
                self.veeprom_menu.setToolTip("vEEPROM is only available in Virtual ECU mode")
                self.veeprom_status_label.setText("")
            else:
                self.veeprom_menu.setToolTip("")
                # Update status bar label
                if is_connected_vecu and has_flash:
                    src = Path(self._vecu_bin_path).name if self._vecu_bin_path else "unknown"
                    self.veeprom_status_label.setText(f"vEEPROM: loaded ({src})")
                    self.veeprom_status_label.setStyleSheet("color: #4f4;")
                elif is_connected_vecu:
                    # Connected but flash is empty/erased
                    transport = self._comm.transport
                    if all(b == 0xFF for b in transport._simulated_bin[:256]):
                        self.veeprom_status_label.setText("vEEPROM: erased")
                        self.veeprom_status_label.setStyleSheet("color: #ff4;")
                    else:
                        self.veeprom_status_label.setText("vEEPROM: empty")
                        self.veeprom_status_label.setStyleSheet("color: #888;")
                elif self._vecu_bin_path:
                    fname = Path(self._vecu_bin_path).name
                    self.veeprom_status_label.setText(f"vEEPROM: queued ({fname})")
                    self.veeprom_status_label.setStyleSheet("color: #88f;")
                else:
                    self.veeprom_status_label.setText("vEEPROM: not loaded")
                    self.veeprom_status_label.setStyleSheet("color: #888;")

        # ── vEEPROM Handlers ──────────────────────────────────────────

        def _veeprom_load(self) -> None:
            """Load a .bin file into the virtual flash image."""
            path, _ = QFileDialog.getOpenFileName(
                self, "Load .bin to vEEPROM", "",
                "Bin Files (*.bin);;Cal Files (*.cal);;All Files (*)"
            )
            if not path:
                return

            try:
                raw = Path(path).read_bytes()
            except Exception as e:
                self.log_widget.append_log(f"vEEPROM load failed: {e}", "error")
                return

            fname = Path(path).name

            # If connected to vECU, hot-reload into the transport
            if (self._comm and self._comm.transport.is_open
                    and isinstance(self._comm.transport, LoopbackTransport)):
                if self._comm.transport.load_flash(bytearray(raw)):
                    self._vecu_bin_path = path
                    self.log_widget.append_log(
                        f"vEEPROM: hot-loaded {fname} ({len(raw)} bytes)", "success"
                    )
                else:
                    self.log_widget.append_log(
                        f"vEEPROM: invalid size {len(raw)} — expected 128KB or 16KB", "error"
                    )
                    return
            else:
                # Not connected yet — store path for next vECU connect
                self._vecu_bin_path = path
                self.log_widget.append_log(
                    f"vEEPROM: queued {fname} for next Virtual ECU connect", "info"
                )

            self._update_veeprom_menu_state()

        def _veeprom_unload(self) -> None:
            """Clear vEEPROM to all zeros."""
            if not (self._comm and isinstance(self._comm.transport, LoopbackTransport)):
                return
            self._comm.transport.reset_flash()
            self.log_widget.append_log("vEEPROM: unloaded — all zeros", "info")
            self._update_veeprom_menu_state()

        def _veeprom_erase(self) -> None:
            """Erase vEEPROM to all 0xFF (simulates full chip erase)."""
            if not (self._comm and isinstance(self._comm.transport, LoopbackTransport)):
                return
            self._comm.transport.erase_flash()
            self.log_widget.append_log("vEEPROM: erased — all 0xFF", "info")
            self._update_veeprom_menu_state()

        def _veeprom_export(self) -> None:
            """Export current vEEPROM contents to a .bin file."""
            if not (self._comm and isinstance(self._comm.transport, LoopbackTransport)):
                return
            path, _ = QFileDialog.getSaveFileName(
                self, "Export vEEPROM to .bin", "veeprom_export.bin",
                "Bin Files (*.bin);;All Files (*)"
            )
            if not path:
                return
            try:
                flash_data = self._comm.transport.export_flash()
                Path(path).write_bytes(flash_data)
                self.log_widget.append_log(
                    f"vEEPROM: exported {len(flash_data)} bytes to {Path(path).name}", "success"
                )
            except Exception as e:
                self.log_widget.append_log(f"vEEPROM export failed: {e}", "error")

        def _veeprom_info(self) -> None:
            """Show vEEPROM diagnostic info dialog."""
            if not (self._comm and isinstance(self._comm.transport, LoopbackTransport)):
                return
            info = self._comm.transport.flash_info()
            sector_lines = []
            for idx in range(8):
                status = info["sectors"].get(idx, "unknown")
                icon = {"used": "█", "erased": "░", "empty": "○"}.get(status, "?")
                sector_lines.append(f"  Sector {idx}: {icon} {status}")

            cs_match = "✓ MATCH" if info["checksum"] == info["stored_checksum"] else "✗ MISMATCH"
            msg = (
                f"<pre>"
                f"vEEPROM Flash Info\n"
                f"{'─' * 40}\n"
                f"Size:            {info['size']:,} bytes ({info['size'] // 1024} KB)\n"
                f"Source:          {info['source_file'] or '(none)'}\n"
                f"Sectors used:    {info['sectors_used']} / 8\n"
                f"Sectors erased:  {info['sectors_erased']} / 8\n"
                f"\n"
                f"{''.join(chr(10).join(sector_lines))}\n"
                f"\n"
                f"Computed checksum: ${info['checksum']:04X}\n"
                f"Stored checksum:   ${info['stored_checksum']:04X}  {cs_match}\n"
                f"SHA-256: {info['sha256'][:32]}...\n"
                f"</pre>"
            )
            QMessageBox.information(self, "vEEPROM Info", msg)

        def closeEvent(self, event) -> None:
            # ── Block window close during an active WRITE ──
            if self._flash_active and self._flash_task == "write":
                QMessageBox.critical(
                    self, "⚠ CANNOT CLOSE — WRITE IN PROGRESS",
                    "A flash WRITE is active.\n\n"
                    "Closing the application now will BRICK the PCM.\n"
                    "Wait for the write to finish or use Cancel first.",
                )
                event.ignore()
                return

            # During a read, warn but allow close
            if self._flash_active and self._flash_task == "read":
                if self._comm:
                    self._comm.cancel()
                self.log_widget.append_log("Read cancelled by window close", "warning")

            if self._logger and self._logger.running:
                self._logger.stop()
            if self._comm and self._comm.transport.is_open:
                self._comm.disconnect()
            # Persist settings to disk if enabled
            if self._persist_on_close:
                self.options_tab.apply_to_config(self._config)
                self.options_tab.apply_log_config(self._log_cfg)
                SettingsManager.save(self._config, self._log_cfg)
                log.info("Settings saved on exit")
            event.accept()


# ═══════════════════════════════════════════════════════════════════════
# SECTION 13 — CLI INTERFACE
# ═══════════════════════════════════════════════════════════════════════

def cli_log_callback(msg: str, level: str = "info", **kwargs) -> None:
    """Print log messages to console."""
    prefix = {"info": "  ", "warning": "⚠ ", "error": "✗ ", "success": "✓ ", "debug": "  "}
    print(f"{prefix.get(level, '  ')}{msg}")

def cli_progress_callback(current: int, total: int, label: str = "", **kwargs) -> None:
    """Print progress to console."""
    if total > 0:
        pct = (current / total) * 100
        bar_len = 40
        filled = int(bar_len * current / total)
        bar = "█" * filled + "░" * (bar_len - filled)
        print(f"\r  {label} [{bar}] {pct:.0f}%", end="", flush=True)
        if current >= total:
            print()

def run_cli(args: argparse.Namespace) -> int:
    """Run the CLI interface."""
    print(f"\n{__app_name__} v{__version__}")
    print(f"Target: {__target_ecm__}\n")

    # Create transport
    if args.transport == "loopback":
        transport = LoopbackTransport()
    elif args.transport == "vecu":
        bin_file = getattr(args, 'vecu_bin', None) or getattr(args, 'input', None)
        if not bin_file:
            print("ERROR: --transport vecu requires --vecu-bin <path> to load into the virtual ECU")
            return 1
        transport = LoopbackTransport(bin_path=bin_file)
    elif args.transport == "d2xx":
        transport = D2XXTransport(args.device_index or 0, args.baud)
    else:
        transport = PySerialTransport(args.port, args.baud)

    config = CommConfig(
        device_id=int(args.device_id, 16) if args.device_id else DeviceID.VX_VY_F7,
        baud=args.baud,
        timeout_ms=args.timeout,
        max_retries=args.retries,
        write_chunk_size=args.chunk_size,
        high_speed_read=args.high_speed,
        ignore_echo=getattr(args, 'ignore_echo', True),
        inter_frame_delay_ms=getattr(args, 'inter_frame_delay', DEFAULT_INTER_FRAME_DELAY_MS),
        auto_checksum_fix=getattr(args, 'auto_checksum', True),
    )

    comm = ECUComm(transport, config)
    comm.on("log", cli_log_callback)
    comm.on("progress", cli_progress_callback)

    # Connect
    print(f"Connecting...")
    if not comm.connect():
        print("✗ Connection failed")
        return 1

    try:
        if args.command == "read":
            flash_op = FlashOp(comm)
            data = flash_op.full_read()
            if data:
                ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                if args.cal:
                    # Raw 16KB cal
                    out_path = args.output or f"cal_raw_{ts}.cal"
                    BinFile.save_cal(out_path, data, padded=False)
                    print(f"\n✓ Saved raw 16KB cal to {out_path} ({BinFile.CAL_SIZE} bytes)")
                elif args.cal_padded:
                    # Padded 128KB with only cal
                    out_path = args.output or f"cal_padded_{ts}.bin"
                    BinFile.save_cal(out_path, data, padded=True)
                    print(f"\n✓ Saved padded cal to {out_path} ({BinFile.BIN_SIZE} bytes)")
                else:
                    # Full 128KB bin
                    out_path = args.output or f"read_{ts}.bin"
                    BinFile.save(out_path, data)
                    print(f"\n✓ Saved full bin to {out_path} ({BinFile.BIN_SIZE} bytes)")
                return 0
            else:
                print("\n✗ Read failed")
                return 1

        elif args.command == "write":
            if not args.input:
                print("✗ No input file specified (use --input)")
                return 1
            bin_data = BinFile.load(args.input)

            # Checksum fix
            if not BinFile.verify_checksum(bin_data):
                old, new = BinFile.fix_checksum(bin_data)
                print(f"  Auto-fixed checksum: 0x{old:04X} → 0x{new:04X}")

            flash_op = FlashOp(comm)
            mode = args.write_mode or "BIN"
            success = flash_op.full_write(bin_data, mode)
            return 0 if success else 1

        elif args.command == "datalog":
            logger = DataLogger(comm)
            csv_path = args.output or None
            params = args.params.split(",") if args.params else None

            print("Starting datalog (Ctrl+C to stop)...")
            if not comm.disable_chatter():
                print("  Warning: chatter disable failed, logging may be noisy")

            logger.on_data = lambda d: print(
                f"\r  RPM={d.get('RPM', 0):5.0f}  ECT={d.get('ECT Temp', 0):5.1f}°C  "
                f"SPK={d.get('Spark Advance', 0):5.1f}°  KNK={d.get('Knock Retard', 0):4.1f}°  "
                f"AFR={d.get('AFR', 0):4.1f}  TPS={d.get('TPS %', 0):4.1f}%",
                end="", flush=True
            )
            logger.start(csv_path, params)

            try:
                while logger.running:
                    time.sleep(0.5)
            except KeyboardInterrupt:
                print("\n\nStopping...")
                logger.stop()

            comm.enable_chatter()
            return 0

        elif args.command == "info":
            # Read ECU info
            if not comm.disable_chatter():
                return 1
            data = comm.request_mode1(message=0)
            if data:
                print("\nECU Sensor Data:")
                for name, value in sorted(data.items()):
                    param = PARAM_BY_NAME.get(name)
                    units = param.units if param else ""
                    print(f"  {name:20s} = {value:>10.2f} {units}")
            comm.enable_chatter()
            return 0

        elif args.command == "checksum":
            if not args.input:
                print("✗ No input file specified")
                return 1
            bin_data = BinFile.load(args.input)
            stored = (bin_data[CHECKSUM_OFFSET_HI] << 8) | bin_data[CHECKSUM_OFFSET_LO]
            computed = BinFile.compute_checksum(bin_data)
            os_id = BinFile.get_os_id(bin_data)
            print(f"  File:     {args.input}")
            print(f"  OS ID:    {os_id}")
            print(f"  Stored:   0x{stored:04X}")
            print(f"  Computed: 0x{computed:04X}")
            print(f"  Status:   {'✓ MATCH' if stored == computed else '✗ MISMATCH'}")
            if stored != computed and args.fix:
                BinFile.fix_checksum(bin_data)
                BinFile.save(args.input, bin_data)
                print(f"  Fixed:    0x{stored:04X} → 0x{computed:04X}")
            return 0

        elif args.command == "ports":
            ports = PySerialTransport.list_ports()
            if ports:
                print("Available ports:")
                for p in ports:
                    print(f"  {p}")
            else:
                print("No serial ports found")
            return 0

        else:
            print(f"Unknown command: {args.command}")
            return 1

    except KeyboardInterrupt:
        print("\n\nCancelled by user")
        comm.cancel()
        return 130
    except Exception as e:
        print(f"\n✗ Error: {e}")
        log.exception("CLI error")
        return 1
    finally:
        comm.disconnect()


# ═══════════════════════════════════════════════════════════════════════
# SECTION 14 — ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kingai_commie_flasher",
        description=f"{__app_name__} v{__version__} — VY V6 ECU Flash/Read/Datalog/Tune Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s gui                                    # Launch GUI
  %(prog)s read --port COM3 --output read.bin     # Read ECU to file
  %(prog)s write --port COM3 --input tune.bin     # Write bin to ECU
  %(prog)s write --port COM3 --input tune.bin --mode CAL   # Cal-only write
  %(prog)s datalog --port COM3                     # Live datalog to CSV
  %(prog)s info --port COM3                        # Show ECU sensor values
  %(prog)s checksum --input file.bin               # Verify/fix checksum
  %(prog)s ports                                   # List serial ports
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # GUI
    subparsers.add_parser("gui", help="Launch GUI interface")

    # Read
    read_p = subparsers.add_parser("read", help="Read full bin from ECU")
    read_p.add_argument("--output", "-o", help="Output .bin file path")
    read_p.add_argument("--cal", action="store_true", help="Save only the 16KB cal region (raw, unpadded)")
    read_p.add_argument("--cal-padded", action="store_true", help="Save 128KB file with only the cal region (zeros elsewhere)")

    # Write
    write_p = subparsers.add_parser("write", help="Write bin to ECU")
    write_p.add_argument("--input", "-i", required=True, help="Input .bin file path")
    write_p.add_argument("--mode", dest="write_mode", choices=["BIN", "CAL", "PROM"],
                         default="BIN", help="Write mode: BIN=full, CAL=cal only, PROM=full recovery (default: BIN)")
    write_p.add_argument("--auto-checksum", action="store_true", default=True,
                         help="Auto-fix checksum before writing (default: on)")
    write_p.add_argument("--no-auto-checksum", dest="auto_checksum", action="store_false",
                         help="Do NOT auto-fix checksum before writing")
    write_p.add_argument("--verify", dest="verify_after_write", action="store_true", default=True,
                         help="Verify checksum after write (default: on)")
    write_p.add_argument("--no-verify", dest="verify_after_write", action="store_false",
                         help="Skip post-write verification")

    # Datalog
    datalog_p = subparsers.add_parser("datalog", help="Live data stream logging")
    datalog_p.add_argument("--output", "-o", help="CSV output path")
    datalog_p.add_argument("--params", help="Comma-separated parameter list")

    # Checksum
    cs_p = subparsers.add_parser("checksum", help="Verify or fix bin checksum")
    cs_p.add_argument("--input", "-i", required=True, help="Bin file to check")
    cs_p.add_argument("--fix", action="store_true", help="Fix checksum if mismatched")

    # Ports
    subparsers.add_parser("ports", help="List available serial ports")

    # Info
    info_p = subparsers.add_parser("info", help="Show ECU sensor info")

    # Global options
    for sub in [read_p, write_p, datalog_p, info_p]:
        sub.add_argument("--port", "-p", default="COM3", help="Serial port (default: COM3)")
        sub.add_argument("--baud", type=int, default=DEFAULT_BAUD, help=f"Baud rate (default: {DEFAULT_BAUD})")
        sub.add_argument("--transport", choices=["pyserial", "d2xx", "loopback", "vecu"],
                         default="pyserial", help="Transport type (vecu = virtual ECU from --vecu-bin)")
        sub.add_argument("--vecu-bin", help="Path to .bin file to load into the virtual ECU (required for --transport vecu)")
        sub.add_argument("--device-id", default="F7", help="ALDL device ID hex (default: F7)")
        sub.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_MS, help="Timeout in ms")
        sub.add_argument("--retries", type=int, default=DEFAULT_MAX_RETRIES, help="Max retries")
        sub.add_argument("--chunk-size", type=int, default=DEFAULT_WRITE_CHUNK_SIZE, help="Write chunk size")
        sub.add_argument("--high-speed", action="store_true", help="Use high-speed read mode")
        sub.add_argument("--ignore-echo", action="store_true", default=True,
                         help="Strip echo bytes (default: on, needed for most ALDL cables)")
        sub.add_argument("--no-ignore-echo", dest="ignore_echo", action="store_false",
                         help="Do not strip echo bytes")
        sub.add_argument("--inter-frame-delay", type=int, default=DEFAULT_INTER_FRAME_DELAY_MS,
                         help=f"Inter-frame delay in ms (default: {DEFAULT_INTER_FRAME_DELAY_MS})")
        sub.add_argument("--device-index", type=int, help="FTDI device index (for D2XX)")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        # Default to GUI if available, else show help
        if GUI_AVAILABLE:
            args.command = "gui"
        else:
            parser.print_help()
            return 0

    if args.command == "gui":
        if not GUI_AVAILABLE:
            print(f"ERROR: PySide6 failed to load.")
            print(f"  Python: {sys.executable}")
            print(f"  Error:  {_GUI_IMPORT_ERROR}")
            print(f"")
            print(f"  Fix: use the same python that has PySide6 installed:")
            print(f"    python kingai_commie_flasher.py gui")
            print(f"  Or install PySide6 for this interpreter:")
            print(f"    {sys.executable} -m pip install PySide6")
            return 1
        app = QApplication(sys.argv)
        app.setApplicationName(__app_name__)
        window = MainWindow()
        window.show()
        return app.exec()
    else:
        return run_cli(args)


if __name__ == "__main__":
    sys.exit(main())
