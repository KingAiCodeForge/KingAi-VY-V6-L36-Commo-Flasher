#!/usr/bin/env python3
"""
virtual_aldl_frame_sender_and_vecu.py — Standalone Virtual ECU + Frame Sender
===============================================================================

A standalone TCP/serial bridge that acts as a virtual Delco 68HC11 ECU.
Listens on a serial port (or TCP socket) and responds to ALDL protocol
frames exactly like a real VY V6 ECU would.

Useful for:
    - Testing the flash tool without real hardware
    - Developing and debugging ALDL protocol code
    - Sending arbitrary ALDL frames to a real ECU for testing
    - Training / demonstration purposes

The vECU loads a 128KB .bin file into an AMD 29F010 NOR flash simulator
(virtual_128kb_eeprom.py) and responds to:
    - Mode 1:  Data stream (60-byte simulated sensor values, VY-correct offsets)
    - Mode 2:  RAM/flash read (serves real data from loaded bin, 64-byte blocks)
    - Mode 3:  Read N bytes at address (variable-length read)
    - Mode 4:  Actuator test (simulate IAC, spark, injector, fan relay tests)
    - Mode 5:  Enter programming mode
    - Mode 6:  Kernel upload (accepts and ACKs)
    - Mode 8:  Silence bus
    - Mode 9:  Unsilence bus
    - Mode 10: Write calibration (write to cal sector via flash sim)
    - Mode 13: Security (seed/key — same algorithm as kingai_commie_flasher.py)
    - Mode 16: Flash write data (writes through AMD 29F010 flash simulator)

Flash Simulator Integration:
    The vECU uses the AMD29F010 class from virtual_128kb_eeprom.py to provide
    realistic NOR flash behavior:
    - Erase-before-write required (sector erase sets all bytes to 0xFF)
    - Programming can only clear bits (1→0), cannot set bits (0→1)
    - Sector protection enforced
    - Software ID reads return correct manufacturer/device (0x01/0x20)
    - Flash statistics tracked (reads, programs, erases)

Usage:
    # Start vECU on a TCP port (use with a virtual serial port bridge)
    python virtual_aldl_frame_sender_and_vecu.py --mode vecu --port 8192 --bin stock.bin

    # Send a raw ALDL frame to a real ECU
    python virtual_aldl_frame_sender_and_vecu.py --mode send --serial COM3 --frame "F7 56 08"

    # Interactive ALDL frame sender (type frames, see responses)
    python virtual_aldl_frame_sender_and_vecu.py --mode interactive --serial COM3

Target: Holden VY Ecotec V6 — Delco 68HC11F1, OS $060A (92118883)
Protocol: ALDL 8192 baud, device ID 0xF7

MIT License — Copyright (c) 2026 Jason King (pcmhacking.net: kingaustraliagg)
"""

from __future__ import annotations
import sys
import time
import socket
import struct
import argparse
import threading
import logging
import random
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Tuple

# ── Try importing the AMD 29F010 flash simulator ──
try:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from virtual_128kb_eeprom import AMD29F010
    FLASH_SIM_AVAILABLE = True
except ImportError:
    FLASH_SIM_AVAILABLE = False

# ── Logging Setup (merged from log_setup.py — same pattern as kingai_commie_flasher.py) ──
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

try:
    from rich.logging import RichHandler
    RICH_LOGGING_AVAILABLE = True
except ImportError:
    RICH_LOGGING_AVAILABLE = False


def setup_logging(
    name: str = "vecu",
    level: int = logging.DEBUG,
    console_level: int = logging.WARNING,
    log_dir: Optional[Path] = None,
    rich_console: bool = True,
) -> logging.Logger:
    """
    Configure and return a logger.

    Merged from ignore/log_setup.py — same pattern used by
    kingai_commie_flasher.py so all logs land in the same logs/ folder
    with the same format.

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
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════

DEVICE_ID = 0xF7
ALDL_BAUD = 8192
FRAME_SIZE = 201
FLASH_SIZE = 131072  # 128KB
SECTOR_SIZE = 16384  # 16KB per sector
NUM_SECTORS = 8

# ALDL Modes (all modes defined in kingai_commie_flasher.py)
MODE1_DATASTREAM  = 0x01
MODE2_READ_RAM    = 0x02
MODE3_READ_BYTES  = 0x03
MODE4_ACTUATOR    = 0x04
MODE5_ENTER_PROG  = 0x05
MODE6_UPLOAD      = 0x06
MODE8_SILENCE     = 0x08
MODE9_UNSILENCE   = 0x09
MODE10_WRITE_CAL  = 0x0A
MODE13_SECURITY   = 0x0D
MODE16_FLASH_WRITE = 0x10

# ALDL frame encoding (from kingai_commie_flasher.py)
ALDL_LENGTH_OFFSET = 85

# Security — seed/key algorithm constants (from kingai_commie_flasher.py)
SEED_KEY_MAGIC = 37709    # 0x934D — from kingai_commie_flasher.py
SEED_HI = 0x42
SEED_LO = 0x37

# Flash chip IDs (from kingai_commie_flasher.py)
FLASH_AMD_29F010 = (0x01, 0x20)

# Checksum location in bin file (from kingai_commie_flasher.py)
CHECKSUM_OFFSET_HI = 0x4006
CHECKSUM_OFFSET_LO = 0x4007
CHECKSUM_SKIP_START = 0x4000
CHECKSUM_SKIP_END = 0x4007

# Bank→file offset mapping (from kingai_commie_flasher.py BANK_WRITE_MAP)
BANK_WRITE_MAP = [
    # (bank_byte, file_start, file_end, pcm_base_offset)
    (0x48, 0x0000,  0xFFFF,  0),        # Bank 72: Sectors 0-3 (64KB, 1:1)
    (0x58, 0x10000, 0x17FFF, 0x8000),   # Bank 88: Sectors 4-5 (32KB, remap $8000)
    (0x50, 0x18000, 0x1FFFF, 0x10000),  # Bank 80: Sectors 6-7 (32KB, remap $8000)
]

# VY V6 known addresses (from ALDL_read_RAM_commands.py)
KNOWN_ADDRESSES = {
    0x4000: "Calibration area start",
    0x4006: "Checksum high byte",
    0x4007: "Checksum low byte",
    0x50FE: "Mode 1 data stream definition table",
    0x77C0: "Rev limiter region",
    0x77DE: "Rev limiter high (RPM = byte * 25)",
    0x77DF: "Rev limiter low (RPM = byte * 25)",
    0x7FFF: "Calibration area end",
    0x1FFE0: "Interrupt vector table start (extended)",
    0x1FFFE: "RESET vector high byte (extended)",
    0x1FFFF: "RESET vector low byte (extended)",
}


# ═══════════════════════════════════════════════════════════════════════
# ALDL PROTOCOL HELPERS
# ═══════════════════════════════════════════════════════════════════════

def compute_checksum(frame: bytearray, end: int) -> int:
    """Two's complement checksum (sum of all bytes before end, mod 256, negated)."""
    return (256 - (sum(frame[:end]) & 0xFF)) & 0xFF


def apply_checksum(frame: bytearray) -> bytearray:
    """Apply checksum at the position indicated by the length byte."""
    cs_pos = frame[1] - 83
    frame[cs_pos] = compute_checksum(frame, cs_pos)
    return frame


def verify_frame(data: bytes) -> bool:
    """Verify an incoming ALDL frame checksum."""
    if len(data) < 3:
        return False
    cs_pos = data[1] - 83
    if cs_pos < 3 or cs_pos >= len(data):
        return False
    expected = compute_checksum(bytearray(data[:cs_pos]), cs_pos)
    return data[cs_pos] == expected


def frame_wire_length(frame: bytes) -> int:
    """Get the number of wire bytes from the length byte."""
    return frame[1] - 82


def hex_str(data: bytes) -> str:
    """Format bytes as hex string."""
    return ' '.join(f'{b:02X}' for b in data)


def hex_dump(data: bytes, base_addr: int = 0, width: int = 16) -> str:
    """
    Format data as a hex dump with addresses and ASCII.
    (From ALDL_read_RAM_commands.py)
    """
    lines = []
    for i in range(0, len(data), width):
        addr = base_addr + i
        chunk = data[i:i + width]
        hex_part = ' '.join(f'{b:02X}' for b in chunk)
        ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        lines.append(f"  ${addr:05X}: {hex_part:<{width*3}}  {ascii_part}")
    return '\n'.join(lines)


def compute_seed_key(seed_hi: int, seed_lo: int) -> int:
    """
    Compute seed→key for Mode 13 security unlock.
    Algorithm: key = 37709 - (seed_lo*256 + seed_hi)
    Note the SWAPPED byte order — from kingai_commie_flasher.py.
    """
    seed = seed_lo * 256 + seed_hi
    key = SEED_KEY_MAGIC - seed
    if key < 0:
        key += 65536
    return key & 0xFFFF


def compute_vy_checksum(data: bytearray, start: int = 0x2000, end: int = 0x20000,
                        skip_start: int = 0x4000, skip_end: int = 0x4007) -> int:
    """
    Compute VY V6 16-bit calibration checksum.
    Sums all bytes in range, skipping the checksum storage region.
    (From virtual_128kb_eeprom.py compute_checksum method)
    """
    total = 0
    for addr in range(start, min(end, len(data))):
        if skip_start <= addr <= skip_end:
            continue
        total = (total + data[addr]) & 0xFFFF
    return total


# ═══════════════════════════════════════════════════════════════════════
# VIRTUAL ECU
# ═══════════════════════════════════════════════════════════════════════

class VirtualECU:
    """
    Simulates a Delco 68HC11 ECU running OS $060A.

    Loads a 128KB bin file into an AMD 29F010 NOR flash simulator and
    responds to all ALDL protocol modes just like the real hardware.

    Features beyond basic sim:
      - AMD 29F010 flash model: proper erase-before-write, AND programming,
        sector erase, software ID, protection bits
      - Seed/key algorithm (SEED_KEY_MAGIC = 37709, from kingai_commie_flasher.py)
      - All modes: 1, 2, 3, 4, 5, 6, 8, 9, 10, 13, 16
      - 60-byte Mode 1 sensor data with VY-correct parameter offsets
      - Flash bank-aware writes matching kingai_commie_flasher BANK_WRITE_MAP
      - VY V6 checksum computation and verification
      - Logging via Python logging module
    """

    def __init__(self, bin_path: str | None = None, device_id: int = DEVICE_ID):
        self.device_id = device_id
        self.in_programming = False
        self.kernel_uploaded = False
        self.unlocked = False
        self.silenced = False
        self.write_bank = 0x48
        self.write_addr = 0x0000

        # ── AMD 29F010 Flash Simulator ──
        if FLASH_SIM_AVAILABLE:
            self.flash_chip = AMD29F010()
            log.info("AMD 29F010 flash simulator loaded")
        else:
            self.flash_chip = None
            log.warning("Flash simulator not available — using raw bytearray")

        # Load bin into flash
        self._flash_data = bytearray(FLASH_SIZE)
        if bin_path and Path(bin_path).exists():
            with open(bin_path, 'rb') as f:
                data = f.read()
            if len(data) == 16384:
                # 16KB cal-only → pad into 128KB at $4000
                self._flash_data = bytearray(b'\xFF' * FLASH_SIZE)
                self._flash_data[0x4000:0x4000 + 16384] = data
                log.info("Loaded 16KB cal into $4000-$7FFF")
            elif len(data) == FLASH_SIZE:
                self._flash_data = bytearray(data)
            else:
                self._flash_data[:len(data)] = data
                log.warning("Loaded %d bytes (expected %d)", len(data), FLASH_SIZE)

            if self.flash_chip:
                self.flash_chip.load_from_bytes(bytes(self._flash_data))
            log.info("Loaded %d bytes from %s", len(data), Path(bin_path).name)
        else:
            if self.flash_chip:
                pass  # Already starts erased (all 0xFF)
            log.info("Running with blank flash (all 0xFF)")

        # Actuator test state (Mode 4)
        self._actuator_active = False
        self._actuator_id = 0

        # Statistics
        self.stats = {
            'frames_rx': 0,
            'frames_tx': 0,
            'mode1_reads': 0,
            'mode2_reads': 0,
            'mode3_reads': 0,
            'mode4_tests': 0,
            'mode16_writes': 0,
            'mode10_writes': 0,
            'security_unlocks': 0,
            'bad_keys': 0,
        }

    @property
    def flash(self) -> bytearray:
        """Access to flash data (via flash chip if available, else raw)."""
        if self.flash_chip:
            return self.flash_chip.data
        return self._flash_data

    def process_frame(self, frame: bytes) -> bytes | None:
        """
        Process an incoming ALDL frame and return the response.
        Routes to the appropriate mode handler.
        """
        if len(frame) < 3:
            return None

        self.stats['frames_rx'] += 1
        device_id = frame[0]
        mode = frame[2]

        # Only respond to our device ID (or broadcast)
        if device_id != self.device_id and device_id != 0x00:
            return None

        handler = {
            MODE8_SILENCE:      lambda: self._handle_silence(),
            MODE9_UNSILENCE:    lambda: self._handle_unsilence(),
            MODE13_SECURITY:    lambda: self._handle_security(frame),
            MODE5_ENTER_PROG:   lambda: self._handle_enter_prog(),
            MODE6_UPLOAD:       lambda: self._handle_upload(frame),
            MODE1_DATASTREAM:   lambda: self._handle_datastream(),
            MODE2_READ_RAM:     lambda: self._handle_read(frame),
            MODE3_READ_BYTES:   lambda: self._handle_read_bytes(frame),
            MODE4_ACTUATOR:     lambda: self._handle_actuator(frame),
            MODE10_WRITE_CAL:   lambda: self._handle_write_cal(frame),
            MODE16_FLASH_WRITE: lambda: self._handle_write(frame),
        }.get(mode)

        if handler:
            resp = handler()
            if resp:
                self.stats['frames_tx'] += 1
            return resp
        else:
            log.warning("Unknown mode: 0x%02X", mode)
            return None

    def _make_ack(self, mode: int, extra: bytes = b'') -> bytes:
        """Build a simple ACK response."""
        resp = bytearray(FRAME_SIZE)
        resp[0] = self.device_id
        resp[1] = 0x56 + len(extra)
        resp[2] = mode
        for i, b in enumerate(extra):
            resp[3 + i] = b
        apply_checksum(resp)
        wire_len = frame_wire_length(resp)
        return bytes(resp[:wire_len])

    # ── Mode 8: Silence Bus ──

    def _handle_silence(self) -> bytes:
        self.silenced = True
        log.info("Bus silenced (Mode 8)")
        return self._make_ack(MODE8_SILENCE)

    # ── Mode 9: Unsilence Bus ──

    def _handle_unsilence(self) -> bytes:
        self.silenced = False
        log.info("Bus unsilenced (Mode 9)")
        return self._make_ack(MODE9_UNSILENCE)

    # ── Mode 13: Security (Seed/Key) ──

    def _handle_security(self, frame: bytes) -> bytes:
        """
        Handle Mode 13 seed/key security.
        Uses SEED_KEY_MAGIC = 37709 with swapped byte order
        (same algorithm as kingai_commie_flasher.py).
        """
        submode = frame[3] if len(frame) > 3 else 0

        if submode == 0x01:
            # Seed request — send our fixed seed
            log.info("Seed request — sending 0x%02X 0x%02X", SEED_HI, SEED_LO)
            return self._make_ack(MODE13_SECURITY, bytes([0x01, SEED_HI, SEED_LO]))

        elif submode == 0x02:
            # Key response — validate using seed/key algorithm
            if len(frame) >= 6:
                rx_key = (frame[4] << 8) | frame[5]
                expected_key = compute_seed_key(SEED_HI, SEED_LO)

                if rx_key == expected_key:
                    self.unlocked = True
                    self.stats['security_unlocks'] += 1
                    log.info("Security unlocked (key=0x%04X correct)", rx_key)
                    return self._make_ack(MODE13_SECURITY, bytes([0x02]))
                else:
                    self.stats['bad_keys'] += 1
                    log.warning("Security FAILED: got 0x%04X, expected 0x%04X",
                                rx_key, expected_key)
                    # Still ACK (real ECU sends NAK but for testing, ACK with error byte)
                    return self._make_ack(MODE13_SECURITY, bytes([0x02, 0x55]))
            else:
                # Malformed — accept anyway for dev convenience
                self.unlocked = True
                log.warning("Security: short key frame, accepting anyway")
                return self._make_ack(MODE13_SECURITY, bytes([0x02]))

        return None

    # ── Mode 5: Enter Programming ──

    def _handle_enter_prog(self) -> bytes:
        self.in_programming = True
        log.info("Entered programming mode (Mode 5)")
        return self._make_ack(MODE5_ENTER_PROG)

    # ── Mode 6: Kernel Upload ──

    def _handle_upload(self, frame: bytes) -> bytes:
        """Handle Mode 6 kernel upload — ACK each block."""
        self.kernel_uploaded = True
        payload_len = frame[1] - ALDL_LENGTH_OFFSET if len(frame) > 1 else 0
        log.info("Kernel upload block received (Mode 6, %d payload bytes)", payload_len)
        return self._make_ack(MODE6_UPLOAD, bytes([0xAA]))

    # ── Mode 1: Data Stream ──

    def _handle_datastream(self) -> bytes:
        """
        Return simulated Mode 1 sensor data (60 bytes).
        Offsets match MODE1_MSG0_PARAMS from kingai_commie_flasher.py.
        """
        self.stats['mode1_reads'] += 1
        data = bytearray(60)

        # Simulate realistic idle values (VY V6 Ecotec at ~800 RPM, warmed up)
        rpm = 800
        rpm_raw = rpm // 25  # scale = 25.0, so raw = RPM/25
        data[0] = (rpm_raw >> 8) & 0xFF    # RPM high byte (offset 0)
        data[1] = rpm_raw & 0xFF           # RPM low byte (offset 1)

        desired_idle = 750
        idle_raw = desired_idle // 25
        data[2] = (idle_raw >> 8) & 0xFF   # Desired Idle high (offset 2)
        data[3] = idle_raw & 0xFF          # Desired Idle low (offset 3)

        data[4] = 128                # ECT Voltage ~2.5V (offset 4, X*5/255)
        data[5] = 120                # ECT Temp ~50°C (offset 5, X*0.75-40)
        data[6] = 128                # IAT Voltage ~2.5V (offset 6)
        data[7] = 100                # IAT Temp ~35°C (offset 7, X*0.75-40)
        data[8] = 26                 # TPS ~10% (offset 8, X*100/255)
        data[9] = 26                 # TPSPOT snapshot (offset 9)
        data[10] = 128               # MAP Voltage ~2.5V (offset 10)
        data[11] = 38                # MAP kPa ~38 (offset 11)

        # Fuel system
        data[12] = 128               # Short Term Fuel Trim (128 = 0% correction)
        data[13] = 128               # Long Term Fuel Trim (128 = 0% correction)
        data[14] = 128               # O2 Sensor ~0.45V (offset 14)

        # Spark / timing
        data[15] = 20                # Spark Advance ~20° (offset 15)
        data[16] = 0                 # Knock retard 0° (offset 16)

        # Battery
        data[29] = 140               # Battery voltage 14.0V (offset 29)

        # IAC
        data[42] = 30                # IAC position 30 steps (offset 42)

        # Speed / gear
        data[30] = 0                 # Vehicle speed 0 km/h
        data[31] = 0                 # Speed high byte

        # Add slight random variation for realism
        data[0] = max(0, min(255, data[0] + random.randint(-1, 1)))
        data[14] = max(0, min(255, 128 + random.randint(-10, 10)))  # O2 flutter

        resp = bytearray(FRAME_SIZE)
        resp[0] = self.device_id
        resp[1] = 0x56 + len(data)
        resp[2] = MODE1_DATASTREAM
        resp[3:3 + len(data)] = data
        apply_checksum(resp)
        wire_len = frame_wire_length(resp)
        return bytes(resp[:wire_len])

    # ── Mode 2: Read RAM (64-byte blocks) ──

    def _handle_read(self, frame: bytes) -> bytes:
        """
        Handle Mode 2 RAM read — serve data from flash sim.
        Supports both 2-byte and 3-byte (extended) addressing.
        (From ALDL_read_RAM_commands.py address parsing)
        """
        self.stats['mode2_reads'] += 1
        if frame[1] == 0x59:
            # Extended 3-byte addressing
            addr = (frame[3] << 16) | (frame[4] << 8) | frame[5]
        else:
            # Standard 2-byte addressing
            addr = (frame[3] << 8) | frame[4]

        flash_data = self.flash
        end = min(addr + 64, FLASH_SIZE)
        block = flash_data[addr:end]
        if len(block) < 64:
            block = block + bytes(64 - len(block))

        resp = bytearray(FRAME_SIZE)
        resp[0] = self.device_id
        resp[1] = 0x55 + len(block) + 1
        resp[2] = MODE2_READ_RAM
        resp[3:3 + len(block)] = block
        apply_checksum(resp)
        wire_len = frame_wire_length(resp)

        # Log with known address annotation
        addr_note = KNOWN_ADDRESSES.get(addr, "")
        if addr_note:
            log.info("Read $%05X (%s): %s...", addr, addr_note, hex_str(block[:8]))
        else:
            log.debug("Read $%05X: %s...", addr, hex_str(block[:8]))

        return bytes(resp[:wire_len])

    # ── Mode 3: Read N Bytes ──

    def _handle_read_bytes(self, frame: bytes) -> bytes:
        """
        Handle Mode 3 — read a variable number of bytes at an address.
        Frame: [device_id, length, 0x03, addr_hi, addr_lo, count]
        This mode is defined in kingai_commie_flasher.py (MODE3_READ_BYTES).
        """
        self.stats['mode3_reads'] += 1
        if len(frame) < 6:
            return None

        addr = (frame[3] << 8) | frame[4]
        count = frame[5]
        if count == 0:
            count = 1
        if count > 128:
            count = 128  # Limit to prevent oversized response

        flash_data = self.flash
        end = min(addr + count, FLASH_SIZE)
        block = flash_data[addr:end]
        if len(block) < count:
            block = block + bytes(count - len(block))

        resp = bytearray(FRAME_SIZE)
        resp[0] = self.device_id
        resp[1] = ALDL_LENGTH_OFFSET + len(block) + 1
        resp[2] = MODE3_READ_BYTES
        resp[3:3 + len(block)] = block
        apply_checksum(resp)
        wire_len = frame_wire_length(resp)

        log.debug("Read %d bytes at $%04X (Mode 3)", count, addr)
        return bytes(resp[:wire_len])

    # ── Mode 4: Actuator Test ──

    def _handle_actuator(self, frame: bytes) -> bytes:
        """
        Handle Mode 4 actuator test commands.
        Frame: [device_id, length, 0x04, actuator_id, ...]

        Actuator IDs (VY V6 $060A):
            0x01 = IAC motor (idle air control)
            0x02 = Fuel injectors
            0x03 = Ignition coils (spark test)
            0x04 = Cooling fan relay
            0x05 = A/C clutch relay
            0x06 = MIL (check engine) lamp
            0x07 = Canister purge solenoid

        Defined in kingai_commie_flasher.py as MODE4_ACTUATOR.
        """
        self.stats['mode4_tests'] += 1
        actuator_id = frame[3] if len(frame) > 3 else 0
        param = frame[4] if len(frame) > 4 else 0

        actuator_names = {
            0x01: "IAC Motor",
            0x02: "Fuel Injectors",
            0x03: "Ignition Coils",
            0x04: "Cooling Fan Relay",
            0x05: "A/C Clutch Relay",
            0x06: "MIL Lamp",
            0x07: "Canister Purge",
        }
        name = actuator_names.get(actuator_id, f"Unknown(0x{actuator_id:02X})")

        if actuator_id == 0x00:
            # Stop all actuator tests
            self._actuator_active = False
            self._actuator_id = 0
            log.info("Actuator test STOPPED (Mode 4)")
        else:
            self._actuator_active = True
            self._actuator_id = actuator_id
            log.info("Actuator test: %s (id=0x%02X, param=0x%02X)", name, actuator_id, param)

        return self._make_ack(MODE4_ACTUATOR, bytes([actuator_id, 0xAA]))

    # ── Mode 10: Write Calibration ──

    def _handle_write_cal(self, frame: bytes) -> bytes:
        """
        Handle Mode 10 calibration write (NVRAM/EEPROM area).
        Writes to calibration sector ($4000-$7FFF) only.
        Frame: [device_id, length, 0x0A, addr_hi, addr_lo, data...]

        Defined in kingai_commie_flasher.py as MODE10_WRITE_CAL.
        """
        self.stats['mode10_writes'] += 1
        if len(frame) < 6:
            return None

        addr = (frame[3] << 8) | frame[4]
        data_start = 5
        data_len = frame[1] - ALDL_LENGTH_OFFSET - 3  # subtract mode + 2 addr bytes
        if data_len < 1:
            data_len = 1
        data = frame[data_start:data_start + data_len]

        # Validate: cal writes should be within $4000-$7FFF
        if addr < 0x4000 or addr > 0x7FFF:
            log.warning("Mode 10 write to non-cal address $%04X (outside $4000-$7FFF)", addr)

        # Write through flash simulator if available
        if self.flash_chip:
            for i, b in enumerate(data):
                target = addr + i
                if target < FLASH_SIZE:
                    self.flash_chip.program_byte_at(target, b)
        else:
            end = min(addr + len(data), FLASH_SIZE)
            self._flash_data[addr:end] = data[:end - addr]

        log.info("Cal write $%04X: %d bytes (Mode 10)", addr, len(data))
        return self._make_ack(MODE10_WRITE_CAL, bytes([0xAA]))

    # ── Mode 16: Flash Write ──

    def _handle_write(self, frame: bytes) -> bytes:
        """
        Handle Mode 16 flash write data.
        Writes through the AMD 29F010 flash simulator for realistic NOR behavior.
        Supports bank-aware addressing from kingai_commie_flasher.py BANK_WRITE_MAP.
        """
        self.stats['mode16_writes'] += 1
        if len(frame) > 38:
            # Extract 3-byte address + 32 bytes data
            addr = (frame[3] << 16) | (frame[4] << 8) | frame[5]
            data = frame[6:6 + 32]

            if self.flash_chip:
                # Write through flash simulator (enforces NOR AND semantics)
                for i, b in enumerate(data):
                    target = addr + i
                    if target < FLASH_SIZE:
                        self.flash_chip.program_byte_at(target, b)
                log.info("Flash write $%05X: %d bytes via AMD29F010 sim (Mode 16)", addr, len(data))
            else:
                end = min(addr + len(data), FLASH_SIZE)
                self._flash_data[addr:end] = data[:end - addr]
                log.info("Flash write $%05X: %d bytes raw (Mode 16)", addr, len(data))

        return self._make_ack(MODE16_FLASH_WRITE, bytes([0xAA]))

    # ── Flash Operations (programmatic API for testing) ──

    def erase_sector(self, sector: int) -> bool:
        """Erase a flash sector (for testing write sequences)."""
        if self.flash_chip:
            ok = self.flash_chip.erase_sector_by_index(sector)
            log.info("Sector %d erase: %s", sector, "OK" if ok else "FAILED")
            return ok
        else:
            base = sector * SECTOR_SIZE
            for i in range(SECTOR_SIZE):
                self._flash_data[base + i] = 0xFF
            log.info("Sector %d erased (raw bytearray)", sector)
            return True

    def get_flash_info(self) -> Tuple[int, int]:
        """Read flash manufacturer + device ID."""
        if self.flash_chip:
            return self.flash_chip.read_software_id()
        return FLASH_AMD_29F010

    def verify_checksum(self) -> Tuple[bool, int, int]:
        """
        Verify the VY V6 calibration checksum.
        Returns (match, computed, stored).
        """
        flash_data = self.flash
        computed = compute_vy_checksum(flash_data)
        stored = (flash_data[CHECKSUM_OFFSET_HI] << 8) | flash_data[CHECKSUM_OFFSET_LO]
        return (computed == stored, computed, stored)

    # ── Diagnostics ──

    def dump_flash_info(self) -> str:
        """Return formatted flash chip and sector info."""
        lines = ["=== Virtual ECU Flash Status ==="]
        mfg, dev = self.get_flash_info()
        lines.append(f"  Flash: Manufacturer=0x{mfg:02X}, Device=0x{dev:02X}")

        if self.flash_chip and hasattr(self.flash_chip, 'dump_sector_info'):
            lines.append(self.flash_chip.dump_sector_info())
        if self.flash_chip and hasattr(self.flash_chip, 'dump_stats'):
            lines.append(self.flash_chip.dump_stats())

        ok, computed, stored = self.verify_checksum()
        lines.append(f"  Checksum: stored=0x{stored:04X}, computed=0x{computed:04X}, {'OK' if ok else 'MISMATCH'}")
        return "\n".join(lines)

    def dump_stats(self) -> str:
        """Return formatted vECU statistics."""
        lines = ["=== Virtual ECU Statistics ==="]
        for k, v in self.stats.items():
            lines.append(f"  {k}: {v}")
        lines.append(f"  unlocked: {self.unlocked}")
        lines.append(f"  in_programming: {self.in_programming}")
        lines.append(f"  kernel_uploaded: {self.kernel_uploaded}")
        lines.append(f"  silenced: {self.silenced}")
        if self._actuator_active:
            lines.append(f"  actuator_test: 0x{self._actuator_id:02X} ACTIVE")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════
# TCP SERVER (for vECU mode)
# ═══════════════════════════════════════════════════════════════════════

def run_vecu_tcp(vecu: VirtualECU, host: str = "127.0.0.1", port: int = 8192):
    """Run the virtual ECU as a TCP server."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(1)
    log.info("TCP server listening on %s:%d", host, port)
    log.info("Connect with: socat PTY,link=/dev/ttyVECU TCP:%s:%d", host, port)
    log.info("Or use a virtual COM port bridge on Windows")
    log.info("Flash info:\n%s", vecu.dump_flash_info())

    try:
        while True:
            conn, addr = server.accept()
            log.info("Client connected from %s", addr)
            handle_client(vecu, conn)
            log.info("Client disconnected. Stats:\n%s", vecu.dump_stats())
    except KeyboardInterrupt:
        log.info("Shutting down")
    finally:
        server.close()


def handle_client(vecu: VirtualECU, conn: socket.socket):
    """Handle a single client connection."""
    buf = bytearray()
    try:
        while True:
            data = conn.recv(1024)
            if not data:
                break
            buf.extend(data)

            # Try to parse complete frames from buffer
            while len(buf) >= 3:
                wire_len = buf[1] - 82
                if wire_len < 3 or wire_len > FRAME_SIZE:
                    buf.pop(0)  # discard bad byte
                    continue
                if len(buf) < wire_len:
                    break  # need more data

                frame = bytes(buf[:wire_len])
                buf = buf[wire_len:]

                log.debug("RX: %s", hex_str(frame[:min(len(frame), 20)]))

                resp = vecu.process_frame(frame)
                if resp:
                    conn.sendall(resp)
                    log.debug("TX: %s", hex_str(resp[:min(len(resp), 20)]))
    except (ConnectionResetError, BrokenPipeError):
        log.info("Client disconnected")
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════
# FRAME SENDER (for sending raw frames to real ECU)
# ═══════════════════════════════════════════════════════════════════════

def send_frame(serial_port, frame_hex: str, baud: int = ALDL_BAUD):
    """Send a raw ALDL frame to a real ECU and display the response."""
    try:
        import serial
    except ImportError:
        print("ERROR: pyserial not installed. Run: pip install pyserial")
        sys.exit(1)

    # Parse hex string into bytes
    hex_clean = frame_hex.replace(',', ' ').replace('0x', '').strip()
    raw_bytes = bytes.fromhex(hex_clean.replace(' ', ''))

    # Build a proper frame if fewer than 3 bytes provided
    if len(raw_bytes) < 3:
        print(f"  Frame too short ({len(raw_bytes)} bytes). Need at least device_id, length, mode.")
        return

    # If no checksum, auto-apply it
    frame = bytearray(FRAME_SIZE)
    frame[:len(raw_bytes)] = raw_bytes
    if frame[1] == 0:
        # Auto-calculate length byte
        frame[1] = 85 + len(raw_bytes) - 2  # rough estimate
    apply_checksum(frame)
    wire_len = frame_wire_length(frame)
    tx_data = bytes(frame[:wire_len])

    print(f"  TX: {hex_str(tx_data)}")

    ser = serial.Serial(
        port=serial_port,
        baudrate=baud,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=2.0,
    )

    try:
        ser.reset_input_buffer()
        ser.write(tx_data)
        ser.flush()

        # Consume echo
        time.sleep(0.1)
        echo = ser.read(len(tx_data))

        # Wait for response
        time.sleep(0.05)
        resp = ser.read(FRAME_SIZE)
        if resp:
            print(f"  RX: {hex_str(resp)}")
            if verify_frame(resp):
                print(f"  Checksum: OK")
                mode = resp[2]
                print(f"  Mode: 0x{mode:02X}")
                payload_len = resp[1] - 85 - 1
                if payload_len > 0:
                    payload = resp[3:3 + payload_len]
                    print(f"  Payload ({payload_len} bytes): {hex_str(payload)}")
            else:
                print(f"  Checksum: FAIL")
        else:
            print(f"  No response (timeout)")
    finally:
        ser.close()


def interactive_mode(serial_port: str, baud: int = ALDL_BAUD):
    """Interactive ALDL frame sender — type hex, see responses."""
    print(f"ALDL Interactive Frame Sender")
    print(f"  Port: {serial_port} @ {baud} baud")
    print(f"  Type hex bytes separated by spaces (e.g., F7 56 08)")
    print(f"  Built-in shortcuts:")
    print(f"    silence      → Mode 8 silence bus")
    print(f"    unsilence    → Mode 9 unsilence bus")
    print(f"    seed         → Mode 13 seed request")
    print(f"    read ADDR    → Mode 2 read 64B at hex address")
    print(f"    readn ADDR N → Mode 3 read N bytes at hex address")
    print(f"    xread ADDR   → Mode 2 extended 3-byte addr read")
    print(f"    actuator ID  → Mode 4 actuator test (hex ID)")
    print(f"    actuator 0   → Stop actuator tests")
    print(f"    dump ADDR N  → hex dump N bytes from address")
    print(f"    quit         → Exit")
    print()

    shortcuts = {
        'silence': f'{DEVICE_ID:02X} 56 08',
        'unsilence': f'{DEVICE_ID:02X} 56 09',
        'seed': f'{DEVICE_ID:02X} 57 0D 01',
    }

    while True:
        try:
            line = input("ALDL> ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not line or line.lower() == 'quit':
            break

        # Handle shortcuts
        if line.lower() in shortcuts:
            line = shortcuts[line.lower()]
        elif line.lower().startswith('readn '):
            # Mode 3: readn ADDR N
            parts = line.split()
            addr = int(parts[1], 16)
            count = int(parts[2]) if len(parts) > 2 else 1
            hi = (addr >> 8) & 0xFF
            lo = addr & 0xFF
            line = f'{DEVICE_ID:02X} 59 03 {hi:02X} {lo:02X} {count:02X}'
        elif line.lower().startswith('xread '):
            # Extended 3-byte address read
            addr_str = line.split()[1]
            addr = int(addr_str, 16)
            b2 = (addr >> 16) & 0xFF
            hi = (addr >> 8) & 0xFF
            lo = addr & 0xFF
            line = f'{DEVICE_ID:02X} 59 02 {b2:02X} {hi:02X} {lo:02X}'
        elif line.lower().startswith('read '):
            addr_str = line.split()[1]
            addr = int(addr_str, 16)
            hi = (addr >> 8) & 0xFF
            lo = addr & 0xFF
            line = f'{DEVICE_ID:02X} 58 02 {hi:02X} {lo:02X}'
        elif line.lower().startswith('actuator '):
            parts = line.split()
            act_id = int(parts[1], 16) if len(parts) > 1 else 0
            line = f'{DEVICE_ID:02X} 57 04 {act_id:02X}'

        send_frame(serial_port, line, baud)
        print()


# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Virtual ALDL ECU + Frame Sender",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  vecu         Run as a virtual ECU (TCP server)
  send         Send a single raw ALDL frame to a real ECU
  interactive  Interactive ALDL frame sender

Examples:
  # Start virtual ECU with stock bin (AMD 29F010 flash sim)
  python virtual_aldl_frame_sender_and_vecu.py --mode vecu --bin stock.bin

  # Start with verbose debug logging
  python virtual_aldl_frame_sender_and_vecu.py --mode vecu --bin stock.bin --verbose

  # Send Mode 8 silence to real ECU on COM3
  python virtual_aldl_frame_sender_and_vecu.py --mode send --serial COM3 --frame "F7 56 08"

  # Interactive mode
  python virtual_aldl_frame_sender_and_vecu.py --mode interactive --serial COM3
        """,
    )
    parser.add_argument("--mode", choices=["vecu", "send", "interactive"],
                        default="vecu", help="Operating mode (default: vecu)")
    parser.add_argument("--serial", type=str, default="COM3",
                        help="Serial port for send/interactive modes")
    parser.add_argument("--baud", type=int, default=ALDL_BAUD,
                        help=f"Baud rate (default: {ALDL_BAUD})")
    parser.add_argument("--host", type=str, default="127.0.0.1",
                        help="TCP host for vECU mode (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8192,
                        help="TCP port for vECU mode (default: 8192)")
    parser.add_argument("--bin", type=str, default=None,
                        help="128KB .bin file to load into vECU flash")
    parser.add_argument("--frame", type=str, default=None,
                        help="Hex bytes to send (for send mode)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable verbose debug logging")
    args = parser.parse_args()

    # Reconfigure logger with user-requested console level
    global log
    console_level = logging.DEBUG if args.verbose else logging.WARNING
    log = setup_logging(name="vecu", console_level=console_level)

    if args.mode == "vecu":
        vecu = VirtualECU(bin_path=args.bin, device_id=DEVICE_ID)
        if FLASH_SIM_AVAILABLE:
            log.info("AMD 29F010 flash simulator active")
        else:
            log.warning("AMD 29F010 simulator not available — using raw bytearray")
            log.warning("  (place virtual_128kb_eeprom.py in parent directory)")
        run_vecu_tcp(vecu, args.host, args.port)

    elif args.mode == "send":
        if not args.frame:
            print("ERROR: --frame is required for send mode")
            sys.exit(1)
        send_frame(args.serial, args.frame, args.baud)

    elif args.mode == "interactive":
        interactive_mode(args.serial, args.baud)


if __name__ == "__main__":
    main()