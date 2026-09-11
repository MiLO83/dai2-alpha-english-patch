#!/usr/bin/env python3
"""Apply validated cached translations to independently allocated STAGE strings."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

from dte_codec import encode, encode_whole_page, load_pairs
from translate_ollama import protected
from translation_cache import load_best_by_source


JAPANESE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")
UNSAFE = re.compile(r"[^\x20-\x7e\n\r\t「」]")
BLOCKED_WORDS = re.compile(r"\b(fuck|fucker|motherfucker|shit|cunt)\b", re.I)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", type=Path)
    parser.add_argument("occurrences", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--cache", type=Path, action="append", required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--dte", type=Path)
    parser.add_argument("--dte-selection", type=Path)
    parser.add_argument("--member", action="append", help="Only patch these MWo3 members")
    args = parser.parse_args()

    stage = bytearray(args.stage.read_bytes())
    translations = load_best_by_source(args.cache)
    pairs = load_pairs(args.dte) if args.dte else {}
    selected: set[str] = set()
    if args.dte_selection:
        with args.dte_selection.open(encoding="utf-8", newline="") as source:
            selected = {row["source"] for row in csv.DictReader(source, dialect="excel-tab")}

    with args.occurrences.open(encoding="utf-8", newline="") as source:
        occurrences = list(csv.DictReader(source, dialect="excel-tab"))
    report: list[dict[str, object]] = []
    applied_offsets: set[int] = set()
    members = set(args.member or [])
    for row in occurrences:
        offset = int(row["absolute_offset"], 0)
        original_size = int(row["source_bytes"])
        allocation = int(row["max_encoded_bytes"])
        cached = translations.get(row["source"]) if not members or row["member"] in members else None
        reason = "no-translation"
        encoded = b""
        english = ""
        if cached:
            english = str(cached.get("translation", ""))
            if not english:
                reason = "empty"
            elif JAPANESE.search(english) or UNSAFE.search(english):
                reason = "unsafe-characters"
            elif BLOCKED_WORDS.search(english):
                reason = "blocked-language"
            elif ("「" in row["source"] or "」" in row["source"]) and (
                len(english.splitlines()) > 3 or any(
                    len(line.replace("「", "").replace("」", "")) > (44 if row["source"] in selected else 22)
                    for line in english.splitlines()
                )
            ):
                reason = "layout-overflow"
            elif protected(row["source"]) != protected(english) or [c for c in row["source"] if c in "「」"] != [c for c in english if c in "「」"]:
                reason = "controls-changed"
            else:
                try:
                    encoded, _ = encode_whole_page(english, pairs) if row["source"] in selected else encode(english, {})
                    reason = "fits" if len(encoded) <= allocation else "overflow"
                except (UnicodeEncodeError, ValueError):
                    reason = "encoding-error"
        if reason == "fits" and offset not in applied_offsets:
            current = bytes(stage[offset : offset + original_size])
            if current.decode("cp932") != row["source"]:
                reason = "source-mismatch"
            else:
                clear_size = max(original_size + 1, len(encoded) + 1)
                stage[offset : offset + clear_size] = encoded + b"\0" * (clear_size - len(encoded))
                applied_offsets.add(offset)
        report.append({
            "id": row["id"], "member": row["member"], "absolute_offset": row["absolute_offset"],
            "source_bytes": original_size, "allocation": allocation, "encoded_bytes": len(encoded) if encoded else "",
            "status": "applied" if reason == "fits" else reason, "source": row["source"], "translation": english,
            "encoding": "whole-page-dte" if reason == "fits" and row["source"] in selected else "single-tile",
        })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(stage)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(report[0]), dialect="excel-tab")
        writer.writeheader(); writer.writerows(report)
    counts: dict[str, int] = {}
    for row in report:
        counts[str(row["status"])] = counts.get(str(row["status"]), 0) + 1
    print(json.dumps(counts, sort_keys=True))


if __name__ == "__main__":
    main()
