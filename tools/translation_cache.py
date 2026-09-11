#!/usr/bin/env python3
"""Helpers for reading append-only translation caches safely."""

from __future__ import annotations

import json
from pathlib import Path


VALID_STATUSES = {"fits-all", "fits-some", "valid-overflow"}


def row_is_valid(row: dict[str, object]) -> bool:
    translation = str(row.get("translation", ""))
    if row.get("status") not in VALID_STATUSES or not translation or row.get("residual_japanese"):
        return False
    return True


def load_best_by_id(paths: list[Path]) -> dict[str, dict[str, object]]:
    """Return the latest valid row for each id, falling back to the latest row."""
    latest: dict[str, dict[str, object]] = {}
    valid: dict[str, dict[str, object]] = {}
    for path in paths:
        with path.open(encoding="utf-8") as source:
            for number, line in enumerate(source, 1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exception:
                    raise ValueError(f"{path}:{number}: malformed JSONL") from exception
                key = str(row["id"])
                latest[key] = row
                if row_is_valid(row):
                    valid[key] = row
    return {key: valid.get(key, row) for key, row in latest.items()}


def load_best_by_source(paths: list[Path]) -> dict[str, dict[str, object]]:
    """Return best cache rows keyed by their exact Japanese source text."""
    result: dict[str, dict[str, object]] = {}
    for row in load_best_by_id(paths).values():
        source = str(row.get("source", ""))
        if source:
            result[source] = row
    return result
