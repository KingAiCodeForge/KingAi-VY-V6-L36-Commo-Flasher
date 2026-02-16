#!/usr/bin/env python3
"""
ALDL_read_RAM_commands.py — Standalone ALDL RAM Reader
=======================================================

Standalone tool for reading RAM/flash memory from a Delco 68HC11 ECU
via the ALDL protocol (8192 baud, half-duplex serial).

This is a lightweight version of the read functionality in kingai_commie_flasher.py,
useful for quick reads, debugging, and protocol testing without the full GUI.

Usage:
    # Read 64 bytes at address $77C0 (calibration area — rev limiter region)
    python ALDL_read_RAM_commands.py --port COM3 --address 0x77C0

    # Read 64 bytes with extended 3-byte addressing (for kernel/bank reads)
    python ALDL_read_RAM_commands.py --port COM3 --address 0x18000 --extended

    # Read multiple consecutive blocks and dump to file
    python ALDL_read_RAM_commands.py --port COM3 --address 0x4000 --count 256 --output cal_dump.bin

    # Silence bus first, then read (recommended for noisy bus)
    python ALDL_read_RAM_commands.py --port COM3 --address 0x77C0 --silence

    # Use loopback transport (virtual ECU) for testing
    python ALDL_read_RAM_commands.py --loopback --address 0x77C0

Target: Holden VY Ecotec V6 — Delco 68HC11F1, OS $060A (92118883)
Protocol: ALDL 8192 baud, device ID 0xF7

MIT License — Copyright (c) 2026 Jason King (pcmhacking.net: kingaustraliagg)
"""

from __future__ import annotations
import sys
import time
import argparse
import struct
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════

# Device IDs
DEVICE_VX_VY = 0xF7
DEVICE_VS_VT = 0xF5
DEVICE_VR    = 0xF4

# ALDL modes
MODE1_DATASTREAM  = 0x01
MODE2_READ_RAM    = 0x02
MODE8_SILENCE     = 0x08
MODE9_UNSILENCE   = 0x09

# Protocol constants
ALDL_BAUD = 8192
ALDL_LENGTH_OFFSET = 85    # payload_length = frame[1] - 85
READ_BLOCK_SIZE = 64       # Mode 2 returns 64 bytes per read
FRAME_SIZE = 201           # Fixed frame buffer size
DEFAULT_TIMEOUT = 2.0      # seconds
ECHO_TIMEOUT = 0.5         # seconds


# ═══════════════════════════════════════════════════════════════════════
# ALDL FRAME BUILDING
# ═══════════════════════════════════════════════════════════════════════

def compute_checksum(frame: bytearray) -> int:
    """Compute ALDL checksum: two's complement of sum of all bytes mod 256."""
    return (256 - (sum(frame[:-1]) & 0xFF)) & 0xFF


def apply_checksum(frame: bytearray) -> None:
    """Apply checksum to the last byte of the frame."""
    cs_pos = frame[1] - 83  # checksum position from length byte
    frame[cs_pos] = compute_checksum(frame[:cs_pos])


def verify_checksum(frame: bytes) -> bool:
    """Verify ALDL frame checksum."""
    if len(frame) < 3:
        return False
    cs_pos = frame[1] - 83
    if cs_pos < 3 or cs_pos >= len(frame):
        return False
    expected = compute_checksum(bytearray(frame[:cs_pos]))
    return frame[cs_pos] == expected


def build_mode2_read(device_id: int, address: int, extended: bool = False) -> bytearray:
    """
    Build an ALDL Mode 2 RAM read request.

    Standard (2-byte address): reads 64 bytes at 16-bit address ($0000-$FFFF)
    Extended (3-byte address): reads 64 bytes at 24-bit address (for bank reads)

    Frame format:
        [device_id, length_byte, 0x02, addr_hi, addr_lo, ..., checksum]
    """
    frame = bytearray(FRAME_SIZE)
    frame[0] = device_id
    if extended:
        frame[1] = 0x59  # length = 89
        frame[2] = MODE2_READ_RAM
        frame[3] = (address >> 16) & 0xFF  # bank byte
        frame[4] = (address >> 8) & 0xFF   # addr high
        frame[5] = address & 0xFF          # addr low
    else:
        frame[1] = 0x58  # length = 88
        frame[2] = MODE2_READ_RAM
        frame[3] = (address >> 8) & 0xFF
        frame[4] = address & 0xFF
    apply_checksum(frame)
    return frame


def build_silence_frame(device_id: int) -> bytearray:
    """Build Mode 8 silence (disable chatter) frame."""
    frame = bytearray(FRAME_SIZE)
    frame[0] = device_id
    frame[1] = 0x56
    frame[2] = MODE8_SILENCE
    apply_checksum(frame)
    return frame


def build_unsilence_frame(device_id: int) -> bytearray:
    """Build Mode 9 unsilence (re-enable chatter) frame."""
    frame = bytearray(FRAME_SIZE)
    frame[0] = device_id
    frame[1] = 0x56
    frame[2] = MODE9_UNSILENCE
    apply_checksum(frame)
    return frame


# ═══════════════════════════════════════════════════════════════════════
# SERIAL TRANSPORT
# ═══════════════════════════════════════════════════════════════════════

class ALDLSerial:
    """Minimal ALDL serial transport for Mode 2 reads."""

    def __init__(self, port: str, baud: int = ALDL_BAUD, device_id: int = DEVICE_VX_VY):
        self.port = port
        self.baud = baud
        self.device_id = device_id
        self._serial = None

    def open(self):
        """Open the serial port."""
        try:
            import serial
        except ImportError:
            print("ERROR: pyserial not installed. Run: pip install pyserial")
            sys.exit(1)

        self._serial = serial.Serial(
            port=self.port,
            baudrate=self.baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=DEFAULT_TIMEOUT,
        )
        # Flush any stale data
        self._serial.reset_input_buffer()
        self._serial.reset_output_buffer()

    def close(self):
        """Close the serial port."""
        if self._serial and self._serial.is_open:
            self._serial.close()

    def transact(self, frame: bytearray, timeout: float = DEFAULT_TIMEOUT) -> bytes | None:
        """
        Send an ALDL frame and receive the response.

        Handles echo detection (half-duplex — we receive our own TX bytes back)
        and response timeout.
        """
        if not self._serial:
            return None

        # Calculate actual wire bytes to send (up to checksum position + 1)
        wire_len = frame[1] - 82  # actual bytes on wire
        tx_data = bytes(frame[:wire_len])

        self._serial.reset_input_buffer()
        self._serial.write(tx_data)
        self._serial.flush()

        # Consume echo (half-duplex ALDL echoes back our TX)
        echo_deadline = time.time() + ECHO_TIMEOUT
        echo_buf = bytearray()
        while len(echo_buf) < len(tx_data) and time.time() < echo_deadline:
            remaining = len(tx_data) - len(echo_buf)
            chunk = self._serial.read(remaining)
            if chunk:
                echo_buf.extend(chunk)

        # Wait for response
        self._serial.timeout = timeout
        # Read first 3 bytes (device_id, length, mode)
        header = self._serial.read(3)
        if len(header) < 3:
            return None

        # Calculate response length from length byte
        resp_wire_len = header[1] - 82
        remaining = resp_wire_len - 3
        if remaining < 0 or remaining > 200:
            return None

        body = self._serial.read(remaining)
        if len(body) < remaining:
            return None

        response = bytes(header) + bytes(body)

        # Verify checksum
        if not verify_checksum(response):
            print(f"  WARNING: Bad checksum on response")
            return None

        return response


class LoopbackALDL:
    """
    Loopback transport for testing without hardware.
    Loads a .bin file and serves Mode 2 reads from it.
    """

    def __init__(self, bin_path: str | None = None, device_id: int = DEVICE_VX_VY):
        self.device_id = device_id
        self.flash = bytearray(131072)  # 128KB zeroed
        if bin_path and Path(bin_path).exists():
            with open(bin_path, 'rb') as f:
                data = f.read()
            self.flash[:len(data)] = data
            print(f"  Loaded {len(data)} bytes from {bin_path}")

    def open(self):
        pass

    def close(self):
        pass

    def transact(self, frame: bytearray, timeout: float = DEFAULT_TIMEOUT) -> bytes | None:
        """Simulate ECU response for Mode 2 reads."""
        mode = frame[2]

        if mode == MODE8_SILENCE or mode == MODE9_UNSILENCE:
            resp = bytearray([self.device_id, 0x56, mode])
            apply_checksum(resp)
            return bytes(resp)

        if mode == MODE2_READ_RAM:
            # Extract address
            if frame[1] == 0x59:  # extended 3-byte
                addr = (frame[3] << 16) | (frame[4] << 8) | frame[5]
            else:  # standard 2-byte
                addr = (frame[3] << 8) | frame[4]

            # Read 64 bytes from simulated flash
            end = min(addr + READ_BLOCK_SIZE, len(self.flash))
            block = self.flash[addr:end]
            if len(block) < READ_BLOCK_SIZE:
                block = block + bytes(READ_BLOCK_SIZE - len(block))

            resp = bytearray(FRAME_SIZE)
            resp[0] = self.device_id
            resp[1] = 0x55 + len(block) + 1  # length encoding
            resp[2] = MODE2_READ_RAM
            resp[3:3 + len(block)] = block
            apply_checksum(resp)
            return bytes(resp)

        return None


# ═══════════════════════════════════════════════════════════════════════
# READ OPERATIONS
# ═══════════════════════════════════════════════════════════════════════

def read_ram(transport, address: int, extended: bool = False, device_id: int = DEVICE_VX_VY) -> bytes | None:
    """
    Read 64 bytes from ECU at the given address via Mode 2.

    Returns the data payload (64 bytes) or None on failure.
    """
    frame = build_mode2_read(device_id, address, extended)
    resp = transport.transact(frame)

    if resp is None:
        return None

    if resp[2] != MODE2_READ_RAM:
        print(f"  Unexpected mode in response: 0x{resp[2]:02X}")
        return None

    # Extract data: starts at byte 3, length = resp[1] - 85 - 1
    data_len = resp[1] - ALDL_LENGTH_OFFSET - 1
    if data_len <= 0:
        return None

    return bytes(resp[3:3 + data_len])


def read_range(transport, start: int, length: int, extended: bool = False,
               device_id: int = DEVICE_VX_VY) -> bytearray | None:
    """
    Read a range of bytes by issuing multiple Mode 2 reads.

    Args:
        start:    Starting address
        length:   Total bytes to read
        extended: Use 3-byte addressing
        device_id: ALDL device ID

    Returns:
        bytearray of all read data, or None on failure
    """
    result = bytearray()
    addr = start
    total_blocks = (length + READ_BLOCK_SIZE - 1) // READ_BLOCK_SIZE

    for i in range(total_blocks):
        remaining = length - len(result)
        data = read_ram(transport, addr, extended, device_id)
        if data is None:
            print(f"  Read failed at ${addr:04X} (block {i+1}/{total_blocks})")
            return None

        take = min(len(data), remaining)
        result.extend(data[:take])
        addr += READ_BLOCK_SIZE

        # Progress
        pct = (i + 1) * 100 // total_blocks
        print(f"\r  Reading: ${start:05X}-${start+length-1:05X}  [{pct:3d}%]  {len(result)}/{length} bytes", end="")

    print()  # newline after progress
    return result


def silence_bus(transport, device_id: int = DEVICE_VX_VY) -> bool:
    """Send Mode 8 silence to BCM and ECM to reduce bus noise."""
    # Silence BCM first (device 0xF1), then ECM
    for did in [0xF1, device_id]:
        frame = build_silence_frame(did)
        resp = transport.transact(frame, timeout=2.0)
        if resp is None:
            print(f"  Warning: No response to silence from device 0x{did:02X}")
    return True


def unsilence_bus(transport, device_id: int = DEVICE_VX_VY) -> bool:
    """Send Mode 9 to re-enable normal bus traffic."""
    frame = build_unsilence_frame(device_id)
    resp = transport.transact(frame, timeout=2.0)
    return resp is not None


# ═══════════════════════════════════════════════════════════════════════
# DISPLAY HELPERS
# ═══════════════════════════════════════════════════════════════════════

def hex_dump(data: bytes, base_addr: int = 0, width: int = 16) -> str:
    """Format data as a hex dump with addresses and ASCII."""
    lines = []
    for i in range(0, len(data), width):
        addr = base_addr + i
        chunk = data[i:i + width]
        hex_part = ' '.join(f'{b:02X}' for b in chunk)
        ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        lines.append(f"  ${addr:05X}: {hex_part:<{width*3}}  {ascii_part}")
    return '\n'.join(lines)


# ═══════════════════════════════════════════════════════════════════════
# VY V6 KNOWN ADDRESSES (for quick reference)
# ═══════════════════════════════════════════════════════════════════════

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
# MAIN
# ═══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="ALDL RAM Reader — Read memory from Delco 68HC11 ECU via ALDL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Read 64 bytes at the rev limiter area
  python ALDL_read_RAM_commands.py --port COM3 --address 0x77C0

  # Read 256 bytes of calibration data and save to file
  python ALDL_read_RAM_commands.py --port COM3 --address 0x4000 --count 256 --output cal.bin

  # Read vector table (extended addressing)
  python ALDL_read_RAM_commands.py --port COM3 --address 0x1FFE0 --extended

  # Test with loopback (no hardware needed)
  python ALDL_read_RAM_commands.py --loopback --address 0x77C0

  # Test with a real bin file as virtual ECU
  python ALDL_read_RAM_commands.py --loopback --bin-file stock.bin --address 0x77DE

Known VY V6 addresses:
  $4000         Calibration area start
  $4006-$4007   16-bit checksum
  $50FE         Mode 1 data stream definition table
  $77DE-$77DF   Rev limiter (RPM = byte * 25)
  $1FFE0        Vector table (extended addressing)
  $1FFFE-$1FFFF RESET vector (extended addressing)
        """,
    )
    parser.add_argument("--port", type=str, default="COM3", help="Serial port (default: COM3)")
    parser.add_argument("--baud", type=int, default=ALDL_BAUD, help=f"Baud rate (default: {ALDL_BAUD})")
    parser.add_argument("--device-id", type=str, default="0xF7",
                        help="ECU device ID in hex (default: 0xF7 for VX/VY)")
    parser.add_argument("--address", type=str, required=True,
                        help="Start address in hex (e.g., 0x77C0 or 0x4000)")
    parser.add_argument("--count", type=int, default=64,
                        help="Number of bytes to read (default: 64, rounded up to 64-byte blocks)")
    parser.add_argument("--extended", action="store_true",
                        help="Use 3-byte extended addressing (for addresses > 0xFFFF)")
    parser.add_argument("--silence", action="store_true",
                        help="Send Mode 8 silence before reading")
    parser.add_argument("--output", type=str, default=None,
                        help="Save raw bytes to output file")
    parser.add_argument("--loopback", action="store_true",
                        help="Use loopback transport (no hardware needed)")
    parser.add_argument("--bin-file", type=str, default=None,
                        help="Load a .bin file into loopback virtual ECU")
    parser.add_argument("--no-hexdump", action="store_true",
                        help="Suppress hex dump output (useful with --output)")
    args = parser.parse_args()

    # Parse hex values
    device_id = int(args.device_id, 16)
    address = int(args.address, 16)
    extended = args.extended or address > 0xFFFF

    print(f"ALDL RAM Reader — Delco 68HC11 ($060A)")
    print(f"  Address:   ${address:05X}")
    print(f"  Count:     {args.count} bytes")
    print(f"  Extended:  {extended}")
    print(f"  Device ID: 0x{device_id:02X}")
    print()

    # Look up known address
    if address in KNOWN_ADDRESSES:
        print(f"  Known: {KNOWN_ADDRESSES[address]}")
        print()

    # Set up transport
    if args.loopback:
        print("  Transport: Loopback (Virtual ECU)")
        transport = LoopbackALDL(bin_path=args.bin_file, device_id=device_id)
    else:
        print(f"  Transport: Serial ({args.port} @ {args.baud} baud)")
        transport = ALDLSerial(args.port, args.baud, device_id)

    transport.open()

    try:
        # Optionally silence the bus
        if args.silence and not args.loopback:
            print("  Silencing bus (Mode 8)...")
            silence_bus(transport, device_id)
            time.sleep(0.1)

        # Read
        if args.count <= READ_BLOCK_SIZE:
            # Single block read
            data = read_ram(transport, address, extended, device_id)
        else:
            # Multi-block read
            data = read_range(transport, address, args.count, extended, device_id)

        if data is None:
            print("  ERROR: Read failed — no response from ECU")
            sys.exit(1)

        print(f"  Read {len(data)} bytes at ${address:05X}")
        print()

        # Display hex dump
        if not args.no_hexdump:
            print(hex_dump(data, address))
            print()

        # Show VY V6 specific info for known addresses
        if address <= 0x77DE <= address + len(data):
            offset = 0x77DE - address
            if offset + 1 < len(data):
                rev_hi = data[offset]
                rev_lo = data[offset + 1]
                print(f"  Rev Limiter: {rev_hi * 25} / {rev_lo * 25} RPM (high/low)")
                print()

        if address <= 0x4006 <= address + len(data):
            offset = 0x4006 - address
            if offset + 1 < len(data):
                cs = (data[offset] << 8) | data[offset + 1]
                print(f"  Checksum at $4006: 0x{cs:04X}")
                print()

        # Save to file
        if args.output:
            with open(args.output, 'wb') as f:
                f.write(data)
            print(f"  Saved to {args.output}")

        # Re-enable bus traffic
        if args.silence and not args.loopback:
            print("  Re-enabling bus traffic (Mode 9)...")
            unsilence_bus(transport, device_id)

    finally:
        transport.close()


if __name__ == "__main__":
    main()
