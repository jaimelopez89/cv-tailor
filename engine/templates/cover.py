"""Cover letter rendering.

One renderer, five palettes — each mirrors the CV template of the same name so
a letter and a CV read as one set. Letters are single-page A4 with a letterhead
built from the profile's `meta` block.
"""

import os

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas

from engine.templates.base import BaseTemplate

PAGE_W, PAGE_H = A4
ML, MR, MT, MB = 24 * mm, 22 * mm, 24 * mm, 20 * mm
CW = PAGE_W - ML - MR

SERIF_FONTS = "https://fonts.googleapis.com/css2?family=DM+Serif+Text&family=Poppins:wght@300;400;500;600;700&family=Source+Code+Pro&display=swap"
SANS_FONTS = "https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&family=Source+Code+Pro&display=swap"

# name -> (ink, accent, body, dim, rule, background, heading font, fonts url)
PALETTES = {
    "ember": {
        "ink": "#1C1C28", "accent": "#B8522A", "gold": "#C8872A", "body": "#3A3A50",
        "dim": "#7A7A8A", "rule": "#E0DDD5", "bg": "#FEFBF5",
        "heading_font": "DMSerifText-Regular", "heading_css": "'DM Serif Text', serif",
        "fonts_url": SERIF_FONTS, "header_dark": True,
    },
    "meridian": {
        "ink": "#1E293B", "accent": "#0891B2", "gold": "#0891B2", "body": "#475569",
        "dim": "#94A3B8", "rule": "#E2E8F0", "bg": "#FFFFFF",
        "heading_font": "Poppins-SemiBold", "heading_css": "'Poppins', sans-serif",
        "fonts_url": SANS_FONTS, "header_dark": False,
    },
    "slate": {
        "ink": "#111827", "accent": "#374151", "gold": "#6B7280", "body": "#4B5563",
        "dim": "#9CA3AF", "rule": "#E5E7EB", "bg": "#FFFFFF",
        "heading_font": "Poppins-SemiBold", "heading_css": "'Poppins', sans-serif",
        "fonts_url": SANS_FONTS, "header_dark": False,
    },
    "verdant": {
        "ink": "#1B4332", "accent": "#2D6A4F", "gold": "#D4A843", "body": "#3D3D3D",
        "dim": "#6B6B6B", "rule": "#CCCCCC", "bg": "#FFFFFF",
        "heading_font": "DMSerifText-Regular", "heading_css": "'DM Serif Text', serif",
        "fonts_url": SERIF_FONTS, "header_dark": True,
    },
    "folio": {
        "ink": "#1F1F1F", "accent": "#C04000", "gold": "#D4714A", "body": "#404040",
        "dim": "#6B6B6B", "rule": "#E8E6E2", "bg": "#FAFAF8",
        "heading_font": "Poppins-SemiBold", "heading_css": "'Poppins', sans-serif",
        "fonts_url": SANS_FONTS, "header_dark": False,
    },
}

DEFAULT = "ember"


def palette(name: str = None) -> dict:
    return PALETTES.get((name or DEFAULT).lower(), PALETTES[DEFAULT])


class CoverLetterTemplate(BaseTemplate):
    """Renders a cover letter in the palette of the matching CV template."""

    name = "cover"
    description = "Cover letter matched to a CV template"

    def __init__(self, template_name: str = DEFAULT):
        super().__init__()
        self.template_name = (template_name or DEFAULT).lower()
        self.p = palette(self.template_name)

    # ── PDF ──────────────────────────────────────────────────────────────

    def render_pdf(self, letter: dict, output_path: str) -> str:
        p = self.p
        ink, accent, body, dim, rule = (
            HexColor(p["ink"]), HexColor(p["accent"]), HexColor(p["body"]),
            HexColor(p["dim"]), HexColor(p["rule"]),
        )
        meta = letter.get("meta", {}) or {}
        target = letter.get("target", {}) or {}

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        c = Canvas(output_path, pagesize=A4)

        # Background wash for templates that use one.
        if p["bg"].upper() not in ("#FFFFFF", "#FFF"):
            c.setFillColor(HexColor(p["bg"]))
            c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)

        # Accent rule across the top.
        c.setFillColor(accent)
        c.rect(0, PAGE_H - 3 * mm, PAGE_W, 3 * mm, stroke=0, fill=1)

        y = PAGE_H - MT

        # ── Letterhead ──
        c.setFillColor(ink)
        c.setFont(p["heading_font"], 22)
        c.drawString(ML, y - 16, self.s(meta.get("name", "")))
        y -= 26

        if meta.get("tagline"):
            c.setFillColor(HexColor(p["gold"]))
            c.setFont("Poppins-Light", 10)
            c.drawString(ML, y - 6, self.s(meta["tagline"]))
            y -= 16

        contact = " · ".join(
            self.s(meta.get(k, "")) for k in ("location", "email", "phone", "web", "linkedin")
            if meta.get(k)
        )
        if contact:
            c.setFillColor(dim)
            c.setFont("SourceCodePro-Regular", 8)
            c.drawString(ML, y - 6, contact)
            y -= 14

        y -= 6
        c.setStrokeColor(rule)
        c.setLineWidth(0.6)
        c.line(ML, y, ML + CW, y)
        y -= 26

        # ── Subject line ──
        role, company = target.get("role", ""), target.get("company", "")
        if role or company:
            c.setFillColor(accent)
            c.setFont("Poppins-SemiBold", 10)
            subject = " — ".join(x for x in [self.s(role), self.s(company)] if x)
            c.drawString(ML, y, f"Re: {subject}")
            y -= 24

        # ── Salutation ──
        salutation_style = self.make_style("sal", "Poppins-Regular", 10.5, body, leading=17)
        y -= self.draw_wrapped(c, letter.get("salutation", ""), salutation_style, ML, y, CW)
        y -= 10

        # ── Body ──
        para_style = self.make_style("para", "Poppins-Regular", 10, body, leading=16.5)
        blocks = list(letter.get("paragraphs") or [])
        if letter.get("closing"):
            blocks.append(letter["closing"])

        for para in blocks:
            if not str(para).strip():
                continue
            height = self.measure_text(para, para_style, CW)
            if y - height < MB + 40 * mm:
                # Letters should stay on one page; if they don't, continue overleaf.
                c.showPage()
                if p["bg"].upper() not in ("#FFFFFF", "#FFF"):
                    c.setFillColor(HexColor(p["bg"]))
                    c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
                y = PAGE_H - MT
            y -= self.draw_wrapped(c, para, para_style, ML, y, CW)
            y -= 11

        # ── Sign-off ──
        y -= 10
        c.setFillColor(body)
        c.setFont("Poppins-Regular", 10)
        c.drawString(ML, y, self.s(letter.get("signoff", "Sincerely,")))
        y -= 26
        c.setFillColor(ink)
        c.setFont(p["heading_font"], 13)
        c.drawString(ML, y, self.s(meta.get("name", "")))

        c.save()
        return output_path

    # ── HTML ─────────────────────────────────────────────────────────────

    def render_html(self, letter: dict, output_path: str = None) -> str:
        p = self.p
        meta = letter.get("meta", {}) or {}
        target = letter.get("target", {}) or {}
        name = self.h(meta.get("name", ""))

        contact = " &middot; ".join(
            self.h(meta.get(k, "")) for k in ("location", "email", "phone", "web", "linkedin")
            if meta.get(k)
        )
        subject = " &mdash; ".join(
            x for x in [self.h(target.get("role", "")), self.h(target.get("company", ""))] if x
        )

        blocks = list(letter.get("paragraphs") or [])
        if letter.get("closing"):
            blocks.append(letter["closing"])
        body_html = "\n".join(f"<p>{self.h(b)}</p>" for b in blocks if str(b).strip())

        css = f"""
:root {{
  --ink: {p['ink']}; --accent: {p['accent']}; --gold: {p['gold']};
  --body: {p['body']}; --dim: {p['dim']}; --rule: {p['rule']}; --bg: {p['bg']};
}}
@page {{ size: A4; margin: 0; }}
body {{ background: #e8e5de; font-family: 'Poppins', sans-serif; color: var(--body); line-height: 1.6; }}
.page {{ background: var(--bg); max-width: 210mm; min-height: 297mm; margin: 0 auto; padding: 0 0 48px; position: relative; }}
.accent-bar {{ height: 3px; background: var(--accent); }}
.inner {{ padding: 40px 68px 0; }}
h1 {{ font-family: {p['heading_css']}; font-size: 30px; color: var(--ink); font-weight: 400; letter-spacing: -0.3px; }}
.tagline {{ font-weight: 300; font-size: 12px; color: var(--gold); margin-top: 3px; }}
.contact {{ font-family: 'Source Code Pro', monospace; font-size: 9px; color: var(--dim); margin-top: 6px; }}
hr {{ border: none; border-top: 1px solid var(--rule); margin: 22px 0 26px; }}
.subject {{ font-weight: 600; font-size: 11px; color: var(--accent); margin-bottom: 22px; }}
.salutation {{ font-size: 11.5px; color: var(--body); margin-bottom: 14px; }}
.letter-body p {{ font-size: 11px; line-height: 1.75; color: var(--body); margin-bottom: 14px; }}
.signoff {{ font-size: 11px; color: var(--body); margin-top: 26px; }}
.signature {{ font-family: {p['heading_css']}; font-size: 15px; color: var(--ink); margin-top: 20px; }}
"""

        html = self.html_head(f"{name} - Cover Letter", css, p["fonts_url"])
        html += f"""
<body>
<div class="page">
  <div class="accent-bar"></div>
  <div class="inner">
    <h1>{name}</h1>
    {f'<p class="tagline">{self.h(meta.get("tagline",""))}</p>' if meta.get("tagline") else ''}
    {f'<p class="contact">{contact}</p>' if contact else ''}
    <hr>
    {f'<p class="subject">Re: {subject}</p>' if subject else ''}
    <p class="salutation">{self.h(letter.get("salutation",""))}</p>
    <div class="letter-body">
{body_html}
    </div>
    <p class="signoff">{self.h(letter.get("signoff","Sincerely,"))}</p>
    <p class="signature">{name}</p>
  </div>
</div>
</body>
</html>"""

        if output_path:
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            with open(output_path, "w") as f:
                f.write(html)
        return html


def render_cover_pdf(letter: dict, output_path: str, template_name: str = DEFAULT) -> str:
    return CoverLetterTemplate(template_name).render_pdf(letter, output_path)


def render_cover_html(letter: dict, output_path: str = None, template_name: str = DEFAULT) -> str:
    return CoverLetterTemplate(template_name).render_html(letter, output_path)
