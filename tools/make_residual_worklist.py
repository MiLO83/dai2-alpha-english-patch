#!/usr/bin/env python3
"""Create one translation-input row per residual source in a build report."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--status", action="append", help="include only these report statuses")
    args = parser.parse_args()
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    with args.report.open(encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source, dialect="excel-tab"):
            if row["status"] != "applied" and (not args.status or row["status"] in args.status):
                grouped[row["source"]].append(row)
    fields = ("id", "occurrences", "min_encoded_bytes", "max_encoded_bytes", "source", "translation", "status", "notes")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields, dialect="excel-tab")
        writer.writeheader()
        for number, (text, rows) in enumerate(grouped.items(), 1):
            budgets = [int(row["allocation"]) for row in rows]
            statuses = sorted({row["status"] for row in rows})
            prior = next((row["translation"] for row in rows if row["translation"]), "")
            writer.writerow({
                "id": f"residual-{number:05d}", "occurrences": len(rows),
                "min_encoded_bytes": min(budgets), "max_encoded_bytes": max(budgets),
                "source": text, "translation": prior, "status": "untranslated",
                "notes": ",".join(statuses),
            })
    print(f"wrote {len(grouped)} unique residual strings to {args.output}")


if __name__ == "__main__":
    main()
