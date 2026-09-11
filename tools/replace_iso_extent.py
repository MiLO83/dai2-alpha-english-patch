#!/usr/bin/env python3
"""Copy an ISO and replace one same-sized, sector-aligned file extent."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
from pathlib import Path


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("iso", type=Path)
    parser.add_argument("replacement", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--offset", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--expect-sha256")
    args = parser.parse_args()

    replacement = args.replacement.read_bytes()
    if args.offset % 2048:
        parser.error("--offset must be aligned to a 2048-byte ISO sector")
    if args.offset + len(replacement) > args.iso.stat().st_size:
        parser.error("replacement extends beyond the ISO")

    with args.iso.open("rb") as source:
        source.seek(args.offset)
        original = source.read(len(replacement))
    original_hash = digest(original)
    if args.expect_sha256 and original_hash.lower() != args.expect_sha256.lower():
        parser.error(
            f"original extent SHA-256 is {original_hash}, expected {args.expect_sha256}"
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    if shutil.which("cp"):
        subprocess.run(
            ["cp", "--reflink=auto", "--sparse=always", str(args.iso), str(args.output)],
            check=True,
        )
    else:
        shutil.copyfile(args.iso, args.output)
    with args.output.open("r+b") as output:
        output.seek(args.offset)
        output.write(replacement)

    print(f"original extent SHA-256:    {original_hash}")
    print(f"replacement extent SHA-256: {digest(replacement)}")
    print(f"wrote {len(replacement)} bytes at 0x{args.offset:X} in {args.output}")


if __name__ == "__main__":
    main()
