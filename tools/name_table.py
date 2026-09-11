#!/usr/bin/env python3
"""Dump or rebuild NAME.BIN's fixed 0x40-byte CP932 records."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

from dte_codec import encode
from translation_cache import load_best_by_id


RECORD_SIZE = 0x40
JAPANESE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")


def decoded(record: bytes) -> str:
    return record.split(b"\0", 1)[0].rstrip(b"\xcc").decode("cp932")


def dump(source: Path, output: Path) -> None:
    data = source.read_bytes()
    if len(data) % RECORD_SIZE:
        raise SystemExit("NAME.BIN size is not a multiple of 0x40")
    rows = []
    for index in range(len(data) // RECORD_SIZE):
        text = decoded(data[index * RECORD_SIZE : (index + 1) * RECORD_SIZE])
        rows.append({
            "id": f"name-{index:03d}", "occurrences": 1, "min_encoded_bytes": 63,
            "max_encoded_bytes": 63, "source": text, "translation": "", "status": "untranslated", "notes": "",
        })
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]), dialect="excel-tab")
        writer.writeheader(); writer.writerows(rows)
    print(f"dumped {len(rows)} NAME.BIN records")


def rebuild(source: Path, cache: Path, output: Path, report_path: Path) -> None:
    data = bytearray(source.read_bytes())
    cached = load_best_by_id([cache])
    report = []
    for index in range(len(data) // RECORD_SIZE):
        key = f"name-{index:03d}"; start = index * RECORD_SIZE
        original = decoded(data[start : start + RECORD_SIZE]); row = cached.get(key); status = "no-translation"; english = ""
        if row:
            english = row.get("translation", "")
            try: raw, _ = encode(english, {})
            except UnicodeEncodeError: raw = b""; status = "encoding-error"
            else:
                if not english or JAPANESE.search(english): status = "unsafe"
                elif len(raw) + 1 > RECORD_SIZE: status = "overflow"
                else:
                    data[start : start + RECORD_SIZE] = raw + b"\0" + b"\xcc" * (RECORD_SIZE - len(raw) - 1)
                    status = "applied"
        report.append({"id": key, "status": status, "source": original, "translation": english})
    output.parent.mkdir(parents=True, exist_ok=True); output.write_bytes(data)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(report[0]), dialect="excel-tab")
        writer.writeheader(); writer.writerows(report)
    print(f"rebuilt NAME.BIN; applied {sum(row['status'] == 'applied' for row in report)} records")


def main() -> None:
    parser = argparse.ArgumentParser(); commands = parser.add_subparsers(required=True)
    d = commands.add_parser("dump"); d.add_argument("source", type=Path); d.add_argument("output", type=Path)
    r = commands.add_parser("rebuild"); r.add_argument("source", type=Path); r.add_argument("cache", type=Path); r.add_argument("output", type=Path); r.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.__dict__.get("cache") is None: dump(args.source, args.output)
    else: rebuild(args.source, args.cache, args.output, args.report)


if __name__ == "__main__":
    main()
