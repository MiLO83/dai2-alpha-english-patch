#!/usr/bin/env python3
"""Make controlled, reversible edits to Dai-2 Alpha's FTALL.P04 atlas."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


ATLAS_WIDTH = 320
ATLAS_STRIDE = ATLAS_WIDTH // 2
GLYPH_WIDTH = 18
GLYPH_HEIGHT = 18
GLYPH_COLUMNS = 16


def direct_sjis_index(code: int) -> int:
    """Implement the retail renderer's SJIS-to-atlas mapping."""
    lead = code >> 8
    trail = code & 0xFF
    adjustments = {
        0x81: 0x8140,
        0x82: 0x8180,
        0x83: 0x81C0,
        0x84: 0x8200,
        0x87: 0x82C0,
        0x88: 0x8300,
    }
    if lead in adjustments:
        index = code - adjustments[lead]
    elif 0x89 <= lead <= 0x97 or (lead == 0x98 and trail < 0x73):
        # Confirmed at EE 0x001252D8: (lead - 0x89) * 0xC0 + 0x5C0 + trail.
        index = (lead - 0x89) * 0xC0 + 0x5C0 + trail
    else:
        raise ValueError("SJIS code is not in one of the renderer's mapped ranges")
    if not 0 <= index < GLYPH_COLUMNS * 280:
        raise ValueError(f"SJIS code {code:04X} maps outside FTALL.P04")
    return index


def pixel_offset(index: int, x: int, y: int) -> tuple[int, bool]:
    glyph_x = (index % GLYPH_COLUMNS) * GLYPH_WIDTH
    glyph_y = (index // GLYPH_COLUMNS) * GLYPH_HEIGHT
    atlas_x = glyph_x + x
    offset = (glyph_y + y) * ATLAS_STRIDE + atlas_x // 2
    return offset, bool(atlas_x & 1)


def set_pixel(font: bytearray, index: int, x: int, y: int, color: int) -> None:
    offset, high_nibble = pixel_offset(index, x, y)
    if high_nibble:
        font[offset] = (font[offset] & 0x0F) | (color << 4)
    else:
        font[offset] = (font[offset] & 0xF0) | color


def get_pixel(font: bytes | bytearray, index: int, x: int, y: int) -> int:
    offset, high_nibble = pixel_offset(index, x, y)
    return font[offset] >> 4 if high_nibble else font[offset] & 0x0F


def mark_glyph(font: bytearray, index: int, color: int) -> None:
    """Replace one cell with a boxed X test marker."""
    for y in range(GLYPH_HEIGHT):
        for x in range(GLYPH_WIDTH):
            edge = x in (0, GLYPH_WIDTH - 1) or y in (0, GLYPH_HEIGHT - 1)
            diagonal = x == y or x == GLYPH_WIDTH - 1 - y
            set_pixel(font, index, x, y, color if edge or diagonal else 0)


def brightest(first: int, second: int) -> int:
    """Combine adjacent samples; index zero is transparent, lower ink is brighter."""
    if not first:
        return second
    if not second:
        return first
    return min(first, second)


def make_pair(font: bytearray, target: int, left: int, right: int) -> None:
    """Horizontally condense two existing 18x18 glyphs into one cell."""
    source = bytes(font)
    for y in range(GLYPH_HEIGHT):
        for half, source_index in enumerate((left, right)):
            for x in range(GLYPH_WIDTH // 2):
                color = brightest(
                    get_pixel(source, source_index, x * 2, y),
                    get_pixel(source, source_index, x * 2 + 1, y),
                )
                set_pixel(font, target, half * (GLYPH_WIDTH // 2) + x, y, color)


def embolden_pair(font: bytearray, target: int) -> None:
    """Grow condensed strokes one pixel without crossing the half-cell boundary."""
    source = bytes(font)
    half_width = GLYPH_WIDTH // 2
    for half in range(2):
        start = half * half_width
        end = start + half_width
        for y in range(GLYPH_HEIGHT):
            for x in range(start, end):
                samples = [get_pixel(source, target, x, y)]
                if x > start:
                    samples.append(get_pixel(source, target, x - 1, y))
                if x + 1 < end:
                    samples.append(get_pixel(source, target, x + 1, y))
                if y:
                    samples.append(get_pixel(source, target, x, y - 1))
                if y + 1 < GLYPH_HEIGHT:
                    samples.append(get_pixel(source, target, x, y + 1))
                color = 0
                for sample in samples:
                    color = brightest(color, sample)
                set_pixel(font, target, x, y, color)


def copy_glyph(font: bytearray, target: int, source_index: int) -> None:
    """Copy one complete 18x18 glyph cell to another slot."""
    source = bytes(font)
    for y in range(GLYPH_HEIGHT):
        for x in range(GLYPH_WIDTH):
            set_pixel(font, target, x, y, get_pixel(source, source_index, x, y))


def clear_glyph(font: bytearray, target: int) -> None:
    """Make a glyph cell fully transparent."""
    for y in range(GLYPH_HEIGHT):
        for x in range(GLYPH_WIDTH):
            set_pixel(font, target, x, y, 0)


def latin_index(char: str) -> int:
    if "0" <= char <= "9":
        return direct_sjis_index(0x824F + ord(char) - ord("0"))
    if "A" <= char <= "Z":
        return direct_sjis_index(0x8260 + ord(char) - ord("A"))
    if "a" <= char <= "z":
        return direct_sjis_index(0x8281 + ord(char) - ord("a"))
    if char == " ":
        return direct_sjis_index(0x8140)
    if char == "'":
        return direct_sjis_index(0x8166)
    if char == '"':
        return direct_sjis_index(0x8168)
    if 0x21 <= ord(char) <= 0x7E:
        raw = chr(ord(char) + 0xFEE0).encode("cp932")
        if len(raw) == 2:
            return direct_sjis_index(int.from_bytes(raw, "big"))
    raise ValueError(f"DTE source {char!r} has no direct fullwidth glyph")


def ttf_half_glyph(char: str, path: Path, size: int, variation: str,
                   monochrome: bool = False) -> list[list[int]]:
    """Rasterize one character into a native 9x18 antialiased ink mask.

    Pillow's grayscale coverage is quantized into the retail font's seven ink
    levels.  Deliberately do not draw a separate stroke/halo: partially covered
    edge pixels provide antialiasing without making adjacent letters glow.
    """
    from PIL import Image, ImageDraw, ImageFont

    width = GLYPH_WIDTH // 2
    fill = Image.new("L", (width, GLYPH_HEIGHT), 0)
    font = ImageFont.truetype(str(path), size)
    if variation:
        font.set_variation_by_name(variation.encode("ascii"))
    if char != " ":
        # Baseline 15 leaves room for descenders while matching the retail cell.
        ImageDraw.Draw(fill).text((width // 2, 15), char, font=font, fill=255, anchor="ms")
    result = [[0] * width for _ in range(GLYPH_HEIGHT)]
    for y in range(GLYPH_HEIGHT):
        for x in range(width):
            inside = fill.getpixel((x, y))
            if inside:
                # In monochrome mode, use one hard coverage threshold and the
                # brightest ink index: no outline and no antialias shades.
                if not monochrome or inside >= 128:
                    result[y][x] = 1 if monochrome else 1 + (255 - inside) * 6 // 255
    return result


def make_pair_ttf(font: bytearray, target: int, pair: str, path: Path, size: int,
                  variation: str, monochrome: bool = False) -> None:
    for half, char in enumerate(pair):
        pixels = ttf_half_glyph(char, path, size, variation, monochrome)
        for y, row in enumerate(pixels):
            for x, color in enumerate(row):
                set_pixel(font, target, half * (GLYPH_WIDTH // 2) + x, y, color)


def apply_dte_table(font: bytearray, path: Path, ttf: Path | None = None,
                    ttf_size: int = 16, ttf_variation: str = "Condensed Bold",
                    ttf_monochrome: bool = False) -> int:
    count = 0
    with path.open(encoding="utf-8", newline="") as source:
        lines = (line for line in source if not line.startswith("#"))
        for row in csv.DictReader(lines, dialect="excel-tab"):
            pair, code = row["pair"], row["sjis"].strip()
            if not pair or not code:
                continue
            if len(pair) != 2:
                raise ValueError(f"DTE pair must be two characters: {pair!r}")
            target = direct_sjis_index(int(code, 16))
            if ttf:
                make_pair_ttf(font, target, pair, ttf, ttf_size, ttf_variation,
                              ttf_monochrome)
            else:
                make_pair(font, target, latin_index(pair[0]), latin_index(pair[1]))
                embolden_pair(font, target)
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("font", type=Path)
    parser.add_argument("output", type=Path)
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--index", type=lambda value: int(value, 0))
    target.add_argument("--sjis", type=lambda value: int(value, 16))
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--mark", action="store_true")
    operation.add_argument(
        "--pair-sjis",
        nargs=2,
        metavar=("LEFT", "RIGHT"),
        type=lambda value: int(value, 16),
    )
    operation.add_argument("--copy-sjis", type=lambda value: int(value, 16))
    operation.add_argument("--blank", action="store_true")
    operation.add_argument("--dte-table", type=Path)
    parser.add_argument("--color", type=lambda value: int(value, 0), default=1)
    parser.add_argument("--ttf", type=Path, help="Rasterize DTE pairs from this TTF/variable TTF")
    parser.add_argument("--ttf-size", type=int, default=16)
    parser.add_argument("--ttf-variation", default="Condensed Bold")
    parser.add_argument(
        "--ttf-monochrome",
        action="store_true",
        help="Use hard-edged solid TTF pixels with no outline or antialiasing",
    )
    args = parser.parse_args()

    if not 0 <= args.color <= 15:
        parser.error("--color must be from 0 through 15")
    if not args.dte_table and args.index is None and args.sjis is None:
        parser.error("--index or --sjis is required for --mark and --pair-sjis")
    index = None
    if not args.dte_table:
        index = args.index if args.index is not None else direct_sjis_index(args.sjis)
    font = bytearray(args.font.read_bytes())
    if len(font) != 806_400:
        parser.error(f"expected an 806400-byte FTALL.P04, got {len(font)} bytes")
    if index is not None and not 0 <= index < GLYPH_COLUMNS * 280:
        parser.error("glyph index is outside the 4480-slot atlas")

    if args.mark:
        mark_glyph(font, index, args.color)
        operation_name = "marked"
    elif args.pair_sjis:
        left, right = (direct_sjis_index(code) for code in args.pair_sjis)
        make_pair(font, index, left, right)
        operation_name = f"combined glyphs {left} and {right} into"
    elif args.copy_sjis is not None:
        source_index = direct_sjis_index(args.copy_sjis)
        copy_glyph(font, index, source_index)
        operation_name = f"copied glyph {source_index} into"
    elif args.blank:
        clear_glyph(font, index)
        operation_name = "cleared"
    else:
        count = apply_dte_table(font, args.dte_table, args.ttf, args.ttf_size,
                                args.ttf_variation, args.ttf_monochrome)
        operation_name = f"installed {count} DTE pairs in"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(font)
    if index is None:
        print(f"{operation_name} {args.output}")
    else:
        print(f"{operation_name} glyph {index} (0x{index:X}) in {args.output}")


if __name__ == "__main__":
    main()
