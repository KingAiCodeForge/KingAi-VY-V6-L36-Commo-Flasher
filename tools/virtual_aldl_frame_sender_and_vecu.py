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

The vECU loads a 128KB .bin file as its flash memory and responds to:
    - Mode 1:  Data stream (simulated sensor values)
    - Mode 2:  RAM/flash read (serves real data from loaded bin)
    - Mode 5:  Enter programming mode
    - Mode 6:  Kernel upload (accepts and ACKs)
    - Mode 8:  Silence bus
    - Mode 9:  Unsilence bus
    - Mode 13: Security (seed/key)
    - Mode 16: Flash write data (writes to virtual flash)

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
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════

DEVICE_ID = 0xF7
ALDL_BAUD = 8192
FRAME_SIZE = 201
FLASH_SIZE = 131072  # 128KB

# ALDL Modes
MODE1_DATASTREAM  = 0x01
MODE2_READ_RAM    = 0x02
MODE5_ENTER_PROG  = 0x05
MODE6_UPLOAD      = 0x06
MODE8_SILENCE     = 0x08
MODE9_UNSILENCE   = 0x09
MODE10_WRITE_CAL  = 0x0A
MODE13_SECURITY   = 0x0D
MODE16_FLASH_WRITE = 0x10

# Security
SEED_KEY_MAGIC = 37709
SEED_HI = 0x42
SEED_LO = 0x37


# ═══════════════════════════════════════════════════════════════════════
# ALDL PROTOCOL HELPERS
# ═══════════════════════════════════════════════════════════════════════

def compute_checksum(frame: bytearray, end: int) -> int:
    """Two's complement checksum."""
    return (256 - (sum(frame[:end]) & 0xFF)) & 0xFF


def apply_checksum(frame: bytearray) -> bytearray:
    """Apply checksum at the position indicated by the length byte."""
    cs_pos = frame[1] - 83
    frame[cs_pos] = compute_checksum(frame, cs_pos)
    return frame


def verify_frame(data: bytes) -> bool:
    """Verify an incoming ALDL frame."""
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


# ═══════════════════════════════════════════════════════════════════════
# VIRTUAL ECU
# ═══════════════════════════════════════════════════════════════════════

class VirtualECU:
    """
    Simulates a Delco 68HC11 ECU running OS $060A.

    Loads a 128KB bin file as flash memory and responds to ALDL
    protocol frames just like the real hardware.
    """

    def __init__(self, bin_path: str | None = None, device_id: int = DEVICE_ID):
        self.device_id = device_id
        self.flash = bytearray(FLASH_SIZE)
        self.in_programming = False
        self.kernel_uploaded = False
        self.unlocked = False
        self.silenced = False
        self.write_bank = 0x48
        self.write_addr = 0x0000

        if bin_path and Path(bin_path).exists():
            with open(bin_path, 'rb') as f:
                data = f.read()
            self.flash[:len(data)] = data
            print(f"[vECU] Loaded {len(data)} bytes from {Path(bin_path).name}")
        else:
            print(f"[vECU] Running with blank flash (all 0x00)")

    def process_frame(self, frame: bytes) -> bytes | None:
        """
        Process an incoming ALDL frame and return the response.

        This is the main dispatch — routes to the appropriate mode handler.
        """
        if len(frame) < 3:
            return None

        device_id = frame[0]
        mode = frame[2]

        # Only respond to our device ID (or broadcast)
        if device_id != self.device_id and device_id != 0x00:
            return None

        if mode == MODE8_SILENCE:
            return self._handle_silence()
        elif mode == MODE9_UNSILENCE:
            return self._handle_unsilence()
        elif mode == MODE13_SECURITY:
            return self._handle_security(frame)
        elif mode == MODE5_ENTER_PROG:
            return self._handle_enter_prog()
        elif mode == MODE6_UPLOAD:
            return self._handle_upload(frame)
        elif mode == MODE1_DATASTREAM:
            return self._handle_datastream()
        elif mode == MODE2_READ_RAM:
            return self._handle_read(frame)
        elif mode == MODE16_FLASH_WRITE:
            return self._handle_write(frame)
        else:
            print(f"[vECU] Unknown mode: 0x{mode:02X}")
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

    def _handle_silence(self) -> bytes:
        self.silenced = True
        print("[vECU] Bus silenced (Mode 8)")
        return self._make_ack(MODE8_SILENCE)

    def _handle_unsilence(self) -> bytes:
        self.silenced = False
        print("[vECU] Bus unsilenced (Mode 9)")
        return self._make_ack(MODE9_UNSILENCE)

    def _handle_security(self, frame: bytes) -> bytes:
        """Handle Mode 13 seed/key security."""
        submode = frame[3] if len(frame) > 3 else 0

        if submode == 0x01:
            # Seed request
            print(f"[vECU] Seed request — sending 0x{SEED_HI:02X} 0x{SEED_LO:02X}")
            return self._make_ack(MODE13_SECURITY, bytes([0x01, SEED_HI, SEED_LO]))
        elif submode == 0x02:
            # Key response — accept any key
            self.unlocked = True
            print("[vECU] Security unlocked")
            return self._make_ack(MODE13_SECURITY, bytes([0x02]))
        return None

    def _handle_enter_prog(self) -> bytes:
        self.in_programming = True
        print("[vECU] Entered programming mode (Mode 5)")
        return self._make_ack(MODE5_ENTER_PROG)

    def _handle_upload(self, frame: bytes) -> bytes:
        """Handle Mode 6 kernel upload — ACK each block."""
        self.kernel_uploaded = True
        print(f"[vECU] Kernel upload block received (Mode 6)")
        return self._make_ack(MODE6_UPLOAD, bytes([0xAA]))

    def _handle_datastream(self) -> bytes:
        """Return simulated Mode 1 sensor data (60 bytes)."""
        data = bytearray(60)
        data[0] = 32     # RPM high byte (32*256+0 = 8192 counts → ~800 RPM)
        data[1] = 0      # RPM low byte
        data[2] = 140    # Coolant temp (140-40 = 100°F → ~50°C)
        data[3] = 14     # Battery voltage (14 * 0.1 = 14.0V approx)
        data[4] = 25     # TPS (25/255 * 100 ≈ 10%)
        data[5] = 128    # O2 sensor (~0.45V, stoich)
        data[6] = 128    # Short term fuel trim (128 = 0% correction)
        data[7] = 128    # Long term fuel trim (128 = 0% correction)

        resp = bytearray(FRAME_SIZE)
        resp[0] = self.device_id
        resp[1] = 0x56 + len(data)
        resp[2] = MODE1_DATASTREAM
        resp[3:3 + len(data)] = data
        apply_checksum(resp)
        wire_len = frame_wire_length(resp)
        return bytes(resp[:wire_len])

    def _handle_read(self, frame: bytes) -> bytes:
        """Handle Mode 2 RAM read — serve data from loaded bin."""
        if frame[1] == 0x59:
            addr = (frame[3] << 16) | (frame[4] << 8) | frame[5]
        else:
            addr = (frame[3] << 8) | frame[4]

        end = min(addr + 64, FLASH_SIZE)
        block = self.flash[addr:end]
        if len(block) < 64:
            block = block + bytes(64 - len(block))

        resp = bytearray(FRAME_SIZE)
        resp[0] = self.device_id
        resp[1] = 0x55 + len(block) + 1
        resp[2] = MODE2_READ_RAM
        resp[3:3 + len(block)] = block
        apply_checksum(resp)
        wire_len = frame_wire_length(resp)
        print(f"[vECU] Read ${addr:05X}: {hex_str(block[:16])}...")
        return bytes(resp[:wire_len])

    def _handle_write(self, frame: bytes) -> bytes:
        """Handle Mode 16 flash write data."""
        # Extract 3-byte address + 32 bytes data from frame
        if len(frame) > 38:
            addr = (frame[3] << 16) | (frame[4] << 8) | frame[5]
            data = frame[6:6 + 32]
            end = min(addr + len(data), FLASH_SIZE)
            self.flash[addr:end] = data[:end - addr]
            print(f"[vECU] Write ${addr:05X}: {len(data)} bytes")

        return self._make_ack(MODE16_FLASH_WRITE, bytes([0xAA]))


# ═══════════════════════════════════════════════════════════════════════
# TCP SERVER (for vECU mode)
# ═══════════════════════════════════════════════════════════════════════

def run_vecu_tcp(vecu: VirtualECU, host: str = "127.0.0.1", port: int = 8192):
    """Run the virtual ECU as a TCP server."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(1)
    print(f"[vECU] TCP server listening on {host}:{port}")
    print(f"[vECU] Connect with: socat PTY,link=/dev/ttyVECU TCP:{host}:{port}")
    print(f"[vECU] Or use a virtual COM port bridge on Windows")

    try:
        while True:
            conn, addr = server.accept()
            print(f"[vECU] Client connected from {addr}")
            handle_client(vecu, conn)
    except KeyboardInterrupt:
        print("\n[vECU] Shutting down")
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

                print(f"[vECU] RX: {hex_str(frame[:min(len(frame), 20)])}...")

                resp = vecu.process_frame(frame)
                if resp:
                    conn.sendall(resp)
                    print(f"[vECU] TX: {hex_str(resp[:min(len(resp), 20)])}...")
    except (ConnectionResetError, BrokenPipeError):
        print("[vECU] Client disconnected")
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
    print(f"    silence    → Mode 8 silence bus")
    print(f"    unsilence  → Mode 9 unsilence bus")
    print(f"    seed       → Mode 13 seed request")
    print(f"    read ADDR  → Mode 2 read at hex address")
    print(f"    quit       → Exit")
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
        elif line.lower().startswith('read '):
            addr_str = line.split()[1]
            addr = int(addr_str, 16)
            hi = (addr >> 8) & 0xFF
            lo = addr & 0xFF
            line = f'{DEVICE_ID:02X} 58 02 {hi:02X} {lo:02X}'

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
  # Start virtual ECU with stock bin
  python virtual_aldl_frame_sender_and_vecu.py --mode vecu --bin stock.bin

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
    args = parser.parse_args()

    if args.mode == "vecu":
        vecu = VirtualECU(bin_path=args.bin, device_id=DEVICE_ID)
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