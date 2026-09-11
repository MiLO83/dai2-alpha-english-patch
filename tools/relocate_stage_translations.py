#!/usr/bin/env python3
"""Relocate translated strings into expanded MWo3 overlays and rewrite pointers."""

from __future__ import annotations

import argparse
import csv
import re
import struct
from pathlib import Path

from dte_codec import encode, encode_whole_page, load_pairs
from translation_cache import load_best_by_source


JAPANESE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")
UNSAFE = re.compile(r"[^\x20-\x7e\n\r\t「」]")
CONTROL = re.compile(r"\$[A-Za-z]")


def align(value: int, amount: int) -> int:
    return (value + amount - 1) & -amount


def member_starts(data: bytes) -> list[int]:
    starts: list[int] = []
    cursor = 0
    while (cursor := data.find(b"MWo3", cursor)) >= 0:
        starts.append(cursor)
        cursor += 4
    return starts


def member_name(member: bytes) -> str:
    return member[0x20:0x40].split(b"\0", 1)[0].decode("ascii", "replace")


def wrap_words(text: str, capacities: list[int]) -> list[str] | None:
    words = re.sub(r"[ \t\r\n]+", " ", text).strip().split(" ")
    if not words:
        return [""]
    lines: list[str] = []
    index = 0
    for capacity in capacities:
        line = ""
        while index < len(words):
            candidate = words[index] if not line else line + " " + words[index]
            if len(candidate) > capacity:
                break
            line = candidate
            index += 1
        if not line:
            return None
        lines.append(line)
        if index == len(words):
            return lines
    return None


def reflow_dialogue(text: str, width: int = 22, max_lines: int = 3) -> tuple[str, bool] | None:
    opening = text.find("「")
    closing = text.rfind("」")
    if opening < 0 or closing < opening:
        return (text, False)
    speaker = re.sub(r"[ \t\r\n]+", " ", text[:opening]).strip()
    body = text[opening + 1:closing]
    suffix = text[closing + 1:]
    if suffix.strip():
        return None
    capacities = [width - len(speaker)] + [width] * (max_lines - 1)
    wrapped = wrap_words(body, capacities) if capacities[0] > 0 else None
    omitted = False
    if wrapped is None and speaker:
        wrapped = wrap_words(body, [width] * max_lines)
        omitted = wrapped is not None
        if omitted:
            speaker = ""
    if wrapped is None:
        return None
    return f"{speaker}「{'\n'.join(wrapped)}」", omitted


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", type=Path)
    parser.add_argument("occurrences", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--cache", type=Path, action="append", required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--member", action="append", required=True)
    parser.add_argument("--dte", type=Path)
    parser.add_argument("--dte-selection", type=Path)
    args = parser.parse_args()

    original = args.stage.read_bytes()
    translations = load_best_by_source(args.cache)
    pairs = load_pairs(args.dte) if args.dte else {}
    selected: dict[str, str] = {}
    if args.dte_selection:
        with args.dte_selection.open(encoding="utf-8", newline="") as source:
            selected = {row["source"]: row["translation"] for row in csv.DictReader(source, dialect="excel-tab")}
    wanted_members = set(args.member)
    by_member: dict[str, list[dict[str, str]]] = {}
    with args.occurrences.open(encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source, dialect="excel-tab"):
            if row["member"] in wanted_members:
                by_member.setdefault(row["member"], []).append(row)

    starts = member_starts(original)
    rebuilt: list[bytes] = []
    report: list[dict[str, object]] = []
    seen_members: set[str] = set()
    for number, start in enumerate(starts):
        end = starts[number + 1] if number + 1 < len(starts) else len(original)
        member = bytearray(original[start:end])
        name = member_name(member)
        if name not in wanted_members:
            rebuilt.append(bytes(member))
            continue
        seen_members.add(name)
        load = struct.unpack_from("<I", member, 8)[0]
        original_size = len(member)
        for row in by_member.get(name, []):
            source_text = row["source"]
            old_offset = int(row["member_offset"], 0)
            cached = translations.get(source_text)
            status = "no-translation"
            english = ""
            omitted = False
            encoding = "single-tile"
            if cached:
                english = str(cached.get("translation", ""))
                english = english.replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"')
                if not english:
                    status = "empty"
                elif JAPANESE.search(english) or UNSAFE.search(english):
                    status = "unsafe"
                elif CONTROL.findall(source_text) != CONTROL.findall(english):
                    status = "controls-changed"
                elif [c for c in source_text if c in "「」"] != [c for c in english if c in "「」"]:
                    status = "brackets-changed"
                else:
                    use_dte = source_text in selected
                    if use_dte:
                        english = selected[source_text]
                    if "「" in english:
                        flowed = (english, False) if use_dte else reflow_dialogue(english, 22)
                        if flowed is None:
                            status = "needs-pagination"
                            report.append({"member": name, "member_offset": row["member_offset"], "status": status, "encoding": encoding, "speaker_omitted": omitted, "source": source_text, "translation": english})
                            continue
                        english, omitted = flowed
                    try:
                        raw, _ = encode_whole_page(english, pairs) if use_dte else encode(english, {})
                        encoding = "whole-page-dte" if use_dte else "single-tile"
                    except (UnicodeEncodeError, ValueError):
                        status = "encoding-error"
                    else:
                        old_address = load + old_offset
                        pointer_offsets = [
                            pos for pos in range(0, original_size - 3, 4)
                            if struct.unpack_from("<I", member, pos)[0] == old_address
                        ]
                        if not pointer_offsets:
                            status = "no-pointer"
                        else:
                            new_offset = align(len(member), 8)
                            member.extend(b"\0" * (new_offset - len(member)))
                            member.extend(raw + b"\0")
                            new_address = load + new_offset
                            for pos in pointer_offsets:
                                struct.pack_into("<I", member, pos, new_address)
                            status = "relocated"
            report.append({"member": name, "member_offset": row["member_offset"], "status": status, "encoding": encoding, "speaker_omitted": omitted, "source": source_text, "translation": english})
        new_size = align(len(member), 0x80)
        member.extend(b"\0" * (new_size - len(member)))
        growth = new_size - original_size
        struct.pack_into("<I", member, 0x10, struct.unpack_from("<I", member, 0x10)[0] + growth)
        struct.pack_into("<I", member, 0x18, load + new_size)
        struct.pack_into("<I", member, 0x1C, load + new_size)
        rebuilt.append(bytes(member))

    missing = wanted_members - seen_members
    if missing:
        parser.error(f"members not found: {', '.join(sorted(missing))}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(b"".join(rebuilt))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(report[0]), dialect="excel-tab")
        writer.writeheader()
        writer.writerows(report)
    counts: dict[str, int] = {}
    for row in report:
        counts[str(row["status"])] = counts.get(str(row["status"]), 0) + 1
    print(f"rebuilt STAGE.BIN: {len(original)} -> {sum(map(len, rebuilt))} bytes")
    print(" ".join(f"{key}={counts[key]}" for key in sorted(counts)))


if __name__ == "__main__":
    main()
