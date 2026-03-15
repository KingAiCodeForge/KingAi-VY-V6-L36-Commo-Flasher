#!/usr/bin/env python3
"""Compare all bin files against the reference Enhanced v1.0a."""
import hashlib, os, sys
os.chdir(os.path.dirname(os.path.abspath(__file__)))

ref_name = 'VX-VY_V6_$060A_Enhanced_v1.0a.bin'
ref = open(ref_name, 'rb').read()
ref_hash = hashlib.sha256(ref).hexdigest()[:16]
print(f'REFERENCE: {ref_name}')
print(f'  SHA256: {ref_hash}  Size: {len(ref)}')
print(f'  Checksum bytes at $4006-$4007: 0x{ref[0x4006]:02X} 0x{ref[0x4007]:02X}')
print()

# 8 sectors of 16KB each
SECTORS = [
    ("Sector 0  $0000-$3FFF (code/bootstrap)", 0x0000, 0x4000),
    ("Sector 1  $4000-$7FFF (calibration)",    0x4000, 0x8000),
    ("Sector 2  $8000-$BFFF (code)",           0x8000, 0xC000),
    ("Sector 3  $C000-$FFFF (code)",           0xC000, 0x10000),
    ("Sector 4  $10000-$13FFF (code)",         0x10000, 0x14000),
    ("Sector 5  $14000-$17FFF (code)",         0x14000, 0x18000),
    ("Sector 6  $18000-$1BFFF (code/OS)",      0x18000, 0x1C000),
    ("Sector 7  $1C000-$1FFFF (vectors/OS)",   0x1C000, 0x20000),
]

bins = sorted([f for f in os.listdir('.') if f.endswith('.bin') and f != ref_name])
for b in bins:
    data = open(b, 'rb').read()
    h = hashlib.sha256(data).hexdigest()[:16]
    match = data == ref
    if match:
        print(f'  {b}')
        print(f'    SHA256: {h}  IDENTICAL')
    else:
        diffs = sum(1 for i in range(min(len(data), len(ref))) if data[i] != ref[i])
        first_diff = next((i for i in range(min(len(data), len(ref))) if data[i] != ref[i]), -1)
        print(f'  {b}')
        print(f'    SHA256: {h}  DIFFERENT  total_diffs={diffs}  first_at=0x{first_diff:05X}')
        if first_diff >= 0:
            print(f'    ref[0x{first_diff:05X}]=0x{ref[first_diff]:02X}  this[0x{first_diff:05X}]=0x{data[first_diff]:02X}')
        # Per-sector breakdown
        for name, start, end in SECTORS:
            sec_diffs = sum(1 for i in range(start, min(end, len(data))) if data[i] != ref[i])
            status = "OK" if sec_diffs == 0 else f"DIFF={sec_diffs}"
            print(f'      {name}: {status}')
    print()
