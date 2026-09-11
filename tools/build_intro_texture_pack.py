#!/usr/bin/env python3
"""Build deterministic English PCSX2 replacements for the prologue cards."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent.parent
DUMPS = ROOT / "work/pcsx2/windows/app/textures/SLPS-25228/dumps"
ASSETS = ROOT / "assets/pcsx2-textures/SLPS-25228/replacements"
LIVE = ROOT / "work/pcsx2/windows/app/textures/SLPS-25228/replacements"
FONT = ROOT / "assets/UbuntuSansMono.ttf"

CARDS = {
    "dd8802deede167bf-2fb4332b5de32995-00002293.png": (
        "New A.D. 188.\n"
        "The Earth Sphere was rebuilding\n"
        "after the last war.\n"
        "With the Titans destroyed,\n"
        "the Federation reorganized\n"
        "and strengthened its forces\n"
        "against alien invaders and\n"
        "threats from underground."
    ),
    "29093e83d46aaf45-2fb4332b5de32995-00002293.png": (
        "On Earth, the Daiku Maryu Corps\n"
        "was formed, bringing many\n"
        "Super Robots under its command.\n"
        "Separately, the secret defense\n"
        "organization GGG prepared for\n"
        "emergencies and full-scale\n"
        "operations."
    ),
    "61ba6300daecc716-2fb4332b5de32995-00002293.png": (
        "Meanwhile, in space, Londo Bell,\n"
        "based at the Londinium colony,\n"
        "investigated Neo Zeon remnants\n"
        "and anti-Federation forces,\n"
        "including the Crossbone Vanguard."
    ),
    "636fb62f4bdecc39-2fb4332b5de32995-00002293.png": (
        "Meanwhile, on Mars, alongside\n"
        "the terraforming project,\n"
        "Preventer led construction of\n"
        "a military base serving as a\n"
        "bridgehead against alien invasion."
    ),
    "8a1ae3db282bffd3-2fb4332b5de32995-00002293.png": (
        "Thus, the people of Earth left\n"
        "their fleeting peace behind and\n"
        "steadily prepared to resist\n"
        "invaders from above and below.\n"
        "All sensed that the next war\n"
        "would soon begin..."
    ),
}


def render(source: Path, output: Path, text: str) -> None:
    image = Image.open(source).convert("RGBA")
    if image.size != (1024, 256):
        raise ValueError(f"unexpected texture size for {source}: {image.size}")

    # Only the prologue-copy rectangle is replaced. The shared character art,
    # lower-left artwork, palette values and every other pixel remain intact.
    image.paste((0, 0, 0, 0), (32, 25, 610, 215))
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(FONT), 19)
    draw.multiline_text(
        (43, 34), text, font=font, fill=(248, 248, 248, 128),
        spacing=1, stroke_width=1, stroke_fill=(16, 16, 16, 128),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dumps", type=Path, default=DUMPS)
    parser.add_argument("--output", type=Path, default=ASSETS)
    parser.add_argument("--install", type=Path, default=LIVE)
    args = parser.parse_args()

    for filename, text in CARDS.items():
        source = args.dumps / filename
        if not source.is_file():
            parser.error(f"missing dumped texture: {source}")
        destination = args.output / filename
        render(source, destination, text)
        if args.install:
            args.install.mkdir(parents=True, exist_ok=True)
            shutil.copy2(destination, args.install / filename)
        print(destination)


if __name__ == "__main__":
    main()
