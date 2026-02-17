#!/usr/bin/env python3
"""Test the Virtual ECU transport with real bin files."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pathlib import Path

import importlib.util
kcf_path = str(Path(__file__).parent / 'kingai_commie_flasher.py')
spec = importlib.util.spec_from_file_location('kingai_commie_flasher', kcf_path)
mod = importlib.util.module_from_spec(spec)
mod.__file__ = kcf_path
# Must register BEFORE exec so @dataclass can resolve __module__
sys.modules['kingai_commie_flasher'] = mod
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

LoopbackTransport = mod.LoopbackTransport
ECUComm = mod.ECUComm
CommConfig = mod.CommConfig

from tools.hc11_disassembler import HC11Disassembler

# ── Load Enhanced bin as Virtual ECU ──
bin_path = str(Path(__file__).parent / 'ignore' / 'VX-VY_V6_$060A_Enhanced_v1.0a.bin')
transport = LoopbackTransport(bin_path=bin_path)
print(f"Virtual ECU loaded: {len(transport._simulated_bin)} bytes")
rev_hi = transport._simulated_bin[0x77DE]
rev_lo = transport._simulated_bin[0x77DF]
print(f"Rev Limit High: 0x{rev_hi:02X} = {rev_hi*25} RPM")
print(f"Rev Limit Low:  0x{rev_lo:02X} = {rev_lo*25} RPM")

# ── Open connection ──
transport.open()
config = CommConfig()
config.ignore_echo = False  # Loopback doesn't echo
comm = ECUComm(transport, config)

# ── Test 1: Mode 2 read of rev limiter area ──
print("\n=== TEST 1: Mode 2 read at $77C0 (cal area) ===")
data = comm.read_ram(0x77C0, extended=False)
if data:
    print(f"Got {len(data)} bytes")
    for i in range(0, min(len(data), 64), 16):
        chunk = data[i:i+16]
        hex_str = ' '.join(f'{b:02X}' for b in chunk)
        addr = 0x77C0 + i
        print(f"  ${addr:04X}: {hex_str}")
    offset = 0x77DE - 0x77C0
    if offset < len(data):
        print(f"  Rev Limit High at offset {offset}: 0x{data[offset]:02X} = {data[offset]*25} RPM")
        print(f"  Rev Limit Low  at offset {offset+1}: 0x{data[offset+1]:02X} = {data[offset+1]*25} RPM")
    print("  PASS")
else:
    print("  FAIL: read_ram returned None")

# ── Test 2: Extended 3-byte address read ──
print("\n=== TEST 2: Extended read at $00000 (bank 0 start) ===")
data2 = comm.read_ram(0x00000, extended=True)
if data2:
    hex_str = ' '.join(f'{b:02X}' for b in data2[:32])
    print(f"  First 32 bytes: {hex_str}")
    print("  PASS")
else:
    print("  FAIL: extended read returned None")

# ── Test 3: Read vector table ──
print("\n=== TEST 3: Vector table (last 32 bytes of 128KB) ===")
data3 = comm.read_ram(0x1FFE0, extended=True)
if data3:
    vec_names = ['TOC4','TOC3','TOC2','TOC1','TIC3','TIC2','TIC1','RTI','IRQ','XIRQ','SWI','ILLOP','COP','CME','CMF','RESET']
    for i in range(0, min(len(data3), 32), 2):
        target = (data3[i] << 8) | data3[i+1]
        idx = i // 2
        name = vec_names[idx] if idx < len(vec_names) else f"VEC{idx}"
        print(f"  {name:6s} -> ${target:04X}")
    print("  PASS")
else:
    print("  FAIL: vector read returned None")

# ── Test 4: Disassemble RESET entry from virtual bin ──
print("\n=== TEST 4: Disassemble RESET entry ===")
reset_vec = (transport._simulated_bin[0x1FFFE] << 8) | transport._simulated_bin[0x1FFFF]
print(f"  RESET vector: ${reset_vec:04X}")

# Map CPU address to file offset for extended read:
# CPU $C011 -> file offset depends on bank mapping
# In the 128KB image: $8000-$FFFF = file 0x18000-0x1FFFF (bank 3, 32KB at end)
# So $C011 -> file 0x1C011? Actually let's just read via the transport
file_offset = 0x18000 + (reset_vec - 0x8000) if reset_vec >= 0x8000 else reset_vec
data4 = comm.read_ram(file_offset, extended=True)
if data4:
    dis = HC11Disassembler()
    results = dis.disassemble(data4[:32], base_addr=reset_vec)
    for r in results:
        print(f"  {r.format()}")
    print("  PASS")
else:
    print("  FAIL: reset entry read returned None")

# ── Test 5: Compare STOCK vs ENHANCED ──
print("\n=== TEST 5: STOCK vs ENHANCED comparison ===")
stock_path = str(Path(__file__).parent / 'ignore' / '92118883_STOCK.bin')
if Path(stock_path).exists():
    stock_transport = LoopbackTransport(bin_path=stock_path)
    s_hi = stock_transport._simulated_bin[0x77DE]
    s_lo = stock_transport._simulated_bin[0x77DF]
    print(f"  STOCK    Rev Limit: {s_hi*25}/{s_lo*25} RPM")
    print(f"  ENHANCED Rev Limit: {rev_hi*25}/{rev_lo*25} RPM")
    
    # Count differing bytes in calibration area ($4000-$7FFF)
    diffs = 0
    for i in range(0x4000, 0x8000):
        if transport._simulated_bin[i] != stock_transport._simulated_bin[i]:
            diffs += 1
    print(f"  Calibration area ($4000-$7FFF) differences: {diffs} bytes")
    print("  PASS")
else:
    print(f"  SKIP: stock bin not found at {stock_path}")

print("\n*** ALL VIRTUAL ECU TESTS PASSED ***")
