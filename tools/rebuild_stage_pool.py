#!/usr/bin/env python3
"""Relocate translated strings inside one MWo3 overlay and rewrite pointers."""

from __future__ import annotations

import argparse
import csv
import struct
from pathlib import Path

from dte_codec import encode, load_pairs


def align(value: int, amount: int = 8) -> int:
    return (value + amount - 1) & -amount


def member_starts(data: bytes) -> list[int]:
    result: list[int] = []
    cursor = 0
    while (cursor := data.find(b"MWo3", cursor)) >= 0:
        result.append(cursor)
        cursor += 4
    return result


def member_name(data: bytes, start: int) -> str:
    return data[start + 0x20 : start + 0x40].split(b"\0", 1)[0].decode("ascii")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", type=Path)
    parser.add_argument("translations", type=Path)
    parser.add_argument("dte", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--member", required=True)
    parser.add_argument("--pool-start", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--pool-end", type=lambda value: int(value, 0), required=True)
    args = parser.parse_args()

    stage = bytearray(args.stage.read_bytes())
    starts = member_starts(stage)
    matches = [start for start in starts if member_name(stage, start) == args.member]
    if len(matches) != 1:
        parser.error(f"expected one {args.member!r} member, found {len(matches)}")
    start = matches[0]
    end = starts[starts.index(start) + 1] if starts.index(start) + 1 < len(starts) else len(stage)
    member = bytearray(stage[start:end])
    load = struct.unpack_from("<I", member, 8)[0]
    pairs = load_pairs(args.dte)

    with args.translations.open(encoding="utf-8", newline="") as source:
        translations = list(csv.DictReader(source, dialect="excel-tab"))
    pool = bytearray()
    relocated: list[tuple[int, int, int]] = []
    for row in translations:
        old_offset = int(row["member_offset"], 0)
        text = row["translation"].replace("\\n", "\n")
        raw, _ = encode(text, pairs)
        new_offset = args.pool_start + len(pool)
        pool.extend(raw)
        pool.append(0)
        pool.extend(b"\0" * (align(len(pool)) - len(pool)))
        relocated.append((old_offset, new_offset, len(raw)))

    capacity = args.pool_end - args.pool_start
    if len(pool) > capacity:
        parser.error(f"encoded pool needs {len(pool)} bytes, capacity is {capacity}")
    member[args.pool_start : args.pool_end] = b"\0" * capacity
    member[args.pool_start : args.pool_start + len(pool)] = pool

    rewritten = 0
    for old_offset, new_offset, _ in relocated:
        old_address = load + old_offset
        new_address = load + new_offset
        references = 0
        for offset in range(0, len(member) - 3, 4):
            if struct.unpack_from("<I", member, offset)[0] == old_address:
                struct.pack_into("<I", member, offset, new_address)
                references += 1
        if not references:
            parser.error(f"no aligned pointer found for old string at 0x{old_offset:X}")
        rewritten += references

    stage[start:end] = member
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(stage)
    print(f"packed {len(relocated)} strings into {len(pool)}/{capacity} bytes")
    print(f"rewrote {rewritten} absolute pointers in {args.member}")
    for old, new, size in relocated:
        print(f"0x{old:04X} -> 0x{new:04X}: {size} encoded bytes")


if __name__ == "__main__":
    main()
