#!/usr/bin/env python3
"""Analyze English bigrams and measure/encode the game's full-width text."""

from __future__ import annotations

import argparse
import csv
import re
from collections import Counter
from pathlib import Path


CONTROL = re.compile(r"\$[A-Za-z]")
PAIR = re.compile(r"(?=([A-Za-z][A-Za-z]))")
WHOLE_PAGE_BOUNDARY = re.compile(r"(\$[A-Za-z]|\r?\n|[「」])")


def load_pairs(path: Path) -> dict[str, bytes]:
    pairs: dict[str, bytes] = {}
    with path.open(encoding="utf-8", newline="") as source:
        lines = (line for line in source if not line.startswith("#"))
        for row in csv.DictReader(lines, dialect="excel-tab"):
            pair = row["pair"]
            code = row["sjis"].strip()
            if not pair or not code:
                continue
            if len(pair) != 2 or not pair.isascii() or not all(0x20 <= ord(char) <= 0x7E for char in pair):
                raise ValueError(f"invalid DTE pair {pair!r}")
            raw = bytes.fromhex(code)
            if len(raw) != 2:
                raise ValueError(f"DTE code for {pair!r} must contain two bytes")
            pairs[pair] = raw
    return pairs


def encode_single(char: str) -> bytes:
    if char == " ":
        return "\u3000".encode("cp932")
    if char == "\n":
        return b"\n"
    if 0x21 <= ord(char) <= 0x7E:
        fullwidth = chr(ord(char) + 0xFEE0)
        try:
            return fullwidth.encode("cp932")
        except UnicodeEncodeError:
            pass
    raw = char.encode("cp932")
    if len(raw) != 2:
        raise UnicodeEncodeError("cp932", char, 0, 1, "glyph is not a two-byte code")
    return raw


def encode(text: str, pairs: dict[str, bytes]) -> tuple[bytes, int]:
    output = bytearray()
    used = 0
    cursor = 0
    while cursor < len(text):
        control = CONTROL.match(text, cursor)
        if control:
            output.extend(control.group().encode("ascii"))
            cursor = control.end()
        elif text[cursor : cursor + 2] in pairs:
            output.extend(pairs[text[cursor : cursor + 2]])
            used += 1
            cursor += 2
        else:
            output.extend(encode_single(text[cursor]))
            cursor += 1
    return bytes(output), used


def encode_whole_page(text: str, pairs: dict[str, bytes]) -> tuple[bytes, int]:
    """Encode every visible segment as non-overlapping pairs or fail atomically."""
    output = bytearray(); used = 0
    for part in WHOLE_PAGE_BOUNDARY.split(text):
        if not part:
            continue
        if WHOLE_PAGE_BOUNDARY.fullmatch(part):
            output.extend(encode(part, {})[0])
            continue
        if not part.isascii() or any(not 0x20 <= ord(char) <= 0x7E for char in part):
            raise ValueError("whole-page DTE requires printable ASCII visible text")
        if len(part) & 1:
            part += " "
        for index in range(0, len(part), 2):
            pair = part[index : index + 2]
            if pair not in pairs:
                raise ValueError(f"whole-page DTE pair {pair!r} is unassigned")
            output.extend(pairs[pair]); used += 1
    return bytes(output), used


def analyze(args: argparse.Namespace) -> None:
    counts: Counter[str] = Counter()
    with args.input.open(encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source, dialect="excel-tab"):
            text = row.get(args.column, "")
            counts.update(match.group(1) for match in PAIR.finditer(text))
    rows = counts.most_common(args.limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output, dialect="excel-tab")
        writer.writerow(("rank", "pair", "occurrences", "potential_bytes_saved"))
        for rank, (pair, count) in enumerate(rows, 1):
            writer.writerow((rank, pair, count, count * 2))
    print(f"wrote {len(rows)} pair candidates to {args.output}")


def report(args: argparse.Namespace) -> None:
    pairs = load_pairs(args.dte)
    with args.input.open(encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source, dialect="excel-tab"))
    fields = list(rows[0]) + ["encoded_bytes", "dte_tiles", "remaining_bytes", "encoding_status"]
    for row in rows:
        try:
            raw, used = encode(row[args.column], pairs)
            budget = int(row[args.budget_column])
            row.update(
                encoded_bytes=str(len(raw)),
                dte_tiles=str(used),
                remaining_bytes=str(budget - len(raw)),
                encoding_status="fits" if len(raw) <= budget else "OVERFLOW",
            )
        except (UnicodeEncodeError, ValueError) as error:
            row.update(encoded_bytes="", dte_tiles="", remaining_bytes="", encoding_status=f"ERROR: {error}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields, dialect="excel-tab")
        writer.writeheader()
        writer.writerows(rows)
    print(f"measured {len(rows)} strings using {len(pairs)} DTE pairs in {args.output}")


def allocate(args: argparse.Namespace) -> None:
    with args.input.open(encoding="utf-8", newline="") as source:
        candidates = list(csv.DictReader(source, dialect="excel-tab"))
    codes = list(range(0x87A0, 0x87FD))
    selected = candidates[: min(args.limit, len(codes), len(candidates))]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output, dialect="excel-tab")
        writer.writerow(("pair", "sjis", "notes"))
        for row, code in zip(selected, codes):
            writer.writerow((row["pair"], f"{code:04X}", f"rank {row['rank']}; provisional"))
    print(f"assigned {len(selected)} pairs to provisional codes 87A0-87FC in {args.output}")


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(required=True)
    analyze_parser = commands.add_parser("analyze")
    analyze_parser.add_argument("input", type=Path)
    analyze_parser.add_argument("output", type=Path)
    analyze_parser.add_argument("--column", default="translation")
    analyze_parser.add_argument("--limit", type=int, default=128)
    analyze_parser.set_defaults(function=analyze)
    report_parser = commands.add_parser("report")
    report_parser.add_argument("input", type=Path)
    report_parser.add_argument("dte", type=Path)
    report_parser.add_argument("output", type=Path)
    report_parser.add_argument("--column", default="translation")
    report_parser.add_argument("--budget-column", default="min_encoded_bytes")
    report_parser.set_defaults(function=report)
    allocate_parser = commands.add_parser("allocate")
    allocate_parser.add_argument("input", type=Path)
    allocate_parser.add_argument("output", type=Path)
    allocate_parser.add_argument("--limit", type=int, default=93)
    allocate_parser.set_defaults(function=allocate)
    args = parser.parse_args()
    args.function(args)


if __name__ == "__main__":
    main()
