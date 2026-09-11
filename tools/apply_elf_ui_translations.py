#!/usr/bin/env python3
"""Apply verified whole-field DTE translations to the SLPS executable."""

from __future__ import annotations

import argparse
import csv
import re
from collections import Counter
from pathlib import Path

from dte_codec import encode_whole_page, load_pairs
from allocate_whole_page_dte import paired_size


JAPANESE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")
HEADERS = ("Original Japanese", "Automatic Translation", "English")
SAFE_SINGLE_FIELDS = {"空", "陸", "海", "宇"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("table", type=Path)
    parser.add_argument("metadata", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--dte", type=Path, required=True)
    parser.add_argument("--ascii", action="store_true",
                        help="encode menu translations with the native single-byte Latin font")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    with args.table.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source, dialect="excel-tab")
        fields = tuple(reader.fieldnames or ())
        if fields not in (HEADERS, ("Scope",) + HEADERS):
            parser.error(f"{args.table} must contain Scope (optional), then: {', '.join(HEADERS)}")
        chosen = {
            row["Original Japanese"]: row["English"].strip() or row["Automatic Translation"].strip()
            for row in reader
            if "Scope" not in row or row["Scope"] == "ui"
        }
    with args.metadata.open(encoding="utf-8", newline="") as source:
        occurrences = list(csv.DictReader(source, dialect="excel-tab"))

    data = bytearray(args.executable.read_bytes())
    pairs = load_pairs(args.dte)
    report: list[dict[str, str | int]] = []
    for row in occurrences:
        offset = int(row["offset"], 0)
        capacity = int(row["field_bytes"])
        # Some CP932 extension characters decode canonically to a different
        # byte pair when re-encoded; metadata retains the exact disc bytes.
        original = bytes.fromhex(row.get("source_hex", "")) or row["source"].encode("cp932")
        current = bytes(data[offset:offset + len(original)])
        translation = chosen.get(row["source"], "")
        status = "untranslated"
        encoded = b""
        if row["source"].startswith("０１２３４５６７８９ＡＢＣＤＥＦ"):
            # Random-access character palette used by numeric formatting and
            # name entry. Pair-compressing it changes every indexed element.
            status = "dynamic-lookup"
        elif len(row["source"]) == 1 and row["source"] not in SAFE_SINGLE_FIELDS:
            status = "dynamic-fragment"
        elif current != original:
            status = "source-mismatch"
        elif not translation:
            status = "untranslated"
        elif JAPANESE.search(translation):
            status = "residual-japanese"
        elif (len(translation.encode("ascii", errors="replace")) if args.ascii
              else paired_size(translation)) > capacity:
            status = "overflow"
        else:
            try:
                if args.ascii:
                    encoded = translation.encode("ascii")
                else:
                    encoded, _ = encode_whole_page(translation, pairs)
                data[offset:offset + capacity + 1] = encoded + bytes(capacity + 1 - len(encoded))
                status = "applied"
            except (UnicodeEncodeError, ValueError):
                status = "encoding-error"
        report.append({
            "id": row["id"], "source": row["source"], "translation": translation,
            "offset": row["offset"], "capacity": capacity,
            "encoded_bytes": len(encoded), "status": status,
        })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=report[0].keys(), dialect="excel-tab")
        writer.writeheader(); writer.writerows(report)
    print(dict(Counter(str(row["status"]) for row in report)))
    print(args.output)


if __name__ == "__main__":
    main()
