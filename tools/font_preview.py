#!/usr/bin/env python3
"""Render Dai-2 Alpha's FTALL.P04 packed 4-bpp font atlas.

The output is a binary PPM image so this analysis tool has no third-party
dependencies. FONTCOL.C16 is interpreted as PS2-style little-endian BGR555.
"""

from __future__ import annotations

import argparse
from pathlib import Path


GLYPH_WIDTH = 18
GLYPH_HEIGHT = 18
ATLAS_WIDTH = 320
ATLAS_COLUMNS = 16
BYTES_PER_GLYPH = GLYPH_WIDTH * GLYPH_HEIGHT // 2


def bgr555(value: int) -> tuple[int, int, int]:
    red = (value & 0x1F) * 255 // 31
    green = ((value >> 5) & 0x1F) * 255 // 31
    blue = ((value >> 10) & 0x1F) * 255 // 31
    return red, green, blue


def load_palette(path: Path, palette_number: int) -> list[tuple[int, int, int]]:
    data = path.read_bytes()
    start = palette_number * 16 * 2
    raw = data[start : start + 32]
    if len(raw) != 32:
        raise ValueError(f"palette {palette_number} is outside {path}")
    return [bgr555(int.from_bytes(raw[i : i + 2], "little")) for i in range(0, 32, 2)]


def unpack_low_nibble_first(data: bytes) -> list[int]:
    pixels: list[int] = []
    for value in data:
        pixels.extend((value & 0x0F, value >> 4))
    return pixels


def deinterlace_ps2_4bpp(pixels: list[int], width: int, height: int) -> list[int]:
    """Undo the common PS2 4-bpp interlace pattern within one image."""
    interlace = (0x00, 0x10, 0x02, 0x12, 0x11, 0x01, 0x13, 0x03)
    matrix = (0, 1, -1, 0)
    tile_matrix = (4, -4)
    output = [0] * (width * height)

    for y in range(height):
        for x in range(width):
            odd_row = y & 1
            num1 = (y // 4) & 1
            num2 = (x // 4) & 1
            num3 = y % 4
            num4 = (x // 4) % 4
            if odd_row:
                num4 += 4
            source = (
                interlace[num4]
                + ((x * 4) % 16)
                + ((x // 16) * 32)
                + ((y - 1) * width if odd_row else y * width)
            )
            target_x = x + num1 * tile_matrix[num2]
            target_y = y + matrix[num3]
            if 0 <= source < len(pixels) and 0 <= target_x < width and 0 <= target_y < height:
                output[target_y * width + target_x] = pixels[source]
    return output


def render(
    font: bytes,
    palette: list[tuple[int, int, int]],
    columns: int,
    deinterlace: bool = False,
) -> bytes:
    atlas_stride = ATLAS_WIDTH // 2
    if len(font) % atlas_stride:
        raise ValueError("font size is not an exact multiple of the 320-pixel atlas width")
    atlas_height = len(font) // atlas_stride
    if atlas_height % GLYPH_HEIGHT:
        raise ValueError("font atlas height is not an exact multiple of 18 pixels")

    glyph_rows = atlas_height // GLYPH_HEIGHT
    glyph_count = glyph_rows * ATLAS_COLUMNS
    rows = (glyph_count + columns - 1) // columns
    width = columns * GLYPH_WIDTH
    height = rows * GLYPH_HEIGHT
    image = bytearray(width * height * 3)

    for glyph_index in range(glyph_count):
        atlas_column = glyph_index % ATLAS_COLUMNS
        atlas_row = glyph_index // ATLAS_COLUMNS
        pixels = []
        for glyph_y in range(GLYPH_HEIGHT):
            start = (
                (atlas_row * GLYPH_HEIGHT + glyph_y) * atlas_stride
                + atlas_column * (GLYPH_WIDTH // 2)
            )
            pixels.extend(unpack_low_nibble_first(font[start : start + GLYPH_WIDTH // 2]))
        if deinterlace:
            pixels = deinterlace_ps2_4bpp(pixels, GLYPH_WIDTH, GLYPH_HEIGHT)
        origin_x = (glyph_index % columns) * GLYPH_WIDTH
        origin_y = (glyph_index // columns) * GLYPH_HEIGHT
        for y in range(GLYPH_HEIGHT):
            for x in range(GLYPH_WIDTH):
                color = palette[pixels[y * GLYPH_WIDTH + x]]
                target = ((origin_y + y) * width + origin_x + x) * 3
                image[target : target + 3] = bytes(color)

    return f"P6\n{width} {height}\n255\n".encode("ascii") + image


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("font", type=Path)
    parser.add_argument("palette", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--columns", type=int, default=50)
    parser.add_argument("--palette-number", type=int, default=0)
    parser.add_argument(
        "--deinterlace",
        action="store_true",
        help="undo the common PS2 4-bpp interlace pattern per glyph",
    )
    args = parser.parse_args()

    font = args.font.read_bytes()
    palette = load_palette(args.palette, args.palette_number)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(render(font, palette, args.columns, args.deinterlace))
    glyph_count = len(font) * 2 // (ATLAS_WIDTH * GLYPH_HEIGHT) * ATLAS_COLUMNS
    print(f"rendered {glyph_count} 18x18 glyphs to {args.output}")


if __name__ == "__main__":
    main()
