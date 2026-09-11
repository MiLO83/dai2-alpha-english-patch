#!/usr/bin/env python3
"""Recover cached translations that fit the real whole-page DTE constraints."""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from pathlib import Path

from allocate_whole_page_dte import paired_size
from bulk_translate_ollama import normalize_english
from translate_ollama import protected


JAPANESE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")
UNSAFE = re.compile(r"[^\x20-\x7e\n\r\t「」]")
BLOCKED_WORDS = re.compile(r"\b(fuck|fucker|motherfucker|shit|cunt)\b", re.I)


def fold_safe_ascii(text: str) -> str:
    """Fold Latin diacritics and a few unambiguous technical symbols only."""
    text = text.translate(str.maketrans({
        "≤": "<=", "ν": "nu", "α": "alpha", "β": "beta",
        "„": '"', "·": "-", "е": "e",
    }))
    result: list[str] = []
    for character in text:
        if ord(character) > 0x7f and "LATIN" in unicodedata.name(character, ""):
            folded = unicodedata.normalize("NFKD", character).encode("ascii", "ignore").decode()
            result.append(folded or character)
        else:
            result.append(character)
    return "".join(result)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help="Translation-input TSV with byte budgets")
    parser.add_argument("cache", type=Path, help="Existing JSONL cache")
    parser.add_argument("output", type=Path, help="Append-only recovered JSONL cache")
    args = parser.parse_args()

    latest: dict[str, dict[str, object]] = {}
    with args.cache.open(encoding="utf-8") as source:
        for line in source:
            if line.strip():
                row = json.loads(line)
                latest[str(row["id"])] = row

    recovered: list[dict[str, object]] = []
    with args.input.open(encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source, dialect="excel-tab"):
            prior = latest.get(row["id"])
            if not prior or not prior.get("translation"):
                continue
            translation = fold_safe_ascii(normalize_english(str(prior["translation"])))
            source_text = row["source"]
            if JAPANESE.search(translation) or UNSAFE.search(translation) or BLOCKED_WORDS.search(translation):
                continue
            if protected(source_text) != protected(translation):
                continue
            if [c for c in source_text if c in "「」"] != [c for c in translation if c in "「」"]:
                continue
            if "「" in source_text:
                lines = translation.replace("「", "").replace("」", "").splitlines()
                if len(lines) > 3 or any(len(line) > 44 for line in lines):
                    continue
            encoded = paired_size(translation)
            minimum = int(row["min_encoded_bytes"])
            maximum = int(row["max_encoded_bytes"])
            if encoded > maximum:
                continue
            recovered.append({
                "id": row["id"], "source": source_text, "translation": translation,
                "minimum_budget": minimum, "maximum_budget": maximum,
                "encoded_bytes": encoded, "speaker_omitted": prior.get("speaker_omitted", False),
                "status": "fits-all" if encoded <= minimum else "fits-some",
                "layout_ok": True, "residual_japanese": False,
                "error": "revalidated for 44-character whole-page DTE layout",
            })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("a", encoding="utf-8") as output:
        for row in recovered:
            output.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"recovered {len(recovered)} DTE translations")


if __name__ == "__main__":
    main()
