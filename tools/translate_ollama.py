#!/usr/bin/env python3
"""Translate a small, reviewable TSV batch through a local Ollama model."""

from __future__ import annotations

import argparse
import csv
import json
import re
import urllib.request
from pathlib import Path

from dte_codec import encode, load_pairs


TOKEN = re.compile(r"\$[A-Za-z]|\r?\n")
DIALOGUE = re.compile(r"[「」（）]")
RESIDUAL_PLACEHOLDER = re.compile(r"[<\[]P\d+[>\]]")


def protected(text: str) -> list[str]:
    return TOKEN.findall(text)


def masked(text: str) -> tuple[str, list[tuple[str, str]]]:
    replacements: list[tuple[str, str]] = []

    def replace(match: re.Match[str]) -> str:
        marker = f"<P{len(replacements)}>"
        replacements.append((marker, match.group()))
        return marker

    return TOKEN.sub(replace, text), replacements


def load_glossary(path: Path | None) -> list[tuple[str, str]]:
    if path is None:
        return []
    with path.open(encoding="utf-8", newline="") as source:
        return [(row["japanese"], row["english"]) for row in csv.DictReader(source, dialect="excel-tab")]


def request_translation(
    url: str,
    model: str,
    row: dict[str, str],
    glossary: list[tuple[str, str]],
    feedback: str = "",
) -> str:
    source, replacements = masked(row["source"])
    relevant = [f"{jp} = {en}" for jp, en in glossary if jp in row["source"]]
    glossary_prompt = "\nRequired terminology:\n" + "\n".join(relevant) if relevant else ""
    prompt = f"""Translate this Japanese video-game dialogue into concise, natural English.
This is Super Robot Wars dialogue. Preserve characterization and established romanized proper names.
Text inside angle brackets such as <P0> is an immutable placeholder: copy each exactly once and in order.
Translate speaker names as well as dialogue. Do not add explanations or stray brackets.
The byte limit is metadata: be concise, but preserve the complete meaning.
Return only the requested JSON object.

Maximum encoded bytes: {row['min_encoded_bytes']}
Japanese: {source}
{glossary_prompt}
{feedback}
"""
    schema = {
        "type": "object",
        "properties": {
            "english": {"type": "string"},
        },
        "required": ["english"],
    }
    payload = json.dumps(
        {"model": model, "prompt": prompt, "stream": False, "format": schema},
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        url.rstrip("/") + "/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=600) as response:
        result = json.load(response)
    english = json.loads(result["response"])["english"]
    for marker, original in replacements:
        english = english.replace(marker, original)
    return english


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--model", default="qwen3.5:latest")
    parser.add_argument("--url", default="http://127.0.0.1:11434")
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--glossary", type=Path)
    parser.add_argument("--dte", type=Path)
    parser.add_argument("--attempts", type=int, default=3)
    args = parser.parse_args()

    with args.input.open(encoding="utf-8", newline="") as source:
        candidates = list(csv.DictReader(source, dialect="excel-tab"))
    rows = [row for row in candidates if DIALOGUE.search(row["source"])][: args.limit]
    glossary = load_glossary(args.glossary)
    pairs = load_pairs(args.dte) if args.dte else {}
    output_rows = []
    for row in rows:
        feedback = ""
        english = ""
        encoded_bytes = None
        tokens_ok = False
        error = ""
        for _ in range(args.attempts):
            english = request_translation(args.url, args.model, row, glossary, feedback)
            tokens_ok = protected(row["source"]) == protected(english)
            if not tokens_ok or RESIDUAL_PLACEHOLDER.search(english):
                tokens_ok = False
                feedback = "Your prior answer changed an immutable placeholder. Preserve every placeholder exactly."
                continue
            try:
                raw, _ = encode(english, pairs)
                encoded_bytes = len(raw)
            except UnicodeEncodeError as exception:
                error = str(exception)
                feedback = "Use only plain ASCII English punctuation and characters supported by CP932."
                continue
            budget = int(row["min_encoded_bytes"])
            if encoded_bytes <= budget:
                break
            feedback = (
                f"Your prior translation encoded to {encoded_bytes} bytes, exceeding the {budget}-byte limit. "
                "Rewrite it much more concisely while preserving meaning, speaker, and placeholders."
            )
        fits = encoded_bytes is not None and encoded_bytes <= int(row["min_encoded_bytes"])
        output_rows.append(
            {
                "id": row["id"],
                "min_encoded_bytes": row["min_encoded_bytes"],
                "source": row["source"],
                "translation": english,
                "tokens_ok": "yes" if tokens_ok else "NO",
                "encoded_bytes": "" if encoded_bytes is None else encoded_bytes,
                "status": "draft-fits" if tokens_ok and fits else "needs-review",
                "error": error,
            }
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(output_rows[0]), dialect="excel-tab")
        writer.writeheader()
        writer.writerows(output_rows)
    invalid = sum(row["tokens_ok"] == "NO" for row in output_rows)
    print(f"wrote {len(output_rows)} drafts to {args.output}; invalid token sets: {invalid}")


if __name__ == "__main__":
    main()
