"""Build a multi-size Windows .ico from assets/quicklingo_icon.png."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
PNG_PATH = ROOT / "assets" / "quicklingo_icon.png"
UI_PNG_PATH = ROOT / "assets" / "quicklingo_icon_ui.png"
ICO_PATH = ROOT / "assets" / "quicklingo_icon.ico"

# Slightly inset the artwork so 16–32 px variants stay readable.
INSET_RATIO = 0.86
CORNER_RADIUS_RATIO = 0.18
ICO_SIZES = (256, 128, 64, 48, 32, 24, 16)


def _square_crop(image: Image.Image) -> Image.Image:
    side = min(image.size)
    x = (image.width - side) // 2
    y = (image.height - side) // 2
    return image.crop((x, y, x + side, y + side))


def _inset_square(image: Image.Image) -> Image.Image:
    side = image.width
    inner = max(1, int(side * INSET_RATIO))
    resized = image.resize((inner, inner), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    offset = (side - inner) // 2
    canvas.paste(resized, (offset, offset), resized if resized.mode == "RGBA" else None)
    return canvas


def _round_corners(image: Image.Image) -> Image.Image:
    size = image.width
    radius = max(1, int(size * CORNER_RADIUS_RATIO))
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    rounded = image.copy()
    rounded.putalpha(mask)
    return rounded


def make_icon() -> None:
    source = Image.open(PNG_PATH).convert("RGBA")
    square = _round_corners(_inset_square(_square_crop(source)))
    master = square.resize((256, 256), Image.Resampling.LANCZOS)
    master.save(UI_PNG_PATH, format="PNG")
    master.save(
        ICO_PATH,
        format="ICO",
        sizes=[(size, size) for size in ICO_SIZES],
    )


if __name__ == "__main__":
    make_icon()
    print(f"Wrote {UI_PNG_PATH}")
    print(f"Wrote {ICO_PATH} ({', '.join(f'{s}px' for s in ICO_SIZES)})")
