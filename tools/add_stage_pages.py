#!/usr/bin/env python3
"""Relocate an MWo3 dialogue block and add translated page records."""

from __future__ import annotations

import argparse
import csv
import struct
from pathlib import Path

from dte_codec import encode


def align(value: int, amount: int = 0x80) -> int:
    return (value + amount - 1) & -amount


def starts(data: bytes) -> list[int]:
    result: list[int] = []
    cursor = 0
    while (cursor := data.find(b"MWo3", cursor)) >= 0:
        result.append(cursor)
        cursor += 4
    return result


def name(data: bytes, start: int) -> str:
    return data[start + 0x20 : start + 0x40].split(b"\0", 1)[0].decode("ascii")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", type=Path)
    parser.add_argument("translations", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--member", required=True)
    parser.add_argument("--block-start", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--block-end", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--parent-reference", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--reuse-old-block-for-strings", action="store_true")
    args = parser.parse_args()

    stage = bytearray(args.stage.read_bytes())
    boundaries = starts(stage)
    matches = [offset for offset in boundaries if name(stage, offset) == args.member]
    if len(matches) != 1:
        parser.error(f"expected one {args.member!r}, found {len(matches)}")
    member_start = matches[0]
    number = boundaries.index(member_start)
    member_end = boundaries[number + 1] if number + 1 < len(boundaries) else len(stage)
    member = bytearray(stage[member_start:member_end])
    load = struct.unpack_from("<I", member, 8)[0]

    with args.translations.open(encoding="utf-8", newline="") as source:
        translated = {
            int(row["member_offset"], 0): [
                page.replace("\\n", "\n") for page in row["translation"].split("\\f")
            ]
            for row in csv.DictReader(source, dialect="excel-tab")
        }

    header = member[args.block_start : args.block_start + 8]
    cursor = args.block_start + 8
    records: list[tuple[bytes, int]] = []
    while cursor + 24 <= args.block_end and struct.unpack_from("<I", member, cursor)[0] == 1:
        record = bytes(member[cursor : cursor + 24])
        target = struct.unpack_from("<I", record, 8)[0]
        records.append((record, target - load))
        cursor += 24
    tail = bytes(member[cursor : args.block_end])
    if not records or not tail:
        parser.error("dialogue block layout was not recognized")

    new_block_offset = align(len(member))
    new_records = bytearray()
    strings: list[tuple[int, bytes]] = []
    page_count = 0
    # Reserve block space first; string addresses are assigned after its final size is known.
    expanded: list[tuple[bytes, int, str | None]] = []
    for record, old_offset in records:
        pages = translated.get(old_offset)
        if pages is None:
            expanded.append((record, old_offset, None))
            continue
        for page in pages:
            expanded.append((record, old_offset, page))
            page_count += 1
    block_size = 8 + len(expanded) * 24 + len(tail)
    if args.reuse_old_block_for_strings:
        string_cursor = args.block_start
    else:
        string_cursor = align(new_block_offset + block_size, 8)
    for record, old_offset, page in expanded:
        clone = bytearray(record)
        if page is not None:
            raw, _ = encode(page, {})
            struct.pack_into("<I", clone, 8, load + string_cursor)
            strings.append((string_cursor, raw + b"\0"))
            string_cursor = (string_cursor + len(raw) + 1 + 7) & -8
        new_records.extend(clone)

    if args.reuse_old_block_for_strings:
        if string_cursor > args.block_end:
            parser.error(
                f"translated strings need {string_cursor - args.block_start} bytes, "
                f"old block provides {args.block_end - args.block_start}"
            )
        new_size = align(new_block_offset + block_size)
    else:
        new_size = align(string_cursor)
    member.extend(b"\0" * (new_size - len(member)))
    if args.reuse_old_block_for_strings:
        member[args.block_start : args.block_end] = b"\0" * (args.block_end - args.block_start)
    member[new_block_offset : new_block_offset + 8] = header
    pos = new_block_offset + 8
    member[pos : pos + len(new_records)] = new_records
    pos += len(new_records)
    member[pos : pos + len(tail)] = tail
    for offset, raw in strings:
        member[offset : offset + len(raw)] = raw

    expected_parent = load + args.block_start
    if struct.unpack_from("<I", member, args.parent_reference)[0] != expected_parent:
        parser.error("parent reference does not point to the original block")
    struct.pack_into("<I", member, args.parent_reference, load + new_block_offset)
    growth = len(member) - (member_end - member_start)
    struct.pack_into("<I", member, 0x10, struct.unpack_from("<I", member, 0x10)[0] + growth)
    struct.pack_into("<I", member, 0x18, load + len(member))
    struct.pack_into("<I", member, 0x1C, load + len(member))

    stage[member_start:member_end] = member
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(stage)
    print(f"relocated block 0x{args.block_start:X} -> 0x{new_block_offset:X}")
    print(f"expanded {len(records)} records to {len(expanded)} ({page_count} translated pages)")
    print(f"grew {args.member} and STAGE.BIN by 0x{growth:X} bytes")


if __name__ == "__main__":
    main()
