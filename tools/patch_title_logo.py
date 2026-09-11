#!/usr/bin/env python3
"""Replace the title-screen logo stored in DATA/NEWFACE.BIN in a PS2 ISO."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from PIL import Image


NEWFACE_LBA = 961845
SECTOR_SIZE = 2048
PAGE_OFFSET = 0x0583A750
PALETTE_OFFSET = 0x0587AB50
PAGE_SIZE = 256
LOGO_BOX = (8, 16, 256, 96)


def rgba16(value: int) -> tuple[int, int, int, int]:
    return (
        (value & 0x1F) * 255 // 31,
        ((value >> 5) & 0x1F) * 255 // 31,
        ((value >> 10) & 0x1F) * 255 // 31,
        255 if value & 0x8000 else 0,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_iso", type=Path)
    parser.add_argument("logo", type=Path, help="248x80 RGBA replacement PNG")
    parser.add_argument("output_iso", type=Path)
    parser.add_argument("--preview", type=Path)
    args = parser.parse_args()

    logo = Image.open(args.logo).convert("RGBA")
    if logo.size != (248, 80):
        parser.error(f"logo must be 248x80, not {logo.size[0]}x{logo.size[1]}")

    base = NEWFACE_LBA * SECTOR_SIZE
    with args.input_iso.open("rb") as source:
        source.seek(base + PAGE_OFFSET)
        indices = bytearray(source.read(PAGE_SIZE * PAGE_SIZE))
        source.seek(base + PALETTE_OFFSET)
        palette_raw = source.read(512)
    if len(indices) != PAGE_SIZE * PAGE_SIZE or len(palette_raw) != 512:
        parser.error("input ISO is truncated")

    palette = [rgba16(int.from_bytes(palette_raw[i:i + 2], "little"))
               for i in range(0, 512, 2)]
    # The GS treats alpha bit 0x8000 as its normal half-range opacity. Match
    # transparent source pixels only to transparent CLUT entries; visible
    # pixels only to visible entries so dark outlines cannot disappear.
    transparent = [i for i, color in enumerate(palette) if color[3] == 0]
    visible = [i for i, color in enumerate(palette) if color[3] != 0]
    cache: dict[tuple[int, int, int, int], int] = {}

    def nearest(color: tuple[int, int, int, int]) -> int:
        if color in cache:
            return cache[color]
        candidates = transparent if color[3] < 64 else visible
        if not candidates:
            candidates = list(range(256))
        r, g, b, _ = color
        result = min(candidates, key=lambda i: (
            (palette[i][0] - r) ** 2
            + (palette[i][1] - g) ** 2
            + (palette[i][2] - b) ** 2
        ))
        cache[color] = result
        return result

    # The title scene also draws legacy auxiliary pieces from this logo-only
    # page. Clear them before inserting the complete English artwork; otherwise
    # they appear as a slash, shard, and horizontal bands over the new logo.
    clear_index = min(transparent, key=lambda i: sum(palette[i][:3]))
    indices[:] = bytes([clear_index]) * len(indices)

    x0, y0, _, _ = LOGO_BOX
    for y in range(80):
        for x in range(248):
            indices[(y0 + y) * PAGE_SIZE + x0 + x] = nearest(logo.getpixel((x, y)))

    args.output_iso.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(args.input_iso, args.output_iso)
    with args.output_iso.open("r+b") as output:
        output.seek(base + PAGE_OFFSET)
        output.write(indices)

    if args.preview:
        preview = Image.new("RGBA", (PAGE_SIZE, PAGE_SIZE))
        preview.putdata([palette[index] for index in indices])
        args.preview.parent.mkdir(parents=True, exist_ok=True)
        preview.save(args.preview)
    print(f"patched native title logo in {args.output_iso}")


if __name__ == "__main__":
    main()
