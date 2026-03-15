#!/usr/bin/env python3
"""Investigate the checksum diff at $4006-$4007."""
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

ref = open('VX-VY_V6_$060A_Enhanced_v1.0a.bin','rb').read()
read = open('VX-VY_V6_$060A_Enhanced_v1.0a_read_2.bin','rb').read()

print("=== Header bytes $4000-$4007 ===")
for i in range(0x4000, 0x4008):
    s = 'MATCH' if ref[i]==read[i] else '*** DIFF ***'
    print(f'  [${i:05X}] ref=0x{ref[i]:02X} read=0x{read[i]:02X} {s}')

print()
print("=== Checksum analysis ===")
print(f'  Ref  checksum word at $4006-$4007: 0x{ref[0x4006]:02X}{ref[0x4007]:02X}')
print(f'  Read checksum word at $4006-$4007: 0x{read[0x4006]:02X}{read[0x4007]:02X}')

# Compute cal sum excluding $4000-$4007
ref_sum = sum(ref[i] for i in range(0x4000, 0x8000) if not (0x4000 <= i <= 0x4007))
read_sum = sum(read[i] for i in range(0x4000, 0x8000) if not (0x4000 <= i <= 0x4007))
print(f'  Ref  cal sum (excl header): 0x{ref_sum:04X} ({ref_sum})')
print(f'  Read cal sum (excl header): 0x{read_sum:04X} ({read_sum})')
print(f'  (They should be identical since only $4006-$4007 differ)')

# Try two's complement
ref_cs = (ref[0x4006] << 8) | ref[0x4007]
read_cs = (read[0x4006] << 8) | read[0x4007]
print(f'  Ref  cs word: {ref_cs} (0x{ref_cs:04X})')
print(f'  Read cs word: {read_cs} (0x{read_cs:04X})')

# Full-image sum with ref checksum zeroed vs non-zeroed
full_sum_ref = sum(ref[i] for i in range(len(ref)))
full_sum_read = sum(read[i] for i in range(len(read)))
print(f'  Full image sum ref:  {full_sum_ref} (0x{full_sum_ref:08X})')
print(f'  Full image sum read: {full_sum_read} (0x{full_sum_read:08X})')
print(f'  Difference: {full_sum_read - full_sum_ref}')
