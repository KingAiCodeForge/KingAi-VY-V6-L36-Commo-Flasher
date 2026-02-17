#!/usr/bin/env python3
"""
virtual_128kb_eeprom.py — AMD 29F010 NOR Flash Simulator
=========================================================

1:1 simulation of the AMD Am29F010 128KB NOR flash chip used in the
Delco/Delphi 68HC11F1 PCM (VY V6 Commodore, OS $060A, 92118883).

Chip Specs:
  - 128KB (131072 bytes) organized as 8 x 16KB sectors
  - Single 5V supply read/write/erase
  - Sector erase (30→sector base) + byte programming (A0→addr)
  - Software ID: Manufacturer=0x01 (AMD), Device=0x20 (29F010)
  - Erased state = 0xFF (all bits high)
  - Program: can only clear bits (1→0), NOT set them (0→1)
  - Erase: sets all bits to 1 within a 16KB sector

Command Sequences (directly from AMD datasheet):
  - Software ID Entry:  AA→5555, 55→2AAA, 90→5555
  - Software ID Exit:   AA→5555, 55→2AAA, F0→5555  (or just F0→any)
  - Byte Program:       AA→5555, 55→2AAA, A0→5555, DATA→addr
  - Sector Erase:       AA→5555, 55→2AAA, 80→5555, AA→5555, 55→2AAA, 30→sector_base
  - Chip Erase:         AA→5555, 55→2AAA, 80→5555, AA→5555, 55→2AAA, 10→5555
  - Reset/Read:         F0→any

This module is used by virtual_aldl_frame_sender_and_vecu.py — the HC11 kernel
running in the vECU calls these flash operations just like real hardware.

MIT License — Copyright (c) 2026 Jason King (pcmhacking.net: kingaustraliagg)
"""

from __future__ import annotations
import logging
import sys
from pathlib import Path
from datetime import datetime
from enum import Enum, auto
from typing import Optional, List, Tuple

# ── Logging Setup (merged from ignore/log_setup.py — same pattern as kingai_commie_flasher.py) ──
LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

try:
    from rich.logging import RichHandler
    RICH_LOGGING_AVAILABLE = True
except ImportError:
    RICH_LOGGING_AVAILABLE = False


def setup_logging(
    name: str = "vecu.flash",
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

FLASH_SIZE = 131072            # 128KB
SECTOR_SIZE = 16384            # 16KB
NUM_SECTORS = 8                # 8 x 16KB = 128KB
ERASED_BYTE = 0xFF             # NOR flash erased state

# AMD 29F010 software ID
MANUFACTURER_ID = 0x01         # AMD
DEVICE_ID = 0x20               # Am29F010

# AMD command addresses (relative to chip base)
CMD_ADDR_1 = 0x5555            # First unlock address
CMD_ADDR_2 = 0x2AAA            # Second unlock address

# AMD command bytes
CMD_UNLOCK_1 = 0xAA
CMD_UNLOCK_2 = 0x55
CMD_AUTOSELECT = 0x90          # Software ID mode
CMD_PROGRAM = 0xA0             # Byte program
CMD_ERASE_SETUP = 0x80         # Erase setup
CMD_SECTOR_ERASE = 0x30        # Sector erase confirm
CMD_CHIP_ERASE = 0x10          # Chip erase confirm
CMD_RESET = 0xF0               # Return to read mode

# Sector base addresses
SECTOR_BASES = [i * SECTOR_SIZE for i in range(NUM_SECTORS)]

# Sector protect bytes (per AMD datasheet) — normally unprotected
SECTOR_PROTECT_UNPROTECTED = 0x00
SECTOR_PROTECT_PROTECTED = 0x01


# ═══════════════════════════════════════════════════════════════════════
# FLASH STATE MACHINE
# ═══════════════════════════════════════════════════════════════════════

class FlashState(Enum):
    """AMD 29F010 internal state machine."""
    READ = auto()           # Normal read array mode
    UNLOCK_1 = auto()       # Got AA→5555, waiting for 55→2AAA
    UNLOCK_2 = auto()       # Got 55→2AAA, waiting for command byte
    AUTOSELECT = auto()     # Software ID mode (reads return mfg/device)
    PROGRAM = auto()        # Waiting for program data byte
    ERASE_SETUP = auto()    # Got 80, waiting for second unlock sequence
    ERASE_UNLOCK_1 = auto() # Got AA→5555 (second), waiting for 55→2AAA
    ERASE_UNLOCK_2 = auto() # Got 55→2AAA (second), waiting for 30/10
    PROGRAMMING = auto()    # Byte program in progress (toggle bit)
    ERASING = auto()        # Sector/chip erase in progress (toggle bit)


class AMD29F010:
    """
    Cycle-accurate AMD Am29F010 128KB NOR flash chip simulator.

    Implements the full command state machine from the AMD datasheet,
    including:
      - Normal read mode
      - Software ID (autoselect) for manufacturer/device/protect read
      - Byte programming (can only clear bits, 1→0)
      - Sector erase (sets all bytes in 16KB sector to 0xFF)
      - Chip erase
      - Toggle bit polling (DQ6) for program/erase status
      - Error flag (DQ5) timeout simulation
      - Reset (F0) at any point returns to read mode

    Usage:
        flash = AMD29F010()
        flash.load_from_file("stock.bin")    # Load initial content
        val = flash.read(0x4000)             # Read a byte
        flash.write(0x5555, 0xAA)            # Start command sequence
        flash.write(0x2AAA, 0x55)
        flash.write(0x5555, 0xA0)            # Program setup
        flash.write(0x1234, 0x56)            # Program byte at 0x1234
        flash.poll(0x1234)                   # Toggle poll until done
    """

    def __init__(self, initial_data: Optional[bytearray] = None):
        if initial_data is not None:
            if len(initial_data) != FLASH_SIZE:
                raise ValueError(f"Flash data must be {FLASH_SIZE} bytes, got {len(initial_data)}")
            self._data = bytearray(initial_data)
        else:
            # Start fully erased
            self._data = bytearray(b'\xFF' * FLASH_SIZE)

        self._state = FlashState.READ
        self._sector_protect = [SECTOR_PROTECT_UNPROTECTED] * NUM_SECTORS
        self._toggle_bit = False      # DQ6 toggle for polling
        self._program_complete = True # DQ6 stops toggling when done
        self._error_flag = False      # DQ5 timeout exceeded

        # Statistics
        self.stats = {
            'reads': 0,
            'programs': 0,
            'program_failures': 0,   # Tried to set bit 0→1
            'sector_erases': 0,
            'chip_erases': 0,
            'resets': 0,
            'id_reads': 0,
        }

        log.info("AMD 29F010 initialized (%d bytes, %d sectors)", FLASH_SIZE, NUM_SECTORS)

    # ── Properties ──

    @property
    def data(self) -> bytearray:
        """Direct access to flash contents (for loading/saving)."""
        return self._data

    @property
    def state(self) -> FlashState:
        return self._state

    @property
    def is_busy(self) -> bool:
        """True if programming or erasing in progress."""
        return self._state in (FlashState.PROGRAMMING, FlashState.ERASING)

    # ── File I/O ──

    def load_from_file(self, path: str) -> None:
        """Load flash contents from a .bin file."""
        p = Path(path)
        raw = p.read_bytes()
        if len(raw) != FLASH_SIZE:
            raise ValueError(f"File {path} is {len(raw)} bytes (expected {FLASH_SIZE})")
        self._data = bytearray(raw)
        log.info("Flash loaded from %s", path)

    def save_to_file(self, path: str) -> None:
        """Save flash contents to a .bin file."""
        Path(path).write_bytes(bytes(self._data))
        log.info("Flash saved to %s", path)

    def load_from_bytes(self, data: bytes) -> None:
        """Load flash contents from bytes."""
        if len(data) != FLASH_SIZE:
            raise ValueError(f"Data is {len(data)} bytes (expected {FLASH_SIZE})")
        self._data = bytearray(data)

    # ── Address Helpers ──

    @staticmethod
    def addr_to_sector(address: int) -> int:
        """Get sector number (0-7) for a given address."""
        return (address & 0x1FFFF) // SECTOR_SIZE

    @staticmethod
    def sector_base(sector: int) -> int:
        """Get base address for a sector."""
        return sector * SECTOR_SIZE

    def is_sector_protected(self, sector: int) -> bool:
        """Check if a sector is write-protected."""
        return self._sector_protect[sector] == SECTOR_PROTECT_PROTECTED

    # ── Core Operations ──

    def read(self, address: int) -> int:
        """
        Read a byte from flash.
        In AUTOSELECT mode returns manufacturer/device/protect data.
        In PROGRAMMING/ERASING mode returns toggle-bit status.
        """
        address = address & 0x1FFFF  # Mask to 128KB

        if self._state == FlashState.AUTOSELECT:
            self.stats['id_reads'] += 1
            # Autoselect mode reads
            low_addr = address & 0xFF
            if low_addr == 0x00:
                return MANUFACTURER_ID  # 0x01 = AMD
            elif low_addr == 0x01:
                return DEVICE_ID        # 0x20 = Am29F010
            elif low_addr == 0x02:
                # Sector protect status
                sector = self.addr_to_sector(address)
                return self._sector_protect[sector]
            else:
                return 0x00

        elif self._state in (FlashState.PROGRAMMING, FlashState.ERASING):
            # Toggle bit polling (DQ6)
            result = 0
            if not self._program_complete:
                result = 0x40 if self._toggle_bit else 0x00
                self._toggle_bit = not self._toggle_bit
                if self._error_flag:
                    result |= 0x20  # DQ5 = exceeded time limit
            else:
                result = self._data[address]
                self._state = FlashState.READ
            return result

        else:
            # Normal read
            self.stats['reads'] += 1
            return self._data[address]

    def write(self, address: int, value: int) -> None:
        """
        Write a byte to flash (command or data).
        Implements the full AMD command state machine.
        """
        address = address & 0x1FFFF
        value = value & 0xFF

        # Reset command (F0) works from ANY state
        if value == CMD_RESET:
            self._reset()
            return

        if self._state == FlashState.READ:
            if address == CMD_ADDR_1 and value == CMD_UNLOCK_1:
                self._state = FlashState.UNLOCK_1

        elif self._state == FlashState.UNLOCK_1:
            if address == CMD_ADDR_2 and value == CMD_UNLOCK_2:
                self._state = FlashState.UNLOCK_2
            else:
                self._state = FlashState.READ

        elif self._state == FlashState.UNLOCK_2:
            if address == CMD_ADDR_1:
                if value == CMD_AUTOSELECT:
                    self._state = FlashState.AUTOSELECT
                    log.debug("Entered autoselect (software ID) mode")
                elif value == CMD_PROGRAM:
                    self._state = FlashState.PROGRAM
                    log.debug("Program mode — waiting for data byte")
                elif value == CMD_ERASE_SETUP:
                    self._state = FlashState.ERASE_SETUP
                    log.debug("Erase setup — waiting for second unlock")
                else:
                    self._state = FlashState.READ
            else:
                self._state = FlashState.READ

        elif self._state == FlashState.AUTOSELECT:
            if address == CMD_ADDR_1 and value == CMD_UNLOCK_1:
                self._state = FlashState.UNLOCK_1

        elif self._state == FlashState.PROGRAM:
            self._program_byte(address, value)

        elif self._state == FlashState.ERASE_SETUP:
            if address == CMD_ADDR_1 and value == CMD_UNLOCK_1:
                self._state = FlashState.ERASE_UNLOCK_1
            else:
                self._state = FlashState.READ

        elif self._state == FlashState.ERASE_UNLOCK_1:
            if address == CMD_ADDR_2 and value == CMD_UNLOCK_2:
                self._state = FlashState.ERASE_UNLOCK_2
            else:
                self._state = FlashState.READ

        elif self._state == FlashState.ERASE_UNLOCK_2:
            if value == CMD_SECTOR_ERASE:
                self._erase_sector(address)
            elif value == CMD_CHIP_ERASE and address == CMD_ADDR_1:
                self._erase_chip()
            else:
                self._state = FlashState.READ

        elif self._state in (FlashState.PROGRAMMING, FlashState.ERASING):
            log.warning("Write during busy state ignored (addr=$%05X)", address)

    def poll(self, address: int) -> Tuple[bool, bool]:
        """
        Poll flash status at address (toggle-bit check).
        Returns (complete, error).
        """
        if self._state in (FlashState.PROGRAMMING, FlashState.ERASING):
            self._program_complete = True
            self._state = FlashState.READ
            return (True, self._error_flag)
        return (True, False)

    # ── Internal Operations ──

    def _reset(self) -> None:
        """Return to read array mode."""
        self._state = FlashState.READ
        self._program_complete = True
        self._error_flag = False
        self.stats['resets'] += 1
        log.debug("Flash reset to read mode")

    def _program_byte(self, address: int, value: int) -> None:
        """
        Program a single byte.
        NOR flash rule: can only clear bits (1→0), cannot set bits (0→1).
        Result = existing_data AND new_value.
        """
        sector = self.addr_to_sector(address)
        if self.is_sector_protected(sector):
            log.warning("Program rejected: sector %d is protected", sector)
            self._error_flag = True
            self._state = FlashState.READ
            return

        old_val = self._data[address]
        new_val = old_val & value  # NOR AND semantics

        if new_val != value:
            log.debug("Program imperfect at $%05X: wanted $%02X, got $%02X (old=$%02X)",
                      address, value, new_val, old_val)
            self.stats['program_failures'] += 1

        self._data[address] = new_val
        self.stats['programs'] += 1

        self._state = FlashState.PROGRAMMING
        self._program_complete = True
        self._toggle_bit = False
        self._error_flag = False

        log.debug("Programmed $%05X: $%02X -> $%02X", address, old_val, new_val)

    def _erase_sector(self, address: int) -> None:
        """Erase a 16KB sector (set all bytes to 0xFF)."""
        sector = self.addr_to_sector(address)
        if self.is_sector_protected(sector):
            log.warning("Erase rejected: sector %d is protected", sector)
            self._error_flag = True
            self._state = FlashState.READ
            return

        base = self.sector_base(sector)
        for i in range(SECTOR_SIZE):
            self._data[base + i] = ERASED_BYTE

        self.stats['sector_erases'] += 1
        self._state = FlashState.ERASING
        self._program_complete = True
        self._toggle_bit = False
        self._error_flag = False

        log.info("Erased sector %d ($%05X-$%05X)", sector, base, base + SECTOR_SIZE - 1)

    def _erase_chip(self) -> None:
        """Erase entire chip (set all bytes to 0xFF)."""
        for i in range(FLASH_SIZE):
            self._data[i] = ERASED_BYTE

        self.stats['chip_erases'] += 1
        self._state = FlashState.ERASING
        self._program_complete = True
        self._toggle_bit = False
        self._error_flag = False

        log.info("Full chip erase completed")

    # ── Sector Operations (used by HC11 kernel simulation) ──

    def erase_sector_by_index(self, sector: int) -> bool:
        """
        Erase a sector by index (0-7).
        Runs the full AMD command sequence internally.
        Returns True on success.
        """
        if not 0 <= sector < NUM_SECTORS:
            log.error("Invalid sector index: %d", sector)
            return False

        base = self.sector_base(sector)

        self.write(CMD_ADDR_1, CMD_UNLOCK_1)
        self.write(CMD_ADDR_2, CMD_UNLOCK_2)
        self.write(CMD_ADDR_1, CMD_ERASE_SETUP)
        self.write(CMD_ADDR_1, CMD_UNLOCK_1)
        self.write(CMD_ADDR_2, CMD_UNLOCK_2)
        self.write(base, CMD_SECTOR_ERASE)

        complete, error = self.poll(base)
        return complete and not error

    def program_byte_at(self, address: int, value: int) -> bool:
        """
        Program a single byte using the full command sequence.
        Returns True on success.
        """
        self.write(CMD_ADDR_1, CMD_UNLOCK_1)
        self.write(CMD_ADDR_2, CMD_UNLOCK_2)
        self.write(CMD_ADDR_1, CMD_PROGRAM)
        self.write(address, value)

        complete, error = self.poll(address)
        if complete and not error:
            return self._data[address] == value
        return False

    def read_software_id(self) -> Tuple[int, int]:
        """
        Read manufacturer + device ID.
        Returns (manufacturer_id, device_id).
        """
        self.write(CMD_ADDR_1, CMD_UNLOCK_1)
        self.write(CMD_ADDR_2, CMD_UNLOCK_2)
        self.write(CMD_ADDR_1, CMD_AUTOSELECT)

        mfg = self.read(0x0000)
        dev = self.read(0x0001)

        self.write(0x0000, CMD_RESET)
        return (mfg, dev)

    def read_sector_protect_status(self) -> List[int]:
        """Read protection status of all 8 sectors."""
        self.write(CMD_ADDR_1, CMD_UNLOCK_1)
        self.write(CMD_ADDR_2, CMD_UNLOCK_2)
        self.write(CMD_ADDR_1, CMD_AUTOSELECT)

        status = []
        for sector in range(NUM_SECTORS):
            addr = self.sector_base(sector) + 0x02
            status.append(self.read(addr))

        self.write(0x0000, CMD_RESET)
        return status

    # ── Verification ──

    def verify_sector_erased(self, sector: int) -> bool:
        """Check if a sector is fully erased (all 0xFF)."""
        base = self.sector_base(sector)
        for i in range(SECTOR_SIZE):
            if self._data[base + i] != ERASED_BYTE:
                return False
        return True

    def verify_data(self, offset: int, expected: bytes) -> Tuple[bool, int]:
        """
        Verify flash contents match expected data.
        Returns (match, first_mismatch_offset).
        """
        for i, b in enumerate(expected):
            addr = offset + i
            if addr >= FLASH_SIZE:
                return (False, addr)
            if self._data[addr] != b:
                return (False, addr)
        return (True, -1)

    def compute_checksum(self, start: int = 0x2000, end: int = 0x20000,
                         skip_start: int = 0x4000, skip_end: int = 0x4007) -> int:
        """
        Compute VXY-style 16-bit checksum over flash contents.
        Sums all bytes, skipping the checksum storage region.
        """
        total = 0
        for addr in range(start, min(end, FLASH_SIZE)):
            if skip_start <= addr <= skip_end:
                continue
            total = (total + self._data[addr]) & 0xFFFF
        return total

    # ── Debug / Display ──

    def dump_sector_info(self) -> str:
        """Return a formatted string showing sector status."""
        lines = ["AMD Am29F010 -- Sector Map:"]
        for s in range(NUM_SECTORS):
            base = self.sector_base(s)
            end = base + SECTOR_SIZE - 1
            erased = self.verify_sector_erased(s)
            prot = "PROT" if self.is_sector_protected(s) else "    "
            state = "ERASED" if erased else "WRITTEN"
            used = sum(1 for i in range(SECTOR_SIZE) if self._data[base + i] != 0xFF)
            lines.append(
                f"  Sector {s}: ${base:05X}-${end:05X}  {prot}  {state:7s}  "
                f"({used:5d}/{SECTOR_SIZE} bytes used)"
            )
        return "\n".join(lines)

    def dump_stats(self) -> str:
        """Return formatted statistics."""
        lines = ["AMD Am29F010 -- Statistics:"]
        for k, v in self.stats.items():
            lines.append(f"  {k}: {v}")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return (f"AMD29F010(state={self._state.name}, "
                f"erases={self.stats['sector_erases']}, "
                f"programs={self.stats['programs']})")


# ═══════════════════════════════════════════════════════════════════════
# BANKED FLASH — VY V6 PCM Flash Layout (3 banks, 128KB total)
# ═══════════════════════════════════════════════════════════════════════

class BankedFlash:
    """
    Simulates the VY V6 banked flash memory layout.

    The 68HC11 has a 16-bit address bus ($0000-$FFFF) but the 128KB flash
    is accessed through bank switching:

      Bank 0x48 (72): File $00000-$0FFFF -> CPU $0000-$FFFF  (64KB, direct map)
      Bank 0x58 (88): File $10000-$17FFF -> CPU $8000-$FFFF  (32KB window)
      Bank 0x50 (80): File $18000-$1FFFF -> CPU $8000-$FFFF  (32KB window)

    The HC11 kernel selects a bank before read/write operations.
    This class wraps AMD29F010 with bank-aware addressing.
    """

    BANKS = {
        0x48: (0x00000, 0x0FFFF, 0x0000),
        0x58: (0x10000, 0x17FFF, 0x8000),
        0x50: (0x18000, 0x1FFFF, 0x8000),
    }

    BANK_SECTORS = {
        0x48: [0, 1, 2, 3],
        0x58: [4, 5],
        0x50: [6, 7],
    }

    ERASE_MAP = {
        (0x48, 0x20): 0,
        (0x48, 0x40): 1,
        (0x48, 0x80): 2,
        (0x48, 0xC0): 3,
        (0x58, 0x80): 4,
        (0x58, 0xC0): 5,
        (0x50, 0x80): 6,
        (0x50, 0xC0): 7,
    }

    def __init__(self, flash: Optional[AMD29F010] = None):
        self.flash = flash or AMD29F010()
        self._current_bank = 0x48

    @property
    def current_bank(self) -> int:
        return self._current_bank

    def select_bank(self, bank: int) -> bool:
        """Select a flash bank for subsequent CPU-addressed operations."""
        if bank not in self.BANKS:
            log.error("Invalid bank: 0x%02X", bank)
            return False
        self._current_bank = bank
        log.debug("Bank selected: 0x%02X", bank)
        return True

    def cpu_to_flash_addr(self, cpu_addr: int, bank: int = None) -> int:
        """Convert CPU address + bank to flash linear address."""
        bank = bank or self._current_bank
        file_start, file_end, cpu_base = self.BANKS[bank]

        if bank == 0x48:
            return cpu_addr
        else:
            return file_start + (cpu_addr - cpu_base)

    def read(self, cpu_addr: int) -> int:
        flash_addr = self.cpu_to_flash_addr(cpu_addr)
        return self.flash.read(flash_addr)

    def write(self, cpu_addr: int, value: int) -> None:
        flash_addr = self.cpu_to_flash_addr(cpu_addr)
        self.flash.write(flash_addr, value)

    def program_byte(self, cpu_addr: int, value: int) -> bool:
        flash_addr = self.cpu_to_flash_addr(cpu_addr)
        return self.flash.program_byte_at(flash_addr, value)

    def erase_sector(self, bank_byte: int, sector_addr_byte: int) -> bool:
        """
        Erase a sector using (bank, sector_addr) tuple format
        matching kingai_commie_flasher.py ERASE_MAP.
        Returns True on success.
        """
        key = (bank_byte, sector_addr_byte)
        if key not in self.ERASE_MAP:
            log.error("Unknown erase target: bank=0x%02X sector=0x%02X",
                      bank_byte, sector_addr_byte)
            return False

        sector_idx = self.ERASE_MAP[key]
        log.info("Erasing sector %d (bank=0x%02X, sect=0x%02X)",
                 sector_idx, bank_byte, sector_addr_byte)
        return self.flash.erase_sector_by_index(sector_idx)


# ═══════════════════════════════════════════════════════════════════════
# STANDALONE SELF-TEST
# ═══════════════════════════════════════════════════════════════════════

def _self_test():
    """Run a standalone self-test of the flash simulator."""
    # Use setup_logging with console output at INFO for self-test visibility
    test_log = setup_logging(name="vecu.flash.selftest", console_level=logging.INFO)

    print("=== AMD Am29F010 Virtual Flash -- Self-Test ===\n")

    flash = AMD29F010()

    # Test 1: Software ID
    print("Test 1: Software ID read")
    mfg, dev = flash.read_software_id()
    assert mfg == 0x01, f"Manufacturer ID wrong: {mfg:#x}"
    assert dev == 0x20, f"Device ID wrong: {dev:#x}"
    print(f"  Manufacturer: ${mfg:02X} (AMD), Device: ${dev:02X} (Am29F010)  OK\n")

    # Test 2: Erased state
    print("Test 2: Initial erased state")
    for addr in [0x0000, 0x4000, 0x10000, 0x1FFFF]:
        assert flash.read(addr) == 0xFF, f"Address ${addr:05X} not erased"
    print("  All sectors read 0xFF  OK\n")

    # Test 3: Byte programming
    print("Test 3: Byte programming")
    ok = flash.program_byte_at(0x4000, 0x42)
    assert ok, "Program failed"
    assert flash.read(0x4000) == 0x42, "Read-back mismatch"
    print("  Wrote $42 to $4000, read back $42  OK")

    ok = flash.program_byte_at(0x4000, 0xFF)
    assert flash.read(0x4000) == 0x42, "NOR AND rule violated"
    print("  Program $FF (try set bits): still $42  OK\n")

    # Test 4: Sector erase
    print("Test 4: Sector erase")
    flash.program_byte_at(0x4001, 0xAB)
    flash.program_byte_at(0x7FFF, 0xCD)
    assert not flash.verify_sector_erased(1)
    ok = flash.erase_sector_by_index(1)
    assert ok, "Erase failed"
    assert flash.verify_sector_erased(1)
    assert flash.read(0x4000) == 0xFF
    print("  Sector 1 ($4000-$7FFF) erased  OK\n")

    # Test 5: Banked flash
    print("Test 5: Banked flash addressing")
    bf = BankedFlash(flash)
    bf.select_bank(0x48)
    bf.program_byte(0x2000, 0x06)
    bf.program_byte(0x2001, 0x0A)
    assert bf.read(0x2000) == 0x06
    assert bf.read(0x2001) == 0x0A
    print("  Bank 72: wrote OS ID $060A at $2000  OK")

    bf.select_bank(0x58)
    bf.program_byte(0x8000, 0xBE)
    assert flash.read(0x10000) == 0xBE
    print("  Bank 88: $8000 -> flash $10000 = $BE  OK")

    bf.select_bank(0x50)
    bf.program_byte(0xFFFF, 0xEF)
    assert flash.read(0x1FFFF) == 0xEF
    print("  Bank 80: $FFFF -> flash $1FFFF = $EF  OK\n")

    # Test 6: Sector erase via bank
    print("Test 6: Banked sector erase")
    ok = bf.erase_sector(0x58, 0x80)
    assert ok
    assert flash.verify_sector_erased(4)
    print("  Erase bank=0x58 sect=0x80 -> sector 4 erased  OK\n")

    # Test 7: Protect status
    print("Test 7: Protection status")
    status = flash.read_sector_protect_status()
    assert all(s == 0x00 for s in status)
    print(f"  All sectors unprotected: {status}  OK\n")

    print(flash.dump_sector_info())
    print()
    print(flash.dump_stats())
    print("\n=== All tests passed ===")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_self_test())