#!/usr/bin/env python3
"""Create the compact unique-string input used for batched UI translation."""

from __future__ import annotations

import argparse
import csv
from collections import OrderedDict
from pathlib import Path


FIELDS = ("id", "occurrences", "min_encoded_bytes", "max_encoded_bytes", "source")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("metadata", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    grouped: OrderedDict[str, list[int]] = OrderedDict()
    with args.metadata.open(encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source, dialect="excel-tab"):
            grouped.setdefault(row["source"], []).append(int(row["field_bytes"]))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=FIELDS, dialect="excel-tab")
        writer.writeheader()
        for number, (text, budgets) in enumerate(grouped.items(), 1):
            writer.writerow({
                "id": f"ui-text-{number:05d}",
                "occurrences": len(budgets),
                "min_encoded_bytes": min(budgets),
                "max_encoded_bytes": max(budgets),
                "source": text,
            })
    print(f"prepared {len(grouped)} unique UI strings in {args.output}")


if __name__ == "__main__":
    main()
