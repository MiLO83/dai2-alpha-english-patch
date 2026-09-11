#!/usr/bin/env python3
"""Merge the shortest structurally safe cache draft into the automatic TSV column."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

from allocate_whole_page_dte import paired_size
from bulk_translate_ollama import screen_layout_ok


CONTROL = re.compile(r"\$[A-Za-z]")
JAPANESE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")
UNSAFE = re.compile(r"[^\x20-\x7e\n\r\t「」]")


def safe(source: str, text: str) -> bool:
    return bool(text) and not JAPANESE.search(text) and not UNSAFE.search(text) \
        and CONTROL.findall(source) == CONTROL.findall(text) \
        and [c for c in source if c in "「」"] == [c for c in text if c in "「」"] \
        and ("「" not in source or screen_layout_ok(text, 44))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("table", type=Path)
    parser.add_argument("cache", type=Path, nargs="+")
    args = parser.parse_args()
    candidates: dict[str, list[str]] = {}
    for path in args.cache:
        with path.open(encoding="utf-8") as source:
            for line in source:
                if not line.strip():
                    continue
                row = json.loads(line)
                japanese, english = str(row.get("source", "")), str(row.get("translation", ""))
                if safe(japanese, english):
                    candidates.setdefault(japanese, []).append(english)
    with args.table.open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source, dialect="excel-tab"))
        fields = source and ("Original Japanese", "Automatic Translation", "English")
    changed = 0
    for row in rows:
        choices = candidates.get(row["Original Japanese"], [])
        if choices:
            best = min(choices, key=lambda text: (paired_size(text), len(text)))
            if row["Automatic Translation"] != best:
                row["Automatic Translation"] = best
                changed += 1
    with args.table.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields, dialect="excel-tab")
        writer.writeheader(); writer.writerows(rows)
    print(f"merged {changed} safe automatic drafts into {args.table}")


if __name__ == "__main__":
    main()
