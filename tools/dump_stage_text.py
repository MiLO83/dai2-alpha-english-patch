#!/usr/bin/env python3
"""Extract probable NUL-terminated CP932 strings from STAGE.BIN to TSV."""

from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict
from bisect import bisect_right
from pathlib import Path


MAGIC = b"MWo3"
NAME_OFFSET = 0x20
NAME_SIZE = 0x20
JAPANESE = re.compile(r"[\u3000-\u30ff\u3400-\u9fff\uff01-\uff60]")


def member_starts(data: bytes) -> list[int]:
    starts: list[int] = []
    cursor = 0
    while (cursor := data.find(MAGIC, cursor)) >= 0:
        starts.append(cursor)
        cursor += len(MAGIC)
    return starts


def member_name(data: bytes, start: int) -> str:
    raw = data[start + NAME_OFFSET : start + NAME_OFFSET + NAME_SIZE].split(b"\0", 1)[0]
    return raw.decode("ascii", "replace")


def acceptable(raw: bytes, text: str) -> bool:
    if len(raw) < 4 or len(JAPANESE.findall(text)) < 2:
        return False
    for char in text:
        if ord(char) < 0x20 and char not in "\n\r\t":
            return False
    return True


def extract(data: bytes) -> list[dict[str, str | int]]:
    starts = member_starts(data)
    rows: list[dict[str, str | int]] = []
    cursor = 0
    while cursor < len(data):
        if data[cursor] == 0:
            cursor += 1
            continue
        end = data.find(b"\0", cursor)
        if end < 0:
            break
        raw = data[cursor:end]
        try:
            text = raw.decode("cp932")
        except UnicodeDecodeError:
            cursor = end + 1
            continue
        if cursor % 8 == 0 and acceptable(raw, text):
            allocation_end = end + 1
            while allocation_end < len(data) and data[allocation_end] == 0:
                allocation_end += 1
            member_index = bisect_right(starts, cursor) - 1
            if member_index >= 0:
                start = starts[member_index]
                rows.append(
                    {
                        "id": f"stage-{cursor:08x}",
                        "member": member_name(data, start),
                        "absolute_offset": f"0x{cursor:X}",
                        "member_offset": f"0x{cursor - start:X}",
                        "source_bytes": len(raw),
                        "max_encoded_bytes": allocation_end - cursor - 1,
                        "source": text,
                        "translation": "",
                        "status": "untranslated",
                    }
                )
        cursor = end + 1
    return rows


def unique_rows(rows: list[dict[str, str | int]]) -> list[dict[str, str | int]]:
    occurrences: dict[str, list[dict[str, str | int]]] = defaultdict(list)
    for row in rows:
        occurrences[str(row["source"])].append(row)
    unique: list[dict[str, str | int]] = []
    for number, (source, found) in enumerate(occurrences.items(), 1):
        budgets = [int(row["max_encoded_bytes"]) for row in found]
        unique.append(
            {
                "id": f"text-{number:05d}",
                "occurrences": len(found),
                "min_encoded_bytes": min(budgets),
                "max_encoded_bytes": max(budgets),
                "source": source,
                "translation": "",
                "status": "untranslated",
                "notes": "",
            }
        )
    return unique


def write_tsv(path: Path, rows: list[dict[str, str | int]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields, dialect="excel-tab")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--unique-output", type=Path)
    args = parser.parse_args()

    rows = extract(args.stage.read_bytes())
    write_tsv(args.output, rows)
    print(f"dumped {len(rows)} probable CP932 strings to {args.output}")
    if args.unique_output:
        unique = unique_rows(rows)
        write_tsv(args.unique_output, unique)
        print(f"dumped {len(unique)} unique strings to {args.unique_output}")


if __name__ == "__main__":
    main()
