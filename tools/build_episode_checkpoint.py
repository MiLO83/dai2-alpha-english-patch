#!/usr/bin/env python3
"""Build and verify one cumulative episode-order translation checkpoint."""

from __future__ import annotations

import argparse
import hashlib
import struct
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"


def run(*arguments: object) -> None:
    subprocess.run([sys.executable, *(str(value) for value in arguments)], check=True, cwd=ROOT)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("label")
    parser.add_argument("--member", action="append", required=True)
    parser.add_argument("--cache", type=Path, action="append", required=True)
    parser.add_argument("--iso", type=Path, default=Path("original/SLPS-25228.iso"))
    args = parser.parse_args()

    stem = ROOT / "work" / "translation" / args.label
    table = stem.with_name(stem.name + "-dte.tsv")
    selection = stem.with_name(stem.name + "-dte-selection.tsv")
    font = stem.with_name(stem.name + "-dte.P04")
    stage = stem.with_name(stem.name + "-expanded.BIN")
    elf = stem.with_name(stem.name + "-expanded.ELF")
    report = stem.with_name(stem.name + "-report.tsv")
    temporary_iso = stem.with_name(stem.name + "-stage-only.tmp.iso")
    allocated_iso = stem.with_name(stem.name + "-stage-elf.tmp.iso")
    output_iso = ROOT / "build" / "checkpoints" / f"SLPS-25228-English-{args.label}-first-pass.iso"
    member_args = [item for member in args.member for item in ("--member", member)]
    cache_args = [item for cache in args.cache for item in ("--cache", cache)]

    # DTE allocation uses the machine cache; reviewed overrides are still honored by relocation.
    run(TOOLS / "allocate_whole_page_dte.py", args.cache[0], "work/script/stage-occurrences.tsv", table, selection, *member_args)
    run(TOOLS / "font_patch.py", "work/analysis/FTALL.P04", font, "--dte-table", table)
    run(
        TOOLS / "relocate_stage_translations.py", "work/analysis/STAGE.BIN",
        "work/script/stage-occurrences.tsv", stage, *cache_args,
        "--report", report, *member_args, "--dte", table, "--dte-selection", selection,
    )
    run(TOOLS / "patch_overlay_allocations.py", "work/analysis/SLPS_252.28", stage, elf)
    run(
        TOOLS / "append_iso_extent.py", args.iso, stage, temporary_iso,
        "--directory-extent", "0x10B", "--iso-name", "STAGE.BIN;1",
    )
    run(
        TOOLS / "replace_iso_extent.py", temporary_iso, elf, allocated_iso,
        "--offset", "0xB5000",
    )
    run(TOOLS / "build_translation_iso.py", allocated_iso, output_iso, "--font", font)

    expected_stage = stage.read_bytes()
    expected_font = font.read_bytes()
    expected_elf = elf.read_bytes()
    with output_iso.open("rb") as image:
        image.seek(0x10B * 2048)
        directory = image.read(2048)
        name_offset = directory.find(b"STAGE.BIN;1")
        if name_offset < 33:
            raise SystemExit("STAGE.BIN ISO9660 record missing")
        record = name_offset - 33
        extent = struct.unpack_from("<I", directory, record + 2)[0]
        size = struct.unpack_from("<I", directory, record + 10)[0]
        image.seek(extent * 2048)
        actual_stage = image.read(size)
        image.seek(0x6DFA8800)
        actual_font = image.read(len(expected_font))
        image.seek(0xB5000)
        actual_elf = image.read(len(expected_elf))
    if actual_stage != expected_stage or actual_font != expected_font or actual_elf != expected_elf:
        raise SystemExit("checkpoint extent verification failed")
    if actual_stage.count(b"MWo3") != 298:
        raise SystemExit("checkpoint MWo3 member count changed")
    digest = hashlib.sha256(output_iso.read_bytes()).hexdigest()
    print(f"verified {output_iso} ({output_iso.stat().st_size} bytes)")
    print(f"SHA-256 {digest}")


if __name__ == "__main__":
    main()
