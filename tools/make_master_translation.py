#!/usr/bin/env python3
"""Merge every known editable text table into one paged master TSV."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
HEADERS = ("Scope", "Original Japanese", "Automatic Translation", "English", "English Page 2", "English Page 3")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, nargs="?",
                        default=ROOT / "translation/all-known-game-text.tsv")
    parser.add_argument("inputs", type=Path, nargs="*", default=[
        ROOT / "translation/game-script.tsv",
        ROOT / "translation/ui-script.tsv",
        ROOT / "translation/title-script.tsv",
    ])
    args = parser.parse_args()
    merged: dict[tuple[str, str], dict[str, str]] = {}
    scopes = ("dialogue", "ui", "title")
    for path, scope in zip(args.inputs, scopes):
        with path.open(encoding="utf-8-sig", newline="") as source:
            for row in csv.DictReader(source, dialect="excel-tab"):
                japanese = row.get("Original Japanese", "")
                if not japanese:
                    continue
                current = merged.setdefault((scope, japanese), {
                    "Scope": scope,
                    "Original Japanese": japanese,
                    "Automatic Translation": "",
                    "English": "",
                    "English Page 2": "",
                    "English Page 3": "",
                })
                # Never replace a populated reviewed or automatic cell with an
                # empty duplicate from a different text domain.
                current["Automatic Translation"] = (
                    current["Automatic Translation"] or row.get("Automatic Translation", "")
                )
                current["English"] = current["English"] or row.get("English", "")
                current["English Page 2"] = current["English Page 2"] or row.get("English Page 2", "")
                current["English Page 3"] = current["English Page 3"] or row.get("English Page 3", "")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=HEADERS, dialect="excel-tab")
        writer.writeheader(); writer.writerows(merged.values())
    print(f"merged {len(merged)} unique known strings into {args.output}")


if __name__ == "__main__":
    main()
