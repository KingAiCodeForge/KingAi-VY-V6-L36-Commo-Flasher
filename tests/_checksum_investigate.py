#!/usr/bin/env python3
"""Inspect two explicitly supplied images without repairing or writing them."""
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("candidate", type=Path)
    args = parser.parse_args()
    try:
        reference, candidate = args.reference.read_bytes(), args.candidate.read_bytes()
    except OSError as exc:
        parser.exit(1, f"ERROR: {exc}\n")
    if len(reference) < 0x8000 or len(candidate) < 0x8000:
        parser.error("each image must contain the complete calibration area through 0x7FFF")
    for label, data in (("reference", reference), ("candidate", candidate)):
        checksum = int.from_bytes(data[0x4006:0x4008], "big")
        cal_sum = sum(data[0x4008:0x8000])
        print(f"{label}: {len(data)} bytes, stored checksum=0x{checksum:04X}, calibration sum excluding header=0x{cal_sum:X}, full sum=0x{sum(data):X}")
    print(f"Full image sum difference: {sum(candidate) - sum(reference)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
