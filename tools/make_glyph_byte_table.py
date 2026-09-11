#!/usr/bin/env python3
"""Export Japanese CP932 and English DTE glyph byte/index mappings."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from font_patch import direct_sjis_index


ROOT = Path(__file__).resolve().parent.parent
FIELDS = ("kind", "Japanese glyph", "Japanese bytes", "English glyph", "English bytes", "atlas index")


def atlas(raw: bytes) -> str:
    if len(raw) != 2:
        return ""
    try:
        return f"0x{direct_sjis_index(int.from_bytes(raw, 'big')):04X}"
    except ValueError:
        return ""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("master", type=Path, nargs="?",
                        default=ROOT / "translation/all-known-game-text.tsv")
    parser.add_argument("dte", type=Path, nargs="?",
                        default=ROOT / "config/dte-current.tsv")
    parser.add_argument("output", type=Path, nargs="?",
                        default=ROOT / "translation/glyph-byte-table.tsv")
    args = parser.parse_args()
    chars: set[str] = set()
    with args.master.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source, dialect="excel-tab"):
            chars.update(row["Original Japanese"])
    rows: list[dict[str, str]] = []
    for char in sorted(chars):
        try:
            raw = char.encode("cp932")
        except UnicodeEncodeError:
            continue
        rows.append({"kind": "Japanese/retail", "Japanese glyph": char,
                     "Japanese bytes": raw.hex().upper(), "English glyph": "",
                     "English bytes": "", "atlas index": atlas(raw)})
    if args.dte.exists():
        with args.dte.open(encoding="utf-8", newline="") as source:
            for row in csv.DictReader(source, dialect="excel-tab"):
                raw = bytes.fromhex(row["sjis"])
                try:
                    japanese = raw.decode("cp932")
                except UnicodeDecodeError:
                    japanese = ""
                rows.append({"kind": "English DTE", "Japanese glyph": japanese,
                             "Japanese bytes": raw.hex().upper(), "English glyph": row["pair"],
                             "English bytes": raw.hex().upper(), "atlas index": atlas(raw)})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=FIELDS, dialect="excel-tab")
        writer.writeheader(); writer.writerows(rows)
    print(f"wrote {len(rows)} glyph mappings to {args.output}")


if __name__ == "__main__":
    main()
