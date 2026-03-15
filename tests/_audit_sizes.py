#!/usr/bin/env python3
"""Temporary script to audit kernel block sizes."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

# Import just the FlashKernel
# We need to handle potential import errors from PySide6
import importlib
spec = importlib.util.spec_from_file_location("kcf", os.path.join(os.path.dirname(__file__), "kingai_commie_flasher.py"))

# Read the file and extract FlashKernel class manually
with open(os.path.join(os.path.dirname(__file__), "kingai_commie_flasher.py"), "r", encoding="utf-8") as f:
    src = f.read()

# Find and exec just the FlashKernel class
start = src.index("class FlashKernel:")
end = src.index("\nclass ALDLProtocol:")
kernel_src = src[start:end]

ns = {}
exec(kernel_src, ns)
FK = ns["FlashKernel"]

print("=== Kernel Block Sizes ===")
for i, name in enumerate(["EXEC_BLOCK_0", "EXEC_BLOCK_1", "EXEC_BLOCK_2"]):
    blk = getattr(FK, name)
    print(f"\n{name}:")
    print(f"  Array length: {len(blk)} bytes")
    print(f"  frame[0] (device_id): 0x{blk[0]:02X}")
    print(f"  frame[1] (length byte): 0x{blk[1]:02X} = {blk[1]}")
    print(f"  frame[2] (mode): 0x{blk[2]:02X}")
    print(f"  frame[3] (sub-command): 0x{blk[3]:02X}")
    wire = blk[1] - 82
    cs_pos = blk[1] - 83
    payload = len(blk) - 3  # after device_id, length, mode
    kernel_code = len(blk) - 4  # after device_id, length, mode, sub-cmd
    print(f"  Wire length: {wire}")
    print(f"  Checksum position: {cs_pos}")
    print(f"  Payload (incl sub-cmd): {payload}")
    print(f"  Kernel code (excl sub-cmd): {kernel_code}")
    print(f"  Array == cs_pos? {len(blk) == cs_pos}")
    print(f"  Wire == array + 1 (for checksum)? {wire == len(blk) + 1}")

print(f"\n=== Totals ===")
b0, b1, b2 = FK.EXEC_BLOCK_0, FK.EXEC_BLOCK_1, FK.EXEC_BLOCK_2
total_payload = (len(b0)-3) + (len(b1)-3) + (len(b2)-3)
total_kernel = (len(b0)-4) + (len(b1)-4) + (len(b2)-4)
print(f"Total payload (incl sub-cmd): {total_payload}")
print(f"Total kernel code (excl sub-cmd): {total_kernel}")
print(f"Total array bytes: {len(b0) + len(b1) + len(b2)}")

# Check WRITE_BANK kernel byte count value
print(f"\n=== WRITE_BANK analysis ===")
wb = FK.WRITE_BANK
print(f"  WRITE_BANK length: {len(wb)} bytes")
# Find the LDAA #$nn instruction that sets the byte counter
# LDAA immediate = 0x86 followed by the value
for i in range(len(wb)-1):
    if wb[i] == 0x86 and i+2 < len(wb) and wb[i+2] == 0xB7:
        print(f"  LDAA #{wb[i+1]:02X} at offset {i} (byte count = {wb[i+1]})")

print(f"\n=== DEFAULT_WRITE_CHUNK_SIZE check ===")
# Extract from source
idx = src.index("DEFAULT_WRITE_CHUNK_SIZE")
line = src[idx:src.index("\n", idx)]
print(f"  {line.strip()}")

# Check seed/key
idx = src.index("def compute_seed_key")
end_idx = src.index("\n\n", idx)
print(f"\n=== compute_seed_key ===")
print(src[idx:end_idx])

# Check how it's called
idx = src.index("seed_hi = resp[4]")
end_idx = src.index("key = ALDLProtocol.compute_seed_key", idx) + 80
print(f"\n=== seed/key invocation ===")
print(src[idx:end_idx])
