#!/usr/bin/env python3
"""Append a replacement file extent and retarget one ISO9660 directory record."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import struct
import subprocess
from pathlib import Path


SECTOR = 2048


def both_endian_u32(value: int) -> bytes:
    return struct.pack("<I", value) + struct.pack(">I", value)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("iso", type=Path)
    parser.add_argument("replacement", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--directory-extent", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--iso-name", required=True, help="ISO9660 identifier, including ;1")
    args = parser.parse_args()

    replacement = args.replacement.read_bytes()
    original_size = args.iso.stat().st_size
    if original_size % SECTOR:
        parser.error("source ISO size is not sector aligned")
    new_extent = original_size // SECTOR
    padded_length = (len(replacement) + SECTOR - 1) // SECTOR * SECTOR
    new_volume_sectors = new_extent + padded_length // SECTOR

    directory_offset = args.directory_extent * SECTOR
    with args.iso.open("rb") as source:
        source.seek(directory_offset)
        directory = source.read(SECTOR)
    needle = args.iso_name.encode("ascii")
    name_offset = directory.find(needle)
    if name_offset < 33:
        parser.error(f"could not find {args.iso_name!r} in directory extent")
    record_offset = name_offset - 33
    record_length = directory[record_offset]
    if directory[record_offset + 32] != len(needle):
        parser.error("directory identifier length did not match")
    if directory[record_offset + 33 : record_offset + 33 + len(needle)] != needle:
        parser.error("directory record layout did not match")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    if shutil.which("cp"):
        subprocess.run(
            ["cp", "--reflink=auto", "--sparse=always", str(args.iso), str(args.output)],
            check=True,
        )
    else:
        shutil.copyfile(args.iso, args.output)

    with args.output.open("r+b") as output:
        output.seek(original_size)
        output.write(replacement)
        output.write(b"\0" * (padded_length - len(replacement)))
        # ISO9660 directory record: extent and data length are both-endian u32.
        output.seek(directory_offset + record_offset + 2)
        output.write(both_endian_u32(new_extent))
        output.seek(directory_offset + record_offset + 10)
        output.write(both_endian_u32(len(replacement)))
        # Primary volume descriptor volume-space-size field.
        output.seek(16 * SECTOR + 80)
        output.write(both_endian_u32(new_volume_sectors))

    print(f"directory record: sector {args.directory_extent}, offset 0x{record_offset:X}, length {record_length}")
    print(f"new extent: sector {new_extent} (0x{new_extent * SECTOR:X})")
    print(f"new volume size: {new_volume_sectors} sectors")
    print(f"replacement SHA-256: {hashlib.sha256(replacement).hexdigest()}")


if __name__ == "__main__":
    main()
