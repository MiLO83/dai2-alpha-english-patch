#!/usr/bin/env python3
"""Build the editable translation workflow ZIP from an explicit safe manifest."""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PREFIX = "dai2-alpha-english-editable-patch"
FORBIDDEN = {".iso", ".bin", ".p04", ".img", ".mdf", ".p2s"}


def manifest() -> list[Path]:
    files = [ROOT / "PACKAGE-README.md", ROOT / "README.md"]
    for directory in ("assets", "config", "data", "patches", "translation"):
        files.extend(path for path in (ROOT / directory).rglob("*") if path.is_file())
    files.extend(path for path in (ROOT / "tools").glob("*.py") if path.is_file())
    files.extend(path for path in (ROOT / "tools").glob("*.sh") if path.is_file())
    if (ROOT / "tools/xdelta3").is_file():
        files.append(ROOT / "tools/xdelta3")
    return sorted(set(files))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, nargs="?",
                        default=ROOT / "release/dai2-alpha-english-editable-patch.zip")
    args = parser.parse_args()
    files = manifest()
    forbidden = [path for path in files if path.suffix.lower() in FORBIDDEN]
    if forbidden:
        parser.error("forbidden game-image files in manifest: " + ", ".join(map(str, forbidden)))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            archive.write(path, f"{PREFIX}/{path.relative_to(ROOT).as_posix()}")
    print(f"packed {len(files)} files into {args.output}")


if __name__ == "__main__":
    main()
