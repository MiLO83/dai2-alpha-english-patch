#!/usr/bin/env python3
"""Build a translation ISO by replacing verified same-sized file extents."""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
from pathlib import Path


FILES = {
    "elf": (0xB5000, 3_542_656, "c8079e2abace5df3a3c60a6410cff48ed5514e5b2601aca1b808a59c1f714450"),
    "stage": (0x6EE0B800, 8_484_480, "d3aed6168c7c4d913d641b39ec93e0245811cf737f803866b8b62b1ff9b8ae87"),
    "name": (0x6DF3D800, 10_560, "cd56e5a56739bb341ec10160c390decfee3e61da10bef7ea8e4c5ef9a9ba2967"),
    "font": (0x6DFA8800, 806_400, "123bbf7cdb61ca8adf38eb5f9049dbd3e85a1873821937d9838802f9ddde9cdc"),
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("iso", type=Path); parser.add_argument("output", type=Path)
    parser.add_argument("--elf", type=Path); parser.add_argument("--stage", type=Path); parser.add_argument("--name", type=Path); parser.add_argument("--font", type=Path)
    args = parser.parse_args()
    replacements = [(kind, getattr(args, kind)) for kind in FILES if getattr(args, kind)]
    if not replacements: parser.error("at least one replacement is required")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.iso.open("rb") as source, args.output.open("wb") as target:
        try:
            remaining = args.iso.stat().st_size
            while remaining:
                copied = os.copy_file_range(source.fileno(), target.fileno(), min(remaining, 64 * 1024 * 1024))
                if not copied: raise OSError("short copy_file_range")
                remaining -= copied
        except (AttributeError, OSError):
            source.seek(0); target.seek(0); target.truncate(0)
            shutil.copyfileobj(source, target, 8 * 1024 * 1024)
    with args.iso.open("rb") as source, args.output.open("r+b") as target:
        for kind, path in replacements:
            offset, size, expected = FILES[kind]; replacement = path.read_bytes()
            if len(replacement) != size: parser.error(f"{kind} replacement is {len(replacement)}, expected {size}")
            source.seek(offset); original = source.read(size)
            if digest(original) != expected: parser.error(f"clean ISO {kind} extent hash mismatch")
            target.seek(offset); target.write(replacement)
            print(f"{kind}: {size} bytes at 0x{offset:X}; sha256 {digest(replacement)}")
    print(f"built {args.output} ({args.output.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
