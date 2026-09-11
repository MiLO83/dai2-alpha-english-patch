#!/usr/bin/env python3
"""Map aligned absolute pointers inside STAGE.BIN MWo3 overlays."""

from __future__ import annotations

import argparse
import csv
import struct
from pathlib import Path


def starts(data: bytes) -> list[int]:
    found: list[int] = []
    cursor = 0
    while (cursor := data.find(b"MWo3", cursor)) >= 0:
        found.append(cursor)
        cursor += 4
    return found


def name(member: bytes) -> str:
    return member[0x20:0x40].split(b"\0", 1)[0].decode("ascii", "replace")


def text_at(member: bytes, offset: int) -> tuple[str, str]:
    end = member.find(b"\0", offset)
    if end < 0:
        return "data", ""
    raw = member[offset:end]
    try:
        text = raw.decode("cp932")
    except UnicodeDecodeError:
        return "data", ""
    if text and all(ord(char) >= 0x20 or char in "\n\r\t" for char in text):
        return "text", text
    return "data", ""


def map_references(data: bytes) -> list[dict[str, str | int]]:
    boundaries = starts(data)
    rows: list[dict[str, str | int]] = []
    for member_number, start in enumerate(boundaries):
        end = boundaries[member_number + 1] if member_number + 1 < len(boundaries) else len(data)
        member = data[start:end]
        if len(member) < 0x20:
            continue
        load = struct.unpack_from("<I", member, 8)[0]
        declared_end = struct.unpack_from("<I", member, 0x18)[0]
        address_end = declared_end if load <= declared_end <= load + len(member) else load + len(member)
        for reference_offset in range(0, len(member) - 3, 4):
            target = struct.unpack_from("<I", member, reference_offset)[0]
            if not load <= target < address_end:
                continue
            target_offset = target - load
            kind, text = text_at(member, target_offset)
            rows.append(
                {
                    "member_number": member_number,
                    "member": name(member),
                    "member_file_offset": f"0x{start:X}",
                    "load_address": f"0x{load:08X}",
                    "declared_end": f"0x{declared_end:08X}",
                    "reference_offset": f"0x{reference_offset:X}",
                    "target_address": f"0x{target:08X}",
                    "target_offset": f"0x{target_offset:X}",
                    "target_kind": kind,
                    "target_text": text,
                }
            )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    rows = map_references(args.stage.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]), dialect="excel-tab")
        writer.writeheader()
        writer.writerows(rows)
    text_count = sum(row["target_kind"] == "text" for row in rows)
    print(f"mapped {len(rows)} aligned pointers ({text_count} text targets) to {args.output}")


if __name__ == "__main__":
    main()
