#!/usr/bin/env python3
"""Compare explicitly supplied images without modifying their bytes."""
import argparse
import hashlib
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("images", type=Path, nargs="+")
    args = parser.parse_args()
    try:
        reference = args.reference.read_bytes()
        print(f"REFERENCE {args.reference}: {len(reference)} bytes SHA256={hashlib.sha256(reference).hexdigest()}")
        for path in args.images:
            data = path.read_bytes()
            diffs = sum(a != b for a, b in zip(reference, data)) + abs(len(reference) - len(data))
            print(f"{path}: {len(data)} bytes SHA256={hashlib.sha256(data).hexdigest()} differences={diffs}")
            for start in range(0, max(len(reference), len(data)), 0x4000):
                left, right = reference[start:start + 0x4000], data[start:start + 0x4000]
                count = sum(a != b for a, b in zip(left, right)) + abs(len(left) - len(right))
                print(f"  sector {start // 0x4000}: differences={count}, lengths={len(left)}/{len(right)}")
    except OSError as exc:
        parser.exit(1, f"ERROR: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
