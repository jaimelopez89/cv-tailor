"""Font download, caching, and registration for the Ember layout engine."""

import os
import requests
from reportlab.lib.fonts import addMapping
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fonts")

# GitHub raw URLs for font files (stable, no API key needed)
FONT_MANIFEST = {
    "DMSerifText-Regular": "https://github.com/google/fonts/raw/main/ofl/dmseriftext/DMSerifText-Regular.ttf",
    "Poppins-Light": "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Light.ttf",
    "Poppins-Regular": "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Regular.ttf",
    "Poppins-Medium": "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Medium.ttf",
    "Poppins-SemiBold": "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-SemiBold.ttf",
    "Poppins-Bold": "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Bold.ttf",
    "SourceCodePro-Regular": "https://github.com/adobe-fonts/source-code-pro/raw/release/TTF/SourceCodePro-Regular.ttf",
}


def ensure_fonts():
    """Download missing fonts and register all with ReportLab. Idempotent."""
    os.makedirs(FONT_DIR, exist_ok=True)

    for name, url in FONT_MANIFEST.items():
        path = os.path.join(FONT_DIR, f"{name}.ttf")
        if not os.path.exists(path):
            print(f"Downloading {name}...")
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            with open(path, "wb") as f:
                f.write(resp.content)

    register_fonts()


def register_fonts():
    """Register all TTF fonts and the Poppins font family with ReportLab."""
    for name in FONT_MANIFEST:
        path = os.path.join(FONT_DIR, f"{name}.ttf")
        if os.path.exists(path):
            pdfmetrics.registerFont(TTFont(name, path))

    # Register Poppins family for Paragraph style bold/italic resolution
    addMapping("Poppins", 0, 0, "Poppins-Regular")
    addMapping("Poppins", 1, 0, "Poppins-Bold")
    addMapping("Poppins", 0, 1, "Poppins-Regular")  # no italic available
    addMapping("Poppins", 1, 1, "Poppins-Bold")
