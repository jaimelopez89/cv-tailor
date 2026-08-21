#!/usr/bin/env python3
"""Generate the CV Tailor app icon.

Kept as a script rather than a committed binary so the mark stays reproducible
and on-brand: burgundy on warm cream, per REVHUNT_BRAND_GUIDELINES.md.

Usage:  python scripts/make_icon.py
Writes: "CV Tailor.app/Contents/Resources/cvtailor.icns"
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BASE = Path(__file__).resolve().parent.parent
ICON_DEST = BASE / "CV Tailor.app" / "Contents" / "Resources" / "cvtailor.icns"

BURGUNDY = (123, 45, 66)
CREAM = (250, 248, 245)
SAGE = (143, 166, 128)

# macOS icons sit on a rounded square inset from the canvas edge.
RENDER = 1024
INSET = int(RENDER * 0.06)
RADIUS = int(RENDER * 0.22)


def _font(size: int):
    for path in (
        "/System/Library/Fonts/Supplemental/Futura.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
    ):
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def render() -> Image.Image:
    img = Image.new("RGBA", (RENDER, RENDER), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    box = (INSET, INSET, RENDER - INSET, RENDER - INSET)
    d.rounded_rectangle(box, radius=RADIUS, fill=BURGUNDY)

    # "CV" as the mark, with a sage rule beneath it standing in for the tailored
    # line of a CV.
    font = _font(int(RENDER * 0.40))
    text = "CV"
    l, t, r, b = d.textbbox((0, 0), text, font=font)
    d.text(
        ((RENDER - (r - l)) / 2 - l, (RENDER - (b - t)) / 2 - t - RENDER * 0.06),
        text, font=font, fill=CREAM,
    )

    rule_w, rule_h = int(RENDER * 0.34), int(RENDER * 0.035)
    rule_y = int(RENDER * 0.66)
    d.rounded_rectangle(
        ((RENDER - rule_w) // 2, rule_y, (RENDER + rule_w) // 2, rule_y + rule_h),
        radius=rule_h // 2, fill=SAGE,
    )
    short_w = int(rule_w * 0.55)
    short_y = rule_y + int(rule_h * 2.4)
    d.rounded_rectangle(
        ((RENDER - short_w) // 2, short_y, (RENDER + short_w) // 2, short_y + rule_h),
        radius=rule_h // 2, fill=(*CREAM, 150),
    )
    return img


def main() -> int:
    if not shutil.which("iconutil"):
        print("iconutil not found — this script needs macOS.", file=sys.stderr)
        return 1

    master = render()
    ICON_DEST.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "cvtailor.iconset"
        iconset.mkdir()
        for size in (16, 32, 128, 256, 512):
            master.resize((size, size), Image.LANCZOS).save(iconset / f"icon_{size}x{size}.png")
            master.resize((size * 2, size * 2), Image.LANCZOS).save(
                iconset / f"icon_{size}x{size}@2x.png")

        res = subprocess.run(
            ["iconutil", "-c", "icns", str(iconset), "-o", str(ICON_DEST)],
            capture_output=True, text=True)
        if res.returncode != 0:
            print(res.stderr, file=sys.stderr)
            return res.returncode

    print(f"Wrote {ICON_DEST} ({ICON_DEST.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
