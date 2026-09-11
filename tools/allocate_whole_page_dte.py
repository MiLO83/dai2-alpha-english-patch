#!/usr/bin/env python3
"""Allocate a small DTE bank only to pages that can be encoded entirely as pairs."""

from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path

from dte_codec import encode
from translation_cache import load_best_by_source


BOUNDARY = re.compile(r"(\$[A-Za-z]|\r?\n|[「」])")


def required_pairs(text: str) -> set[str] | None:
    pairs: set[str] = set()
    for part in BOUNDARY.split(text):
        if not part or BOUNDARY.fullmatch(part):
            continue
        if not part.isascii() or any(not 0x20 <= ord(char) <= 0x7E for char in part):
            return None
        if len(part) & 1:
            part += " "
        pairs.update(part[index : index + 2] for index in range(0, len(part), 2))
    return pairs


def paired_size(text: str) -> int:
    size = 0
    for part in BOUNDARY.split(text):
        if not part:
            continue
        if BOUNDARY.fullmatch(part):
            size += len(encode(part, {})[0])
        else:
            size += ((len(part) + 1) // 2) * 2
    return size


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cache", type=Path); parser.add_argument("occurrences", type=Path)
    parser.add_argument("table", type=Path); parser.add_argument("selection", type=Path)
    parser.add_argument("--slots", type=int, default=93)
    parser.add_argument("--member", action="append", help="Only allocate for these MWo3 members")
    args = parser.parse_args()
    cached = load_best_by_source([args.cache])
    budgets: dict[str, list[int]] = defaultdict(list)
    members = set(args.member or [])
    with args.occurrences.open(encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source, dialect="excel-tab"):
            if members and row["member"] not in members:
                continue
            budgets[row["source"]].append(int(row["max_encoded_bytes"]))
    candidates = []
    for source, row in cached.items():
        text = row.get("translation", "")
        if not text or "「" not in text:
            continue
        pairs = required_pairs(text)
        if pairs is None or len(pairs) > args.slots:
            continue
        normal = len(encode(text, {})[0]); condensed = paired_size(text)
        rescued = sum(condensed <= budget < normal for budget in budgets.get(source, []))
        if rescued:
            candidates.append({"source": source, "translation": text, "pairs": pairs, "normal": normal, "dte": condensed, "rescued": rescued})
    selected = []; allocated: set[str] = set()
    while candidates:
        viable = [row for row in candidates if len(allocated | row["pairs"]) <= args.slots]
        if not viable: break
        best = max(viable, key=lambda row: (row["rescued"] * (row["normal"] - row["dte"])) / max(1, len(row["pairs"] - allocated)))
        selected.append(best); allocated |= best["pairs"]; candidates.remove(best)
    args.table.parent.mkdir(parents=True, exist_ok=True)
    with args.table.open("w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output, dialect="excel-tab"); writer.writerow(("pair", "sjis", "notes"))
        for pair, code in zip(sorted(allocated), range(0x87A0, 0x87A0 + len(allocated))):
            writer.writerow((pair, f"{code:04X}", "whole-page DTE"))
    with args.selection.open("w", encoding="utf-8", newline="") as output:
        fields = ["source", "translation", "normal_bytes", "dte_bytes", "rescued_occurrences"]
        writer = csv.DictWriter(output, fieldnames=fields, dialect="excel-tab"); writer.writeheader()
        for row in selected:
            writer.writerow({"source": row["source"], "translation": row["translation"], "normal_bytes": row["normal"], "dte_bytes": row["dte"], "rescued_occurrences": row["rescued"]})
    print(f"selected {len(selected)} pages rescuing {sum(row['rescued'] for row in selected)} occurrences with {len(allocated)}/{args.slots} pairs")


if __name__ == "__main__":
    main()
