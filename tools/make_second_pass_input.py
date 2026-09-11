#!/usr/bin/env python3
"""Build a retry input containing every unique source left unapplied in a report."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("unique", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    with args.report.open(encoding="utf-8", newline="") as source:
        unapplied = {
            row["source"]
            for row in csv.DictReader(source, dialect="excel-tab")
            if row["status"] != "applied"
        }
    with args.unique.open(encoding="utf-8", newline="") as source:
        rows = [
            row for row in csv.DictReader(source, dialect="excel-tab")
            if row["source"] in unapplied
        ]
    if not rows:
        raise SystemExit("no unapplied sources found")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]), dialect="excel-tab")
        writer.writeheader()
        writer.writerows(rows)
    print(f"selected {len(rows)} unique unapplied strings")


if __name__ == "__main__":
    main()
