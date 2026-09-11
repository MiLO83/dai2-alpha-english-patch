#!/usr/bin/env python3
"""Export and rebuild the game from a three-column human-editable TSV."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
HEADERS = ("Original Japanese", "Automatic Translation", "English")
SOURCE_ISO_SHA256 = "1f63e4acb06a689221a021a693063291d9448bb71776e6bd3d2da050de3cefdd"
STAGE_EXTENT = (0x6EE0B800, 8_484_480, "d3aed6168c7c4d913d641b39ec93e0245811cf737f803866b8b62b1ff9b8ae87")
FONT_EXTENT = (0x6DFA8800, 806_400, "123bbf7cdb61ca8adf38eb5f9049dbd3e85a1873821937d9838802f9ddde9cdc")
ELF_EXTENT = (0xB5000, 3_542_656, "c8079e2abace5df3a3c60a6410cff48ed5514e5b2601aca1b808a59c1f714450")
CONTROL = re.compile(r"\$[A-Za-z]")
JAPANESE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")


def read_tsv(path: Path, scope: str | None = None) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source, dialect="excel-tab")
        fields = tuple(reader.fieldnames or ())
        if fields not in (HEADERS, ("Scope",) + HEADERS):
            raise SystemExit(f"{path}: expected Scope (optional), then: {', '.join(HEADERS)}")
        rows = list(reader)
        if fields[0] == "Scope" and scope:
            rows = [row for row in rows if row["Scope"] == scope]
        return rows


def export_table(path: Path, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise SystemExit(f"refusing to overwrite existing table: {path} (use --force)")
    occurrences = ROOT / "work/script/stage-occurrences.tsv"
    selection = ROOT / "work/translation/full-game-second-pass-all-dte-selection.tsv"
    with occurrences.open(encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source, dialect="excel-tab"))
    with selection.open(encoding="utf-8", newline="") as source:
        automatic = {row["source"]: row["translation"] for row in csv.DictReader(source, dialect="excel-tab")}
    unique: dict[str, None] = {}
    for row in rows:
        unique.setdefault(row["source"], None)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=HEADERS, dialect="excel-tab")
        writer.writeheader()
        for japanese in unique:
            writer.writerow({
                "Original Japanese": japanese,
                "Automatic Translation": automatic.get(japanese, ""),
                "English": "",
            })
    print(f"exported {len(unique)} unique strings to {path}")
    print(f"automatic={sum(bool(automatic.get(text)) for text in unique)} untranslated={sum(not automatic.get(text) for text in unique)}")


def validate_english(source: str, english: str, row_number: int) -> None:
    if JAPANESE.search(english):
        raise SystemExit(f"row {row_number}: English selection still contains Japanese")
    if CONTROL.findall(source) != CONTROL.findall(english):
        raise SystemExit(f"row {row_number}: control codes differ from Original Japanese")
    if [c for c in source if c in "「」"] != [c for c in english if c in "「」"]:
        raise SystemExit(f"row {row_number}: keep the original 「 and 」 dialogue delimiters")


def run(command: list[str]) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, check=True, cwd=ROOT)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(8 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def extract_verified(source_iso: Path, output: Path, extent: tuple[int, int, str]) -> None:
    offset, size, expected = extent
    if output.exists() and output.stat().st_size == size and sha256(output) == expected:
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    with source_iso.open("rb") as source:
        source.seek(offset)
        data = source.read(size)
    if hashlib.sha256(data).hexdigest() != expected:
        raise SystemExit(f"could not verify extracted game data for {output.name}")
    output.write_bytes(data)


def build(table: Path, ui_table: Path, source_iso: Path, output_iso: Path, force: bool, font: Path) -> None:
    rows = read_tsv(table, "dialogue")
    ui_rows = read_tsv(ui_table, "ui") if ui_table.exists() else []
    if output_iso.exists() and not force:
        raise SystemExit(f"refusing to overwrite existing ISO: {output_iso} (use --force)")
    if sha256(source_iso) != SOURCE_ISO_SHA256:
        raise SystemExit("source ISO is not the verified unmodified SLPS-25228 disc")

    analysis = ROOT / "work/analysis"
    clean_stage = analysis / "STAGE.BIN"
    clean_font = analysis / "FTALL.P04"
    clean_elf = analysis / "SLPS_252.28"
    extract_verified(source_iso, clean_stage, STAGE_EXTENT)
    extract_verified(source_iso, clean_font, FONT_EXTENT)
    extract_verified(source_iso, clean_elf, ELF_EXTENT)
    work = ROOT / "work/editor-build"
    work.mkdir(parents=True, exist_ok=True)
    cache = work / "selected-translations.jsonl"
    manual = automatic = original = 0
    manual_sources: set[str] = set()
    ui_manual_sources = {row["Original Japanese"] for row in ui_rows if row["English"].strip()}
    with cache.open("w", encoding="utf-8") as output:
        for number, row in enumerate(rows + ui_rows, 2):
            source = row["Original Japanese"]
            if row["English"].strip():
                chosen = row["English"]
                manual += 1
                manual_sources.add(source)
            elif row["Automatic Translation"].strip():
                chosen = row["Automatic Translation"]
                automatic += 1
            else:
                original += 1
                continue
            validate_english(source, chosen, number)
            output.write(json.dumps({
                "id": f"editor-{number:05d}", "source": source, "translation": chosen,
                "status": "valid-overflow", "residual_japanese": False,
            }, ensure_ascii=False) + "\n")

    occurrences = ROOT / "data/stage-occurrences.tsv"
    if not occurrences.exists():
        occurrences = ROOT / "work/script/stage-occurrences.tsv"
    dte = work / "editable-dte.tsv"
    selection = work / "editable-dte-selection.tsv"
    stage = work / "editable-STAGE.BIN"
    report = work / "editable-build-report.tsv"
    patched_font = work / "editable-FTALL.P04"
    patched_elf = work / "editable-SLPS_252.28"
    ui_report = work / "editable-ui-build-report.tsv"
    fallback_sources = work / "stage-fallback-sources.txt"
    python = sys.executable

    run([python, "tools/allocate_all_dialogue_dte.py", str(occurrences), str(dte),
         str(selection), "--cache", str(cache), "--extra-occurrences", "data/ui-occurrences.tsv",
         "--reclaim-translated-source-glyphs", "--protect-binary-tail", str(clean_elf),
         "--protect-binary-tail-offset", "0x330000"])
    run([python, "tools/apply_translation_slot_swap.py", str(clean_stage),
         str(occurrences), str(stage), "--cache", str(cache), "--report", str(report),
         "--dte", str(dte)])
    with report.open(encoding="utf-8", newline="") as source:
        fallback = sorted({
            row["source"] for row in csv.DictReader(source, dialect="excel-tab")
            if row["status"].startswith("japanese-")
        })
    fallback_sources.write_text(
        "".join(json.dumps(text, ensure_ascii=False) + "\n" for text in fallback), encoding="utf-8"
    )
    # Reallocate once with every actual fallback protected, then rebuild the
    # overlay. Pair sizes do not change, so the slot assignment is stable.
    run([python, "tools/allocate_all_dialogue_dte.py", str(occurrences), str(dte),
         str(selection), "--cache", str(cache), "--extra-occurrences", "data/ui-occurrences.tsv",
         "--reclaim-translated-source-glyphs", "--protect-source-list", str(fallback_sources),
         "--protect-binary-tail", str(clean_elf), "--protect-binary-tail-offset", "0x330000"])
    run([python, "tools/apply_translation_slot_swap.py", str(clean_stage),
         str(occurrences), str(stage), "--cache", str(cache), "--report", str(report),
         "--dte", str(dte)])
    with report.open(encoding="utf-8", newline="") as source:
        failed_manual = [
            row for row in csv.DictReader(source, dialect="excel-tab")
            if row["source"] in manual_sources and row["status"] not in ("applied-swapped", "applied-fixed")
        ]
    if failed_manual:
        sample = ", ".join(f"{row['id']}={row['status']}" for row in failed_manual[:8])
        raise SystemExit(
            f"{len(failed_manual)} manual-English occurrence(s) could not be inserted; "
            f"shorten/fix them and consult {report}. First failures: {sample}"
        )
    run([python, "tools/font_patch.py", str(clean_font), str(patched_font),
         "--dte-table", str(dte), "--ttf", str(font), "--ttf-size", "16",
         "--ttf-variation", "Medium", "--ttf-monochrome"])
    if ui_rows:
        run([python, "tools/apply_elf_ui_translations.py", str(clean_elf), str(ui_table),
             "data/ui-occurrences.tsv", str(patched_elf), "--dte", str(dte),
             "--report", str(ui_report)])
        with ui_report.open(encoding="utf-8", newline="") as source:
            failed_ui_manual = [
                row for row in csv.DictReader(source, dialect="excel-tab")
                if row["source"] in ui_manual_sources and row["status"] != "applied"
            ]
        if failed_ui_manual:
            sample = ", ".join(f"{row['id']}={row['status']}" for row in failed_ui_manual[:8])
            raise SystemExit(
                f"{len(failed_ui_manual)} manual UI occurrence(s) could not be inserted; "
                f"shorten/fix them and consult {ui_report}. First failures: {sample}"
            )
    if output_iso.exists():
        output_iso.unlink()
    run([python, "tools/build_translation_iso.py", str(source_iso), str(output_iso),
         "--elf", str(patched_elf), "--stage", str(stage), "--font", str(patched_font)] if ui_rows else
        [python, "tools/build_translation_iso.py", str(source_iso), str(output_iso),
         "--stage", str(stage), "--font", str(patched_font)])
    print(f"selection: manual={manual} automatic={automatic} original={original}; ui_rows={len(ui_rows)}")
    print(f"built {output_iso}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export", help="create the three-column TSV")
    export.add_argument("table", type=Path, nargs="?", default=ROOT / "translation/game-script.tsv")
    export.add_argument("--force", action="store_true")
    builder = commands.add_parser("build", help="build an ISO using English, automatic, original priority")
    builder.add_argument("table", type=Path, nargs="?", default=ROOT / "translation/game-script.tsv")
    builder.add_argument("source_iso", type=Path, nargs="?", default=ROOT / "original/SLPS-25228.iso")
    builder.add_argument("output_iso", type=Path, nargs="?", default=ROOT / "build/SLPS-25228-English-edited.iso")
    builder.add_argument("--font", type=Path, default=ROOT / "assets/UbuntuSansMono.ttf")
    builder.add_argument("--ui-table", type=Path, default=ROOT / "translation/ui-script.tsv")
    builder.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.command == "export":
        export_table(args.table, args.force)
    else:
        build(args.table, args.ui_table, args.source_iso, args.output_iso, args.force, args.font)


if __name__ == "__main__":
    main()
