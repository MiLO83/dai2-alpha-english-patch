#!/usr/bin/env python3
"""Select unique translation rows used by one or more MWo3 members."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("unique", type=Path)
    parser.add_argument("occurrences", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--member", action="append", required=True)
    args = parser.parse_args()

    members = set(args.member)
    with args.occurrences.open(encoding="utf-8", newline="") as source:
        wanted = {
            row["source"]
            for row in csv.DictReader(source, dialect="excel-tab")
            if row["member"] in members
        }
    with args.unique.open(encoding="utf-8", newline="") as source:
        rows = [row for row in csv.DictReader(source, dialect="excel-tab") if row["source"] in wanted]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]), dialect="excel-tab")
        writer.writeheader()
        writer.writerows(rows)
    if len(rows) != len(wanted):
        parser.error(f"selected {len(rows)} rows for {len(wanted)} unique sources")
    print(f"selected {len(rows)} unique strings from {', '.join(args.member)}")


if __name__ == "__main__":
    main()
