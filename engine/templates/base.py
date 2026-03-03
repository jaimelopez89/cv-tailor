"""Shared utilities for all CV templates.

Provides common PDF drawing helpers, HTML element generators, and the
text sanitizer integration that all templates inherit.
"""

import os
from xml.sax.saxutils import escape as xml_escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph

from engine.fonts import ensure_fonts
from engine.sanitize import sanitize, sanitize_content

PAGE_W, PAGE_H = A4
MARGIN_B = 16 * mm


class BaseTemplate:
    """Base class for all CV templates."""

    name = "base"
    description = "Base template"

    def __init__(self):
        ensure_fonts()

    def render_pdf(self, content: dict, output_path: str) -> str:
        raise NotImplementedError

    def render_html(self, content: dict, output_path: str) -> str:
        raise NotImplementedError

    # ── Text helpers ─────────────────────────────────────────────────────

    @staticmethod
    def s(text) -> str:
        """Sanitize text: strip LLM artifacts."""
        if text is None:
            return ""
        return sanitize(str(text))

    @staticmethod
    def esc(text) -> str:
        """Sanitize + XML-escape for ReportLab Paragraph."""
        return xml_escape(sanitize(str(text or "")))

    @staticmethod
    def h(text) -> str:
        """Sanitize + HTML-escape."""
        return xml_escape(sanitize(str(text or "")))

    @staticmethod
    def prep(content: dict) -> dict:
        """Sanitize entire content dict before rendering."""
        return sanitize_content(content)

    @staticmethod
    def year_range(roles: list) -> str:
        """Extract 'YYYY - YYYY' or 'YYYY - Present' from a list of roles.

        Takes the start year of the earliest role and end of the latest.
        """
        import re
        if not roles:
            return ""
        years_start = []
        years_end = []
        for r in roles:
            period = r.get("period", "")
            # Find all 4-digit years
            found = re.findall(r"\b((?:19|20)\d{2})\b", period)
            if found:
                years_start.append(int(found[0]))
            if "present" in period.lower() or "current" in period.lower() or "now" in period.lower():
                years_end.append(("Present", 9999))
            elif found and len(found) >= 2:
                years_end.append((found[-1], int(found[-1])))
            elif found:
                years_end.append((found[0], int(found[0])))
        if not years_start:
            return ""
        start = str(min(years_start))
        if years_end:
            end_label, end_val = max(years_end, key=lambda x: x[1])
            return f"{start} - {end_label}"
        return start

    # ── PDF drawing utilities ────────────────────────────────────────────

    @staticmethod
    def make_style(name, font_name, font_size, color, leading=None,
                   space_after=0, left_indent=0):
        return ParagraphStyle(
            name,
            fontName=font_name,
            fontSize=font_size,
            textColor=color,
            leading=leading or font_size * 1.4,
            spaceAfter=space_after,
            leftIndent=left_indent,
        )

    @staticmethod
    def draw_wrapped(canvas, text, style, x, y, width):
        """Draw wrapped paragraph, return height consumed."""
        p = Paragraph(xml_escape(sanitize(str(text))), style)
        _, h = p.wrap(width, 500)
        p.drawOn(canvas, x, y - h)
        return h

    @staticmethod
    def measure_text(text, style, width):
        """Measure height of wrapped paragraph without drawing."""
        p = Paragraph(xml_escape(sanitize(str(text))), style)
        _, h = p.wrap(width, 500)
        return h

    # ── HTML generators ──────────────────────────────────────────────────

    def html_head(self, title, css, fonts_url):
        """Generate HTML <head> with embedded CSS and Google Fonts."""
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{self.h(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{fonts_url}" rel="stylesheet">
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
{css}
</style>
</head>"""

    def html_metrics(self, metrics):
        """Generate metrics row HTML."""
        if not metrics:
            return ""
        items = ""
        for m in metrics[:4]:
            v = self.h(m.get("value", ""))
            l = self.h(m.get("label", ""))
            items += f'<div class="metric"><span class="metric-value">{v}</span><span class="metric-label">{l}</span></div>\n'
        return f'<div class="metrics-row">\n{items}</div>'

    def html_experience(self, experience):
        """Generate experience section HTML."""
        if not experience:
            return ""
        entries = ""
        for entry in experience:
            if entry.get("_hidden"):
                continue
            company = self.h(entry.get("company", ""))
            subtitle = self.h(entry.get("subtitle", ""))
            location = self.h(entry.get("location", ""))
            roles = entry.get("roles", [])
            bullets = entry.get("bullets", [])

            roles_html = ""
            for role in roles:
                t = self.h(role.get("title", ""))
                p = self.h(role.get("period", ""))
                roles_html += f'<div class="role"><span class="role-title">{t}</span><span class="role-period">{p}</span></div>\n'

            bullets_html = ""
            for b in bullets:
                text = self.h(b.get("text", "") if isinstance(b, dict) else str(b))
                if text:
                    bullets_html += f"<li>{text}</li>\n"

            yr = self.h(self.year_range(roles))
            loc_str = f' <span class="company-location">{location}</span>' if location else ""

            entries += f"""<article class="exp-entry">
<div class="exp-header"><h3 class="company">{company}{loc_str}</h3><span class="company-years">{yr}</span></div>
{"<p class='subtitle'>" + subtitle + "</p>" if subtitle else ""}
{roles_html}
<ul class="bullets">{bullets_html}</ul>
</article>
"""
        return entries

    def html_ventures(self, ventures):
        if not ventures:
            return ""
        items = ""
        for v in ventures:
            if v.get("_hidden"):
                continue
            name = self.h(v.get("name", ""))
            period = self.h(v.get("period", ""))
            desc = self.h(v.get("description", ""))
            items += f'<div class="venture"><div class="venture-header"><strong>{name}</strong><span class="period">{period}</span></div><p>{desc}</p></div>\n'
        return items

    def html_education(self, education):
        if not education:
            return ""
        items = ""
        for e in education:
            school = self.h(e.get("school", ""))
            degree = self.h(e.get("degree", ""))
            period = self.h(e.get("period", ""))
            details = e.get("details", [])
            if isinstance(details, str):
                details = [d.strip() for d in details.split(";") if d.strip()]
            det_html = "".join(f"<p class='edu-detail'>{self.h(d)}</p>" for d in details)
            period_html = f'<span class="edu-period">{period}</span>' if period else ""
            items += f'<div class="edu-entry"><strong class="edu-school">{school}</strong>{period_html}<p class="degree">{degree}</p>{det_html}</div>\n'
        return items

    def html_skills(self, skills):
        if not skills:
            return ""
        groups = skills.get("groups", []) if isinstance(skills, dict) else []
        items = ""
        for g in groups:
            if g.get("_hidden"):
                continue
            name = self.h(g.get("name", ""))
            skill_items = [self.h(i) for i in g.get("items", [])]
            items += f'<div class="skill-group"><h4>{name}</h4><p>{" &middot; ".join(skill_items)}</p></div>\n'
        return items

    def html_speaking(self, speaking):
        if not speaking:
            return ""
        items = ""
        for s in speaking:
            if isinstance(s, dict):
                title = self.h(s.get("title", ""))
                year = self.h(str(s.get("year", "")))
            else:
                title = self.h(str(s))
                year = ""
            items += f'<div class="speak-entry"><span class="speak-title">{title}</span><span class="speak-year">{year}</span></div>\n'
        return items

    def html_projects(self, projects):
        if not projects:
            return ""
        items = ""
        for p in projects:
            name = self.h(p.get("name", ""))
            url = p.get("url", "")
            desc = self.h(p.get("description", ""))
            if url:
                name_html = f'<a href="https://{self.h(url)}" class="project-link">{name}</a>'
            else:
                name_html = f'<strong>{name}</strong>'
            items += f'<div class="project">{name_html}<p>{desc}</p></div>\n'
        return items

    def html_notable(self, notable):
        if not notable:
            return ""
        return "\n".join(f'<p class="notable-item">{self.h(n)}</p>' for n in notable)

    def _write_html(self, html: str, output_path: str) -> str:
        """Write HTML string to file."""
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        return output_path
