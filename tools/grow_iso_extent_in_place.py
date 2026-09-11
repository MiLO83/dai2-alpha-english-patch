#!/usr/bin/env python3
"""Grow an ISO9660 file inside its existing sector allocation."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import struct
import subprocess
from pathlib import Path


SECTOR = 2048


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("iso", type=Path)
    parser.add_argument("replacement", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--offset", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--original-size", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--expect-sha256", required=True)
    parser.add_argument("--directory-extent", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--iso-name", required=True)
    args = parser.parse_args()

    replacement = args.replacement.read_bytes()
    allocation = (args.original_size + SECTOR - 1) // SECTOR * SECTOR
    if len(replacement) > allocation:
        parser.error(f"replacement needs {len(replacement)} bytes; allocation is {allocation}")
    with args.iso.open("rb") as source:
        source.seek(args.offset)
        original = source.read(args.original_size)
    digest = hashlib.sha256(original).hexdigest()
    if digest.lower() != args.expect_sha256.lower():
        parser.error(f"original SHA-256 is {digest}, expected {args.expect_sha256}")

    directory_offset = args.directory_extent * SECTOR
    with args.iso.open("rb") as source:
        source.seek(directory_offset)
        directory = source.read(SECTOR)
    needle = args.iso_name.encode("ascii")
    name_offset = directory.find(needle)
    if name_offset < 33:
        parser.error("ISO9660 directory record was not found")
    record_offset = name_offset - 33
    old_extent = struct.unpack_from("<I", directory, record_offset + 2)[0]
    if old_extent * SECTOR != args.offset:
        parser.error("directory extent does not match --offset")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    if shutil.which("cp"):
        subprocess.run(["cp", "--reflink=auto", "--sparse=always", str(args.iso), str(args.output)], check=True)
    else:
        shutil.copyfile(args.iso, args.output)
    with args.output.open("r+b") as output:
        output.seek(args.offset)
        output.write(replacement)
        output.write(b"\0" * (allocation - len(replacement)))
        output.seek(directory_offset + record_offset + 10)
        output.write(struct.pack("<I", len(replacement)))
        output.write(struct.pack(">I", len(replacement)))
    print(f"grew {args.iso_name} from {args.original_size} to {len(replacement)} bytes")
    print(f"used {len(replacement)}/{allocation} bytes in the existing extent")


if __name__ == "__main__":
    main()
