#!/usr/bin/env python3
"""Replace MWo3 strings without moving records, pointers, or file data."""

from __future__ import annotations

import argparse
import csv
import struct
from pathlib import Path

from dte_codec import encode


def member_starts(data: bytes) -> list[int]:
    starts: list[int] = []
    cursor = 0
    while (cursor := data.find(b"MWo3", cursor)) >= 0:
        starts.append(cursor)
        cursor += 4
    return starts


def member_name(data: bytes, start: int) -> str:
    return data[start + 0x20 : start + 0x40].split(b"\0", 1)[0].decode("ascii")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", type=Path)
    parser.add_argument("translations", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--member", required=True)
    args = parser.parse_args()

    stage = bytearray(args.stage.read_bytes())
    starts = member_starts(stage)
    matches = [start for start in starts if member_name(stage, start) == args.member]
    if len(matches) != 1:
        parser.error(f"expected one {args.member!r} member, found {len(matches)}")
    member_start = matches[0]
    member_index = starts.index(member_start)
    member_end = starts[member_index + 1] if member_index + 1 < len(starts) else len(stage)

    with args.translations.open(encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source, dialect="excel-tab"))

    for row in rows:
        offset = int(row["member_offset"], 0)
        allocation = int(row["allocation"], 0)
        text = row["translation"].replace("\\n", "\n")
        raw, _ = encode(text, {})
        if len(raw) + 1 > allocation:
            parser.error(
                f"0x{offset:X}: needs {len(raw) + 1} bytes including NUL, "
                f"allocation is {allocation}"
            )
        absolute = member_start + offset
        if absolute + allocation > member_end:
            parser.error(f"0x{offset:X}: allocation leaves the member")
        old = stage[absolute : absolute + allocation]
        old_nul = old.find(0)
        if old_nul < 0:
            parser.error(f"0x{offset:X}: original slot has no NUL terminator")
        stage[absolute : absolute + allocation] = raw + b"\0" * (allocation - len(raw))
        print(
            f"0x{offset:04X}: {old_nul} original bytes -> "
            f"{len(raw)} translated bytes in 0x{allocation:X}-byte slot"
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(stage)


if __name__ == "__main__":
    main()
