#!/usr/bin/env python3
"""Resumable bulk CP932 translation through a local Ollama server."""

from __future__ import annotations

import argparse
import csv
import json
import re
import time
import unicodedata
import urllib.request
from pathlib import Path

from allocate_whole_page_dte import paired_size
from dte_codec import encode
from translate_ollama import load_glossary


PROTECTED = re.compile(r"\$[A-Za-z]|\r?\n|[「」]")
JAPANESE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")


def mask(text: str) -> tuple[str, list[str]]:
    tokens: list[str] = []

    def replace(match: re.Match[str]) -> str:
        tokens.append(match.group())
        return f"<P{len(tokens) - 1}>"

    return PROTECTED.sub(replace, text), tokens


def restore(text: str, tokens: list[str]) -> str | None:
    for index, token in enumerate(tokens):
        marker = f"<P{index}>"
        if text.count(marker) != 1:
            return None
        text = text.replace(marker, token)
    if re.search(r"<P\d+>", text):
        return None
    return text


def normalize_english(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    for old, new in {
        "…": "...", "・": "-", "〜": "~", "—": "-", "–": "-",
        "‘": "'", "’": "'", "“": '"', "”": '"',
    }.items():
        text = text.replace(old, new)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = text.replace("「 ", "「").replace(" 」", "」")
    return text


def screen_layout_ok(text: str, width: int = 22, lines: int = 3) -> bool:
    visible = text.replace("「", "").replace("」", "")
    rows = visible.splitlines()
    return len(rows) <= lines and all(len(row) <= width for row in rows)


def cached_row_usable(row: dict[str, object]) -> bool:
    translation = str(row.get("translation", ""))
    return (
        # Retry anything that does not fit every occurrence. A fits-some or
        # valid-overflow result still leaves Japanese text in tighter slots.
        row.get("status") == "fits-all"
        and bool(translation)
        and not row.get("residual_japanese")
    )


def without_speaker(text: str) -> str | None:
    opening = text.find("「")
    if opening <= 0:
        return None
    prefix = text[:opening]
    if "\n" in prefix or "$" in prefix:
        return None
    return text[opening:]


def request(url: str, model: str, batch: list[dict[str, object]], glossary: list[tuple[str, str]], num_ctx: int, num_predict: int, line_width: int, whole_page_dte: bool) -> dict[str, str]:
    items = []
    for row in batch:
        source, tokens = mask(str(row["source"]))
        row["tokens"] = tokens
        terms = [f"{jp}={en}" for jp, en in glossary if jp in str(row["source"])]
        protected_bytes = sum(len(encode(token, {})[0]) for token in tokens)
        maximum_bytes = int(row["max_encoded_bytes"])
        items.append({
            "id": row["id"],
            "maximum_encoded_bytes": maximum_bytes,
            "maximum_english_characters_excluding_markers": max(
                0, (maximum_bytes - protected_bytes) // (1 if whole_page_dte else 2)
            ),
            "source": source,
            "required_terms": terms,
        })
    markers = sorted({f"<P{i}>" for row in batch for i in range(len(row["tokens"]))})
    prompt = """Translate each Japanese Super Robot Wars text into concise natural English. /no_think
Return exactly one result for every id, in the same order. Copy each listed protected marker exactly once and in order.
The markers represent immutable controls and newlines. Never translate, move, add, or remove them.
Use plain ASCII English inside the tokens. Preserve meaning and established names. Do not add commentary.
Never invent profanity, sexual language, jokes, speaker names, or information absent from the Japanese source.
Translate and retain a speaker label appearing before an opening-dialogue marker. Omit that label only if retaining it makes the mandatory limit impossible.
The literal Japanese brackets 「 and 」 delimit spoken text. Preserve them exactly and keep the speaker label before 「.
Each ordinary English character encodes as two bytes. The stated character and byte maximums are mandatory.
Compress or abbreviate while retaining the core meaning. Never exceed either maximum.
For dialogue containing 「 and 」, every visible line must be at most """ + str(line_width) + """ characters,
counting the speaker label but not 「 or 」. Keep the existing protected newline markers,
so phrase each corresponding line separately within the same limit. Use no more than three
visible lines. Prefer short established names and natural contractions.

The only literal protected markers present in this batch are: """ + repr(markers) + """

INPUT:
""" + json.dumps(items, ensure_ascii=False)
    schema = {
        "type": "object",
        "properties": {
            "translations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"id": {"type": "string"}, "english": {"type": "string"}},
                    "required": ["id", "english"],
                },
            }
        },
        "required": ["translations"],
    }
    body = json.dumps({
        "model": model, "prompt": prompt, "stream": False, "format": schema,
        "options": {"temperature": 0.1, "top_p": 0.85, "num_ctx": num_ctx, "num_predict": num_predict},
    }, ensure_ascii=False).encode()
    req = urllib.request.Request(url.rstrip("/") + "/api/generate", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as response:
        parsed = json.loads(json.load(response)["response"])
    answers = {item["id"]: item["english"] for item in parsed["translations"]}
    expected = {str(row["id"]) for row in batch}
    unexpected = set(answers) - expected
    if unexpected:
        raise ValueError(f"response contains unexpected ids: {sorted(unexpected)}")
    # A large structured response may omit a few requested IDs. Preserve its
    # correctly keyed subset; resumable retries will request the omissions.
    return answers


def request_compression(url: str, model: str, row: dict[str, object], draft: str, tokens: list[str], num_ctx: int, line_width: int, whole_page_dte: bool) -> str:
    source, _ = mask(str(row["source"]))
    budget = int(row["max_encoded_bytes"])
    control_bytes = sum(len(encode(token, {})[0]) for token in tokens)
    restored_limit = max(
        1,
        (budget - control_bytes) // (1 if whole_page_dte else 2)
        + sum(len(token) for token in tokens),
    )
    marker_extra = sum(len(f"<P{i}>") - len(token) for i, token in enumerate(tokens))
    schema_limit = max(1, restored_limit + marker_extra)
    prompt = f"""Shorten this English game UI string or subtitle so it fits the mandatory character limit. /no_think
Return only JSON. Keep the core action and tone. Use terse natural English and ASCII punctuation.
Keep speaker name before 「 if it fits; otherwise omit only the speaker name. Preserve literal 「 and 」 in order.
Never truncate a word or proper name. If necessary, omit a less important phrase instead.
Copy every existing protected marker exactly once and in order. Never invent text or profanity.
Maximum output characters including brackets and markers: {schema_limit}
For dialogue containing 「 and 」, every restored visible line must be at most {line_width} characters,
counting the speaker label but not the brackets. Count carefully before answering.
Japanese source: {source}
Overlong draft: {draft}
"""
    schema = {
        "type": "object",
        "properties": {"english": {"type": "string", "maxLength": schema_limit}},
        "required": ["english"],
    }
    body = json.dumps({
        "model": model, "prompt": prompt, "stream": False, "format": schema,
        "options": {"temperature": 0.1, "top_p": 0.85, "num_ctx": num_ctx, "num_predict": 2048},
    }, ensure_ascii=False).encode()
    req = urllib.request.Request(url.rstrip("/") + "/api/generate", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as response:
        return json.loads(json.load(response)["response"])["english"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path, help="Append-only JSONL translation cache")
    parser.add_argument("--model", default="qwen3.5:latest")
    parser.add_argument("--url", default="http://127.0.0.1:11434")
    parser.add_argument("--glossary", type=Path)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--retry-rejected", action="store_true")
    parser.add_argument("--compress-overflow", action="store_true")
    parser.add_argument("--num-ctx", type=int, default=8192)
    parser.add_argument("--num-predict", type=int, default=4096)
    parser.add_argument("--line-width", type=int, default=22)
    parser.add_argument("--whole-page-dte", action="store_true")
    args = parser.parse_args()

    with args.input.open(encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source, dialect="excel-tab"))
    completed: set[str] = set()
    if args.output.exists():
        for line in args.output.read_text(encoding="utf-8").splitlines():
            if line.strip():
                prior = json.loads(line)
                if not args.retry_rejected or cached_row_usable(prior):
                    completed.add(prior["id"])
    pending = [row for row in rows if row["id"] not in completed]
    if args.limit:
        pending = pending[: args.limit]
    glossary = load_glossary(args.glossary)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    with args.output.open("a", encoding="utf-8") as output:
        for start in range(0, len(pending), args.batch_size):
            batch: list[dict[str, object]] = pending[start : start + args.batch_size]
            error = ""
            answers: dict[str, str] = {}
            for attempt in range(3):
                try:
                    answers = request(
                        args.url, args.model, batch, glossary, args.num_ctx, args.num_predict,
                        args.line_width, args.whole_page_dte,
                    )
                    break
                except Exception as exception:
                    error = str(exception)
                    time.sleep(2 ** attempt)
            for row in batch:
                tokens = row.get("tokens", [])
                restored = restore(answers.get(row["id"], ""), tokens) if row["id"] in answers else None
                if restored is not None:
                    restored = normalize_english(restored)
                encoded = None
                speaker_omitted = False
                if restored is not None:
                    try:
                        encoded = paired_size(restored) if args.whole_page_dte else len(encode(restored, {})[0])
                    except UnicodeEncodeError as exception:
                        error = str(exception)
                minimum_budget = int(row["min_encoded_bytes"])
                maximum_budget = int(row["max_encoded_bytes"])
                if restored is not None and encoded is not None and "「" in str(row["source"]) and (
                    encoded > maximum_budget or not screen_layout_ok(restored, width=args.line_width)
                ):
                    shortened = without_speaker(restored)
                    if shortened is not None:
                        shortened_size = paired_size(shortened) if args.whole_page_dte else len(encode(shortened, {})[0])
                        if shortened_size <= maximum_budget and screen_layout_ok(shortened, width=args.line_width):
                            restored, encoded, speaker_omitted = shortened, shortened_size, True
                if args.compress_overflow and restored is not None and encoded is not None and (
                    encoded > maximum_budget or (
                        "「" in str(row["source"]) and not screen_layout_ok(restored, width=args.line_width)
                    )
                ):
                    for _ in range(2):
                        try:
                            compressed = request_compression(
                                args.url, args.model, row, restored, tokens, args.num_ctx,
                                args.line_width, args.whole_page_dte,
                            )
                            compressed = restore(compressed, tokens)
                            if compressed is None:
                                continue
                            compressed = normalize_english(compressed)
                            compressed_size = paired_size(compressed) if args.whole_page_dte else len(encode(compressed, {})[0])
                            if compressed_size <= maximum_budget and screen_layout_ok(compressed, width=args.line_width):
                                speaker_omitted = "「" in compressed and compressed.startswith("「")
                                restored, encoded = compressed, compressed_size
                                break
                        except Exception as exception:
                            error = str(exception)
                brackets_ok = restored is not None and [c for c in str(row["source"]) if c in "「」"] == [c for c in restored if c in "「」"]
                structurally_valid = restored is not None and encoded is not None and brackets_ok
                layout_ok = bool(restored and ("「" not in restored or screen_layout_ok(restored, width=args.line_width)))
                residual_japanese = bool(restored and JAPANESE.search(restored))
                result = {
                    "id": row["id"], "source": row["source"], "translation": restored or "",
                    "minimum_budget": minimum_budget, "maximum_budget": maximum_budget,
                    "encoded_bytes": encoded,
                    "speaker_omitted": speaker_omitted,
                    "status": (
                        "residual-japanese" if structurally_valid and residual_japanese else
                        "layout-overflow" if structurally_valid and not layout_ok else
                        "fits-all" if structurally_valid and encoded <= minimum_budget else
                        "fits-some" if structurally_valid and encoded <= maximum_budget else
                        "valid-overflow" if structurally_valid else "rejected"
                    ),
                    "layout_ok": layout_ok,
                    "residual_japanese": residual_japanese, "error": error,
                }
                output.write(json.dumps(result, ensure_ascii=False) + "\n")
                output.flush()
            print(f"processed {min(start + len(batch), len(pending))}/{len(pending)}", flush=True)


if __name__ == "__main__":
    main()
