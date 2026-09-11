#!/usr/bin/env python3
"""Rebuild a hybrid ISO after replacing a file with a differently sized copy."""

from __future__ import annotations

import argparse
from pathlib import Path

import pycdlib


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("iso", type=Path)
    parser.add_argument("replacement", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--iso-path", required=True)
    parser.add_argument("--udf-path")
    args = parser.parse_args()

    image = pycdlib.PyCdlib()
    image.open(str(args.iso))
    image.rm_file(iso_path=args.iso_path, udf_path=args.udf_path)
    add_options = {"iso_path": args.iso_path}
    if args.udf_path:
        add_options["udf_path"] = args.udf_path
    image.add_file(str(args.replacement), **add_options)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    image.write(str(args.output))
    image.close()
    print(
        f"replaced {args.iso_path} with {args.replacement.stat().st_size} bytes "
        f"and rebuilt {args.output}"
    )


if __name__ == "__main__":
    main()
