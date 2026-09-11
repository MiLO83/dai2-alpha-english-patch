#!/usr/bin/env python3
"""Replace the five Japanese prologue cards in DATA/MTPRO.BIN."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent.parent
FONT = ROOT / "assets/UbuntuSansMono.ttf"
WIDTH = 640
HEIGHT = 224
PALETTE_SIZE = 0x200
RECORD_SIZE = PALETTE_SIZE + WIDTH * HEIGHT

CARDS = (
    (44, (37, 57, 78, 99, 119, 139, 159, 179), (
        "New A.D. 188.",
        "The Earth Sphere was rebuilding",
        "after the last war.",
        "With the Titans destroyed,",
        "the Federation reorganized",
        "and strengthened its forces",
        "against alien invaders and",
        "threats from underground.",
    )),
    (44, (37, 58, 79, 100, 118, 139, 159, 179), (
        "On Earth,",
        "the Daiku Maryu Corps was formed,",
        "bringing many Super Robots",
        "under its command.",
        "Separately, the Federation's",
        "secret defense group, GGG,",
        "prepared for emergencies and",
        "full-scale operations.",
    )),
    (44, (37, 58, 79, 99, 120, 139, 159), (
        "Meanwhile, in space,",
        "Londo Bell, based at the",
        "Londinium colony, investigated",
        "Neo Zeon remnants and other",
        "anti-Federation forces,",
        "including the Crossbone",
        "Vanguard.",
    )),
    (40, (37, 58, 78, 99, 119), (
        "Meanwhile, on Mars,",
        "alongside terraforming,",
        "Preventer built a military base",
        "as a bridgehead against",
        "alien invasion.",
    )),
    (40, (37, 58, 79, 99, 119, 139, 159), (
        "Thus, Earth's people left",
        "their fleeting peace behind",
        "and steadily prepared",
        "to resist invaders",
        "from above and below.",
        "All sensed the next war",
        "would soon begin...",
    )),
)


def rgba16(value: int) -> tuple[int, int, int, int]:
    return (
        (value & 0x1F) * 255 // 31,
        ((value >> 5) & 0x1F) * 255 // 31,
        ((value >> 10) & 0x1F) * 255 // 31,
        255 if value & 0x8000 else 0,
    )


def encode_card(
    record: bytearray, x: int, line_tops: tuple[int, ...], lines: tuple[str, ...]
) -> Image.Image:
    palette = [rgba16(int.from_bytes(record[i:i + 2], "little"))
               for i in range(0, PALETTE_SIZE, 2)]
    # This texture is used as an intensity/alpha mask by the game. Its CLUT
    # alpha bits are clear; index zero is transparent and nonzero RGB entries
    # carry the visible grayscale ramp.
    opaque = [i for i, color in enumerate(palette) if i and any(color[:3])]
    if not opaque:
        raise ValueError("card palette has no opaque colors")

    mask = Image.new("L", (WIDTH, HEIGHT), 0)
    draw = ImageDraw.Draw(mask)
    font = ImageFont.truetype(str(FONT), 18)
    for top, line in zip(line_tops, lines, strict=True):
        # Pillow's font bounding box has a variable top bearing. Offset each
        # line so its first painted row stays inside the original reveal band.
        bearing = draw.textbbox((0, 0), line, font=font)[1]
        draw.text((x, top - bearing), line, font=font, fill=248)

    levels = list(mask.getdata())
    nearest: dict[int, int] = {0: 0}
    for level in set(levels):
        if level:
            nearest[level] = min(
                opaque,
                key=lambda index: abs(sum(palette[index][:3]) // 3 - level),
            )
    record[PALETTE_SIZE:] = bytes(nearest[level] for level in levels)
    return Image.frombytes("P", (WIDTH, HEIGHT), bytes(record[PALETTE_SIZE:]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="original MTPRO.BIN")
    parser.add_argument("output", type=Path, help="patched MTPRO.BIN")
    parser.add_argument("--preview-dir", type=Path)
    args = parser.parse_args()

    data = bytearray(args.input.read_bytes())
    if len(data) < RECORD_SIZE * 6:
        parser.error(f"MTPRO.BIN is unexpectedly short: {len(data)} bytes")

    for index, (x, line_tops, lines) in enumerate(CARDS):
        start = index * RECORD_SIZE
        record = data[start:start + RECORD_SIZE]
        encode_card(record, x, line_tops, lines)
        data[start:start + RECORD_SIZE] = record
        if args.preview_dir:
            palette = [rgba16(int.from_bytes(record[i:i + 2], "little"))
                       for i in range(0, PALETTE_SIZE, 2)]
            preview = Image.new("RGBA", (WIDTH, HEIGHT))
            preview.putdata([
                (*palette[value][:3], 255 if value else 0)
                for value in record[PALETTE_SIZE:]
            ])
            args.preview_dir.mkdir(parents=True, exist_ok=True)
            preview.save(args.preview_dir / f"card-{index + 1}.png")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    print(f"patched {len(CARDS)} cards in {args.output}")


if __name__ == "__main__":
    main()
