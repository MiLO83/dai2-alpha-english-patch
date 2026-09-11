#!/usr/bin/env python3
"""Merge reviewed canonical UI terms into the automatic translation column."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("table", type=Path)
    parser.add_argument("canonical", type=Path)
    args = parser.parse_args()
    with args.canonical.open(encoding="utf-8-sig", newline="") as source:
        known = {row["japanese"]: row["english"] for row in csv.DictReader(source, dialect="excel-tab")}
    with args.table.open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source, dialect="excel-tab"))
        fields = tuple(source and ("Original Japanese", "Automatic Translation", "English"))
    changed = 0
    for row in rows:
        replacement = known.get(row["Original Japanese"])
        if replacement and row["Automatic Translation"] != replacement:
            row["Automatic Translation"] = replacement
            changed += 1
    with args.table.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields, dialect="excel-tab")
        writer.writeheader(); writer.writerows(rows)
    print(f"merged {changed} canonical UI translations into {args.table}")


if __name__ == "__main__":
    main()
