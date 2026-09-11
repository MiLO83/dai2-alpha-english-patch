#!/usr/bin/env python3
"""Allocate glyph codes so every validated translated dialogue is whole-page DTE."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from allocate_whole_page_dte import paired_size, required_pairs
from dte_codec import encode
from font_patch import direct_sjis_index, latin_index
from translation_cache import load_best_by_source, row_is_valid


def valid_codes(used: set[bytes]) -> list[bytes]:
    protected_indices = {latin_index(chr(value)) for value in range(0x20, 0x7F)}
    # Several menu renderers do not use the ordinary full-width digit cells.
    # Their context-specific numeric table resolves 0..7 to these atlas slots.
    # A matched original/patched Weapon Stats capture established the mapping:
    # 2600 rendered as the DTE tiles 45/CD/01/01, with the remaining values
    # confirming 1->23, 3->67, 4->89, 5->AB, and 7->EF.  Protect the atlas
    # indices themselves so alternate SJIS aliases cannot reclaim them.
    protected_indices.update({0x48B, 0x4BC, 0x4FD, 0x523, 0x54F, 0x5C1, 0x62B, 0x69C})
    # Preserve the kana pages on the name-entry screen even if a glyph is absent
    # from the extracted scenario text.
    protected_codes = {
        bytes((lead, trail))
        for lead, first, last in ((0x82, 0x9F, 0xF1), (0x83, 0x40, 0x96))
        for trail in range(first, last + 1)
        if trail != 0x7F
    }
    # Menus construct stats, levels, percentages, terrain ranks, button hints,
    # and debug values dynamically. Those glyphs do not necessarily occur in
    # any extractable NUL-terminated source string, so reserve their full-width
    # CP932 ranges unconditionally instead of treating them as reclaimable.
    protected_codes.update(
        bytes((0x81, trail)) for trail in range(0x40, 0xFD) if trail != 0x7F
    )
    protected_codes.update(
        bytes((0x82, trail))
        for first, last in ((0x4F, 0x58), (0x60, 0x79), (0x81, 0x9A))
        for trail in range(first, last + 1)
    )
    result: list[bytes] = []
    seen_indices: set[int] = set()
    for lead in range(0x81, 0x99):
        last = 0x72 if lead == 0x98 else 0xFC
        for trail in range(0x40, last + 1):
            if trail == 0x7F:
                continue
            raw = bytes((lead, trail))
            if raw in used or raw in protected_codes:
                continue
            try:
                index = direct_sjis_index(int.from_bytes(raw, "big"))
            except ValueError:
                continue
            if index in protected_indices or index in seen_indices:
                continue
            seen_indices.add(index)
            result.append(raw)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("occurrences", type=Path)
    parser.add_argument("table", type=Path)
    parser.add_argument("selection", type=Path)
    parser.add_argument("--cache", type=Path, action="append", required=True)
    parser.add_argument("--member", action="append")
    parser.add_argument("--extra-occurrences", type=Path, action="append", default=[],
                        help="additional TSVs with source fields to protect/select, such as UI text")
    parser.add_argument("--reclaim-translated-source-glyphs", action="store_true",
                        help="allow codes used only by translated source strings to become DTE slots")
    parser.add_argument("--protect-source-list", type=Path,
                        help="UTF-8 file containing source strings that must retain Japanese glyphs")
    parser.add_argument("--protect-binary-tail", type=Path,
                        help="binary whose non-string lookup-table glyph codes must remain intact")
    parser.add_argument("--protect-binary-tail-offset", type=lambda value: int(value, 0), default=0,
                        help="first byte of --protect-binary-tail to scan (default: 0)")
    args = parser.parse_args()

    with args.occurrences.open(encoding="utf-8", newline="") as source:
        occurrences = list(csv.DictReader(source, dialect="excel-tab"))
    extras: list[dict[str, str]] = []
    for path in args.extra_occurrences:
        with path.open(encoding="utf-8", newline="") as source:
            extras.extend(csv.DictReader(source, dialect="excel-tab"))
    members = set(args.member or [])
    relevant = [row for row in occurrences if not members or row["member"] in members]
    cache = load_best_by_source(args.cache)
    forced_protection = set()
    if args.protect_source_list and args.protect_source_list.exists():
        forced_protection = {
            json.loads(line) for line in args.protect_source_list.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }

    extra_budgets: dict[str, list[int]] = {}
    for row in extras:
        extra_budgets.setdefault(row["source"], []).append(int(row.get("field_bytes", 0)))

    def extra_size(source_text: str) -> int | None:
        # One-character executable strings are lookup fragments used to build
        # numbers, ranks, terrain values, dates, counters, and labels at
        # runtime. Encoding one as DTE would turn one dynamic character into a
        # two-character tile and corrupt every assembled value.
        if len(source_text) == 1:
            return None
        cached = cache.get(source_text, {})
        translation = str(cached.get("translation", ""))
        needed = required_pairs(translation) if row_is_valid(cached) and translation else None
        return paired_size(translation) if needed is not None else None

    def extra_fits_all(source_text: str) -> bool:
        size = extra_size(source_text)
        return size is not None and size <= min(extra_budgets[source_text])

    def extra_fits_any(source_text: str) -> bool:
        size = extra_size(source_text)
        return size is not None and size <= max(extra_budgets[source_text])

    # Never reuse a two-byte value still present in any extracted Japanese text,
    # including text outside the selected checkpoint.
    used_codes: set[bytes] = set()
    if args.reclaim_translated_source_glyphs:
        protected_stage = []
        for row in occurrences:
            source_text = row["source"]
            cached = cache.get(source_text, {})
            translated = str(cached.get("translation", ""))
            if source_text in forced_protection or not (translated and row_is_valid(cached)):
                protected_stage.append(row)
    else:
        protected_stage = occurrences
    protected = protected_stage + [row for row in extras if not extra_fits_all(row["source"])]
    for row in protected:
        raw = row["source"].encode("cp932")
        used_codes.update(raw[index:index + 2] for index in range(len(raw) - 1))
    # The main executable also contains fixed-width lookup arrays used to
    # assemble numbers, ranges, ranks, terrain values, and counters. They are
    # not NUL-terminated strings and therefore do not appear in the UI dump.
    # Conservatively reserve every renderer-mappable pair in the data tail.
    if args.protect_binary_tail:
        binary = args.protect_binary_tail.read_bytes()[args.protect_binary_tail_offset:]
        for index in range(len(binary) - 1):
            raw = binary[index:index + 2]
            try:
                direct_sjis_index(int.from_bytes(raw, "big"))
            except ValueError:
                continue
            used_codes.add(raw)
    codes = valid_codes(used_codes)

    selected: dict[str, str] = {}
    pairs: set[str] = set()
    selected_sources = {row["source"] for row in relevant}
    selected_sources.update(source_text for source_text in extra_budgets if extra_fits_any(source_text))
    for source_text in selected_sources:
        cached = cache.get(source_text, {})
        translation = str(cached.get("translation", ""))
        if not row_is_valid(cached) or not translation:
            continue
        needed = required_pairs(translation)
        if needed is None:
            continue
        selected[source_text] = translation
        pairs.update(needed)
    if len(pairs) > len(codes):
        parser.error(f"all-dialogue DTE needs {len(pairs)} pairs but only {len(codes)} safe glyph codes exist")

    assignment = dict(zip(sorted(pairs), codes))
    args.table.parent.mkdir(parents=True, exist_ok=True)
    with args.table.open("w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output, dialect="excel-tab")
        writer.writerow(("pair", "sjis", "notes"))
        for pair, raw in assignment.items():
            writer.writerow((pair, raw.hex().upper(), "all-dialogue whole-page DTE"))
    with args.selection.open("w", encoding="utf-8", newline="") as output:
        fields = ("source", "translation", "normal_bytes", "dte_bytes", "rescued_occurrences")
        writer = csv.DictWriter(output, fieldnames=fields, dialect="excel-tab")
        writer.writeheader()
        for source_text, translation in sorted(selected.items()):
            writer.writerow({
                "source": source_text,
                "translation": translation,
                "normal_bytes": len(encode(translation, {})[0]),
                "dte_bytes": paired_size(translation),
                "rescued_occurrences": "",
            })
    print(f"selected {len(selected)} translated strings using {len(pairs)}/{len(codes)} safe DTE glyph codes")


if __name__ == "__main__":
    main()
