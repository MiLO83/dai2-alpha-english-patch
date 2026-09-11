#!/usr/bin/env python3
"""Raise PS2 ELF overlay allocations to fit rebuilt MWo3 members."""

from __future__ import annotations

import argparse
import struct
from pathlib import Path


MWO3 = b"MWo3"


def members(data: bytes):
    cursor = 0
    while (cursor := data.find(MWO3, cursor)) >= 0:
        if cursor + 0x40 > len(data):
            break
        fields = struct.unpack_from("<8I", data, cursor)
        name = data[cursor + 0x20:cursor + 0x40].split(b"\0", 1)[0].decode("ascii", "replace")
        yield name, fields
        cursor += 4


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("elf", type=Path)
    parser.add_argument("stage", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    elf = bytearray(args.elf.read_bytes())
    stage = args.stage.read_bytes()
    if elf[:4] != b"\x7fELF" or elf[4:6] != b"\x01\x01":
        parser.error("expected a little-endian ELF32 boot executable")
    phoff = struct.unpack_from("<I", elf, 0x1C)[0]
    phentsize, phnum = struct.unpack_from("<HH", elf, 0x2A)
    if phentsize != 0x20:
        parser.error(f"unexpected program-header size {phentsize}")

    required: dict[int, tuple[int, set[str]]] = {}
    for name, fields in members(stage):
        _, overlay_id, load, text_size, data_size, bss_size, _, _ = fields
        if overlay_id >= phnum:
            parser.error(f"{name}: overlay ID {overlay_id:#x} exceeds ELF phnum {phnum}")
        ram_size = 0x40 + text_size + data_size + bss_size
        offset = phoff + overlay_id * phentsize
        p_type, _, p_vaddr, _, p_filesz, _, _, _ = struct.unpack_from("<8I", elf, offset)
        # Some tiny shared MWo3 records reuse an ID but load at a secondary
        # address. They are not represented by that ID's ELF LOAD entry.
        if p_type != 1 or p_vaddr != load or p_filesz != 0:
            continue
        old = required.get(overlay_id)
        if old is None:
            required[overlay_id] = (ram_size, {name})
        else:
            old_size, names = old
            names.add(name)
            required[overlay_id] = (max(old_size, ram_size), names)

    changed = 0
    for overlay_id, (ram_size, names) in sorted(required.items()):
        offset = phoff + overlay_id * phentsize
        p_memsz = struct.unpack_from("<I", elf, offset + 0x14)[0]
        if ram_size > p_memsz:
            struct.pack_into("<I", elf, offset + 0x14, ram_size)
            print(f"phdr {overlay_id:#04x}: {p_memsz:#x} -> {ram_size:#x} ({', '.join(sorted(names))})")
            changed += 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(elf)
    print(f"patched {changed} overlay allocation(s) in {args.output}")


if __name__ == "__main__":
    main()
