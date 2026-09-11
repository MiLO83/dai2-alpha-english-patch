#!/usr/bin/env python3
"""Extract probable fixed-field CP932 UI strings from the SLPS executable."""

from __future__ import annotations

import argparse
import csv
import re
from collections import OrderedDict
from pathlib import Path


JAPANESE = re.compile(r"[\u3000-\u30ff\u3400-\u9fff\uff01-\uff60]")
HEADERS = ("Original Japanese", "Automatic Translation", "English")
META_HEADERS = (
    "id", "resource", "offset", "source_bytes", "source_hex", "field_bytes", "alignment",
    "source", "status",
)


def printable(text: str) -> bool:
    if not text or not JAPANESE.search(text):
        return False
    if any(ord(c) < 0x20 and c not in "\r\n\t" for c in text):
        return False
    # This game stores its real Japanese UI text as full-width CP932. Half-width
    # katakana in an otherwise kanji-looking suffix is a reliable sign that the
    # scanner started inside binary record metadata rather than at a text field.
    if any("\uff61" <= c <= "\uff9f" for c in text):
        return False
    # Binary MIPS/data runs can accidentally decode as CP932. Real UI fields are
    # overwhelmingly Japanese/ASCII punctuation, not private/control characters.
    return all(c.isprintable() or c in "\r\n\t" for c in text)


def field_end(data: bytes, terminator: int, start: int) -> int:
    """Include NUL padding, stopping on the next likely 8-byte field boundary."""
    cursor = terminator + 1
    limit = min(len(data), start + 0x100)
    while cursor < limit and data[cursor] == 0:
        cursor += 1
    # Fixed UI tables normally align their next item to 8 or 16 bytes. Do not
    # claim unrelated long zero regions as writable capacity.
    natural = (terminator + 8) & ~7
    return min(max(terminator + 1, natural), cursor)


def extract(data: bytes, resource: str, scan_start: int) -> list[dict[str, str | int]]:
    rows: list[dict[str, str | int]] = []
    cursor = scan_start
    while cursor < len(data):
        while cursor < len(data) and data[cursor] == 0:
            cursor += 1
        run_start = cursor
        end = data.find(b"\0", run_start)
        if end < 0:
            break
        cursor = end + 1
        if end == run_start or end - run_start > 0x400:
            continue

        # Structured records often have binary attributes immediately before
        # the text. Test every Japanese-looking suffix and keep the strongest
        # decoding, which also avoids emitting every suffix of the same string.
        choices: list[tuple[int, int, bytes, str]] = []
        for start in range(run_start, end):
            if not (0x81 <= data[start] <= 0x9F or 0xE0 <= data[start] <= 0xEF):
                continue
            raw = data[start:end]
            try:
                text = raw.decode("cp932")
            except UnicodeDecodeError:
                continue
            jp_count = len(JAPANESE.findall(text))
            single_field = (
                start >= 0x330000 and jp_count == 1 and len(text) == 1
                and start == run_start and start % 2 == 0
            )
            if not printable(text) or (jp_count < 2 and not single_field):
                continue
            non_jp = len(text) - jp_count
            choices.append((jp_count * 100 - non_jp, start, raw, text))
        if not choices:
            continue
        _, start, raw, text = max(choices, key=lambda item: (item[0], -item[1]))
        # Reject decoded instruction/data noise containing uncommon control-like
        # Unicode categories. Normal menu strings consist of letters, numbers,
        # Japanese scripts and ordinary punctuation.
        allocated_end = field_end(data, end, start)
        rows.append({
            "id": f"ui-{start:08x}",
            "resource": resource,
            "offset": f"0x{start:X}",
            "source_bytes": len(raw),
            "source_hex": raw.hex().upper(),
            "field_bytes": allocated_end - start - 1,
            "alignment": start & 0xF,
            "source": text,
            "status": "candidate",
        })
    return rows


def read_existing(path: Path) -> dict[str, tuple[str, str]]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source, dialect="excel-tab")
        return {
            row["Original Japanese"]: (
                row.get("Automatic Translation", ""), row.get("English", "")
            )
            for row in reader
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("table", type=Path)
    parser.add_argument("metadata", type=Path)
    parser.add_argument("--reuse", type=Path, help="reuse translations from another three-column TSV")
    parser.add_argument("--scan-start", type=lambda value: int(value, 0), default=0x280000,
                        help="first executable file offset containing game data tables")
    args = parser.parse_args()

    rows = extract(args.executable.read_bytes(), "SLPS_252.28", args.scan_start)
    reused = read_existing(args.reuse) if args.reuse else {}
    unique: OrderedDict[str, None] = OrderedDict()
    for row in rows:
        unique.setdefault(str(row["source"]), None)

    args.table.parent.mkdir(parents=True, exist_ok=True)
    with args.table.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=HEADERS, dialect="excel-tab")
        writer.writeheader()
        for text in unique:
            automatic, english = reused.get(text, ("", ""))
            writer.writerow(dict(zip(HEADERS, (text, automatic, english))))

    args.metadata.parent.mkdir(parents=True, exist_ok=True)
    with args.metadata.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=META_HEADERS, dialect="excel-tab")
        writer.writeheader()
        writer.writerows(rows)

    print(f"extracted {len(rows)} occurrences / {len(unique)} unique UI candidates")
    print(f"reused {sum(text in reused and any(reused[text]) for text in unique)} existing translations")
    print(args.table)
    print(args.metadata)


if __name__ == "__main__":
    main()
