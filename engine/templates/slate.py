"""Slate — Ultra-minimal, Apple-inspired CV template.

Personality: Clean, confident restraint. White background, near-black text,
subtle grey accents. Lots of whitespace. The design disappears so the
content speaks.
"""

import os
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas

from engine.metrics import renderable_metrics
from engine.templates.base import BaseTemplate

PAGE_W, PAGE_H = A4
ML, MR, MB = 28 * mm, 24 * mm, 18 * mm
CW = PAGE_W - ML - MR
RE = ML + CW

NEAR_BLK = HexColor("#111827")
DARK     = HexColor("#1F2937")
MID      = HexColor("#374151")
BODY     = HexColor("#4B5563")
GREY     = HexColor("#6B7280")
SOFT     = HexColor("#9CA3AF")
LIGHT    = HexColor("#D1D5DB")
FAINT    = HexColor("#E5E7EB")
WHITE    = HexColor("#FFFFFF")


class SlateTemplate(BaseTemplate):
    name = "slate"
    description = "Ultra-minimal - clean whitespace, Apple-inspired restraint"

    def render_pdf(self, content: dict, output_path: str) -> str:
        ct = self.prep(content)
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        c = Canvas(output_path, pagesize=A4)
        self._pg = 1
        self._page1(c, ct)
        self._page2(c, ct)
        c.save()
        return output_path

    def _footer(self, c, ct, pg):
        m = ct.get("meta", {})
        c.setFont("Poppins-Regular", 6); c.setFillColor(SOFT)
        c.drawCentredString(PAGE_W / 2, MB - 10, f"Page {pg}")

    def _section(self, c, y, title):
        y -= 18
        c.setFont("Poppins-Medium", 7); c.setFillColor(GREY)
        c.drawString(ML, y, self.s(title).upper())
        y -= 5
        c.setStrokeColor(FAINT); c.setLineWidth(0.4)
        c.line(ML, y, RE, y)
        return y - 10

    # ── PAGE 1 ───────────────────────────────────────────────────────

    def _page1(self, c, ct):
        meta = ct.get("meta", {})

        # Name - large, left-aligned, lots of space above
        y = PAGE_H - 40 * mm
        c.setFont("Poppins-Bold", 28); c.setFillColor(NEAR_BLK)
        c.drawString(ML, y, self.s(meta.get("name", "")))
        y -= 16

        # Tagline
        tagline = self.s(meta.get("tagline", ""))
        if tagline:
            c.setFont("Poppins-Light", 10); c.setFillColor(GREY)
            c.drawString(ML, y, tagline)
            y -= 14

        # Contact line - minimal separator
        parts = [meta.get(k, "") for k in ("location", "email", "web", "linkedin")]
        parts = [self.s(p) for p in parts if p]
        if parts:
            c.setFont("Poppins-Regular", 7); c.setFillColor(SOFT)
            c.drawString(ML, y, "  /  ".join(parts))
            y -= 8

        # Thin rule under header
        y -= 6
        c.setStrokeColor(FAINT); c.setLineWidth(0.5)
        c.line(ML, y, RE, y)
        y -= 4

        # Summary
        summary = ct.get("summary", "")
        if isinstance(summary, dict):
            summary = summary.get("default", "")
        if summary:
            y = self._section(c, y, "Summary")
            st = self.make_style("s", "Poppins-Regular", 8, BODY, leading=13)
            h = self.draw_wrapped(c, summary, st, ML, y, CW)
            y -= h + 4

        # Metrics - horizontal, minimal
        metrics = renderable_metrics(ct.get("metrics"))
        if metrics:
            y -= 8
            n = len(metrics)
            cw = CW / n
            for i, m in enumerate(metrics):
                mx = ML + cw * i
                c.setFont("Poppins-SemiBold", 16); c.setFillColor(NEAR_BLK)
                c.drawString(mx, y, self.s(m.get("value", "")))
                c.setFont("Poppins-Regular", 6); c.setFillColor(SOFT)
                c.drawString(mx, y - 13, self.s(m.get("label", "")).upper())
            y -= 32

        # Experience
        exp = [e for e in ct.get("experience", []) if not e.get("_hidden")]
        if exp:
            y = self._section(c, y, "Experience")
            for i, entry in enumerate(exp):
                eh = self._measure_exp(entry)
                if y - eh < MB + 20:
                    self._footer(c, ct, self._pg)
                    c.showPage(); self._pg += 1
                    y = PAGE_H - 22 * mm
                    y = self._section(c, y, "Experience (continued)")
                y = self._draw_exp(c, y, entry)
                if i < len(exp) - 1:
                    y -= 4
                    c.setStrokeColor(FAINT); c.setLineWidth(0.3)
                    c.line(ML, y, ML + 40, y)
                    y -= 12

        self._footer(c, ct, self._pg)

    def _draw_exp(self, c, y, entry):
        company = self.s(entry.get("company", ""))
        subtitle = self.s(entry.get("subtitle", ""))
        location = self.s(entry.get("location", ""))
        roles = entry.get("roles", [])
        bullets = entry.get("bullets", [])

        # Company + location + year range on same line
        c.setFont("Poppins-SemiBold", 9.5); c.setFillColor(NEAR_BLK)
        company_str = company
        if location:
            company_str += f"  /  {location}"
        c.drawString(ML, y, company_str)
        yr = self.year_range(roles)
        if yr:
            c.setFont("Poppins-Medium", 9); c.setFillColor(DARK)
            c.drawRightString(RE, y + 1, yr)
        y -= 12

        if subtitle:
            c.setFont("Poppins-Regular", 7); c.setFillColor(GREY)
            c.drawString(ML, y, subtitle)
            y -= 11

        for role in roles:
            rt = self.s(role.get("title", ""))
            c.setFont("Poppins-Medium", 8); c.setFillColor(DARK)
            c.drawString(ML, y, rt)
            c.setFont("Poppins-Regular", 6.5); c.setFillColor(SOFT)
            c.drawRightString(RE, y + 1, self.s(role.get("period", "")))
            y -= 12

        y -= 0
        bst = self.make_style("b", "Poppins-Regular", 7.5, BODY, leading=11)
        for b in bullets:
            txt = self.s(b.get("text", "") if isinstance(b, dict) else str(b))
            if not txt:
                continue
            # Grey dash bullet in margin, text aligned with company/roles
            c.setFont("Poppins-Regular", 7.5); c.setFillColor(LIGHT)
            c.drawString(ML - 10, y - 7, "\u2013")
            h = self.draw_wrapped(c, txt, bst, ML, y, CW)
            y -= h + 2.5
        return y

    def _measure_exp(self, entry):
        h = 12 + (11 if entry.get("subtitle") else 0)
        h += len(entry.get("roles", [])) * 12 + 0
        bst = self.make_style("m", "Poppins-Regular", 7.5, BODY, leading=11)
        for b in entry.get("bullets", []):
            txt = b.get("text", "") if isinstance(b, dict) else str(b)
            if txt:
                h += self.measure_text(txt, bst, CW) + 2.5
        return h

    # ── PAGE 2 ───────────────────────────────────────────────────────

    def _page2(self, c, ct):
        has_p2 = (ct.get("ventures") or ct.get("education") or ct.get("notable")
                  or ct.get("speaking") or ct.get("projects")
                  or (ct.get("skills",{}).get("groups") if isinstance(ct.get("skills",{}), dict) else False))
        if not has_p2:
            return
        c.showPage(); self._pg += 1
        y = PAGE_H - 22 * mm

        # Two columns - balanced
        gap = 32
        lw = (CW - gap) * 0.52
        rw = CW - lw - gap
        rx = ML + lw + gap

        # Left: ventures + education
        ly = y
        ventures = [v for v in ct.get("ventures", []) if not v.get("_hidden")]
        if ventures:
            ly = self._section(c, ly, "Ventures & Advisory")
            for v in ventures:
                vname = self.s(v.get("name", ""))
                c.setFont("Poppins-SemiBold", 9); c.setFillColor(NEAR_BLK)
                c.drawString(ML, ly, vname)
                vurl = self.s(v.get("url", ""))
                if vurl:
                    x_url = ML + c.stringWidth(vname, "Poppins-SemiBold", 9) + 6
                    c.setFont("SourceCodePro-Regular", 6.5); c.setFillColor(SOFT)
                    c.drawString(x_url, ly + 0.5, vurl)
                per = self.s(v.get("period", ""))
                if per:
                    c.setFont("Poppins-Regular", 7); c.setFillColor(SOFT)
                    c.drawRightString(ML + lw, ly + 1, per)
                ly -= 12
                desc = self.s(v.get("description", ""))
                if desc:
                    st = self.make_style("vd", "Poppins-Regular", 7, BODY, leading=10)
                    h = self.draw_wrapped(c, desc, st, ML, ly, lw)
                    ly -= h
                ly -= 14

        edu = ct.get("education", [])
        if edu:
            ly -= 4
            ly = self._section(c, ly, "Education")
            for e in edu:
                c.setFont("Poppins-SemiBold", 9); c.setFillColor(NEAR_BLK)
                c.drawString(ML, ly, self.s(e.get("school", "")))
                ly -= 11
                per = self.s(e.get("period", ""))
                if per:
                    c.setFont("Poppins-Regular", 7); c.setFillColor(SOFT)
                    c.drawString(ML, ly, per)
                    ly -= 9
                deg = self.s(e.get("degree", ""))
                if deg:
                    c.setFont("Poppins-Regular", 7.5); c.setFillColor(BODY)
                    c.drawString(ML, ly, deg)
                    ly -= 11
                details = e.get("details", [])
                if isinstance(details, str):
                    details = [x.strip() for x in details.split(";") if x.strip()]
                for d in details:
                    st = self.make_style("ed", "Poppins-Regular", 6.5, GREY, leading=9)
                    h = self.draw_wrapped(c, d, st, ML + 4, ly, lw - 4)
                    ly -= h + 2
                ly -= 8

        projects = ct.get("projects", [])
        if projects:
            ly -= 4
            ly = self._section(c, ly, "Other Projects")
            for proj in projects:
                name = self.s(proj.get("name", ""))
                url = proj.get("url", "")
                c.setFont("Poppins-SemiBold", 8); c.setFillColor(NEAR_BLK)
                c.drawString(ML, ly, name)
                if url:
                    c.setFont("Poppins-Regular", 6); c.setFillColor(SOFT)
                    c.drawString(ML + c.stringWidth(name, "Poppins-SemiBold", 8) + 6, ly + 0.5, url)
                ly -= 10
                desc = self.s(proj.get("description", ""))
                if desc:
                    st = self.make_style("pd", "Poppins-Regular", 6.5, GREY, leading=9)
                    h = self.draw_wrapped(c, desc, st, ML, ly, lw)
                    ly -= h + 12
                else:
                    ly -= 10

        notable = ct.get("notable", [])
        if notable:
            ly -= 4
            ly = self._section(c, ly, "Beyond Work")
            for item in notable:
                st = self.make_style("nt", "Poppins-Regular", 7, BODY, leading=10)
                h = self.draw_wrapped(c, item, st, ML, ly, lw)
                ly -= h + 5

        # Right: skills + speaking
        ry = y
        skills = ct.get("skills", {})
        groups = [g for g in (skills.get("groups", []) if isinstance(skills, dict) else []) if not g.get("_hidden")]
        if groups:
            ry = self._col_section(c, rx, ry, rw, "Expertise")
            for g in groups:
                c.setFont("Poppins-Medium", 7.5); c.setFillColor(DARK)
                c.drawString(rx, ry, self.s(g.get("name", "")))
                ry -= 11
                items = " \u00b7 ".join(self.s(i) for i in g.get("items", []))
                st = self.make_style("sk", "Poppins-Regular", 6.5, GREY, leading=9.5)
                h = self.draw_wrapped(c, items, st, rx, ry, rw)
                ry -= h + 10

        speaking = ct.get("speaking", [])
        if speaking:
            ry -= 4
            ry = self._col_section(c, rx, ry, rw, "Speaking")
            for s in speaking:
                title = self.s(s.get("title", "") if isinstance(s, dict) else str(s))
                yr = str(s.get("year", "")) if isinstance(s, dict) else ""
                st = self.make_style("sp", "Poppins-Regular", 7, BODY, leading=9.5)
                h = self.draw_wrapped(c, title, st, rx, ry, rw - 30)
                if yr:
                    c.setFont("Poppins-Regular", 7); c.setFillColor(SOFT)
                    c.drawRightString(rx + rw, ry, yr)
                ry -= h + 6

        self._footer(c, ct, self._pg)

    def _col_section(self, c, x, y, w, title):
        y -= 18
        c.setFont("Poppins-Medium", 7); c.setFillColor(GREY)
        c.drawString(x, y, self.s(title).upper())
        y -= 5
        c.setStrokeColor(FAINT); c.setLineWidth(0.4)
        c.line(x, y, x + w, y)
        return y - 10

    # ── HTML ─────────────────────────────────────────────────────────

    def render_html(self, content: dict, output_path: str) -> str:
        ct = self.prep(content)
        meta = ct.get("meta", {})
        name = self.h(meta.get("name", ""))
        tagline = self.h(meta.get("tagline", ""))
        contact = "  /  ".join(self.h(meta.get(k, "")) for k in ("location", "email", "web", "linkedin") if meta.get(k))
        summary = ct.get("summary", "")
        if isinstance(summary, dict):
            summary = summary.get("default", "")

        metrics_html = ""
        for m in renderable_metrics(ct.get("metrics")):
            metrics_html += f'<div class="metric"><span class="metric-value">{self.h(m.get("value", ""))}</span><span class="metric-label">{self.h(m.get("label", ""))}</span></div>\n'
        metrics_section = (
            f'<section class="metrics"><div class="metrics-row">{metrics_html}</div></section>'
            if metrics_html else ""
        )

        html = self.html_head(
            f"{name} - CV",
            SLATE_CSS,
            "https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&family=Source+Code+Pro&display=swap"
        )
        html += f"""
<body>
<div class="page page-1">
  <header>
    <h1>{name}</h1>
    <p class="tagline">{tagline}</p>
    <p class="contact">{contact}</p>
  </header>
  <hr class="header-rule">
  <section class="summary"><h2>Summary</h2><p>{self.h(summary)}</p></section>
  {metrics_section}
  {self.section("experience", "Experience", self.html_experience(ct.get("experience", [])))}
</div>
<div class="page page-2">
  <div class="two-col">
    <div class="col-left">
      {self.section("ventures", "Ventures &amp; Advisory", self.html_ventures(ct.get("ventures", [])))}
      {self.section("education", "Education", self.html_education(ct.get("education", [])))}
      {self.section("projects", "Other Projects", self.html_projects(ct.get("projects", [])))}
      {self.section("notable", "Beyond Work", self.html_notable(ct.get("notable", [])))}
    </div>
    <div class="col-right">
      <section class="skills"><h2>Expertise</h2>{self.html_skills(ct.get("skills", {}))}</section>
      {self.section("speaking", "Speaking", self.html_speaking(ct.get("speaking", [])))}
    </div>
  </div>
  <footer><p>Page 2</p></footer>
</div>
</body></html>"""
        return self._write_html(html, output_path)


SLATE_CSS = """
:root {
  --near-blk: #111827; --dark: #1F2937; --mid: #374151;
  --body: #4B5563; --grey: #6B7280; --soft: #9CA3AF;
  --light: #D1D5DB; --faint: #E5E7EB;
}
@page { size: A4; margin: 0; }
body { background: #F3F4F6; font-family: 'Poppins', sans-serif; color: var(--body); line-height: 1.5; }
.page { background: #fff; max-width: 210mm; margin: 0 auto; padding: 0; position: relative; }
.page-1 { min-height: 297mm; padding-top: 64px; }
.page-2 { min-height: 297mm; padding-top: 32px; }
header { padding: 0 80px; }
header h1 { font-size: 32px; font-weight: 700; color: var(--near-blk); letter-spacing: -0.5px; margin-bottom: 6px; }
header .tagline { font-weight: 300; font-size: 13px; color: var(--grey); margin-bottom: 6px; }
header .contact { font-size: 10px; color: var(--soft); letter-spacing: 0.2px; }
hr.header-rule { border: none; border-top: 1px solid var(--faint); margin: 20px 80px 0; }
h2 { font-size: 8px; font-weight: 500; color: var(--grey); text-transform: uppercase;
     letter-spacing: 2px; border-bottom: 1px solid var(--faint); padding-bottom: 6px; margin-bottom: 14px; }
section { padding: 18px 80px 0; }
.summary p { font-size: 11px; line-height: 1.7; color: var(--body); }
.metrics-row { display: flex; gap: 0; }
.metric { flex: 1; }
.metric-value { display: block; font-weight: 600; font-size: 20px; color: var(--near-blk); }
.metric-label { display: block; font-size: 8px; color: var(--soft); text-transform: uppercase; letter-spacing: 0.5px; margin-top: 2px; }
.exp-entry { margin-bottom: 14px; padding-bottom: 14px; border-bottom: 1px solid var(--faint); }
.exp-entry:last-child { border-bottom: none; }
.exp-header { display: flex; justify-content: space-between; align-items: baseline; }
.company { font-weight: 600; font-size: 12px; color: var(--near-blk); }
.company-years { font-weight: 500; font-size: 11px; color: var(--dark); }
.period { font-size: 9px; color: var(--soft); font-weight: 400; }
.subtitle { font-size: 9.5px; color: var(--grey); margin: 1px 0 3px; }
.role { display: flex; justify-content: space-between; margin-bottom: 2px; }
.role-title { font-weight: 500; font-size: 10.5px; color: var(--dark); }
.role-period { font-size: 9px; color: var(--soft); }
ul.bullets { list-style: none; padding: 4px 0 0; }
ul.bullets li { font-size: 10px; line-height: 1.55; color: var(--body); padding: 2px 0 2px 16px; position: relative; }
ul.bullets li::before { content: '\\2013'; color: var(--light); position: absolute; left: 0; }
.two-col { display: grid; grid-template-columns: 52% 1fr; gap: 40px; padding: 0 80px; }
.col-left section, .col-right section { padding: 0; margin-bottom: 24px; }
.venture, .edu-entry { margin-bottom: 16px; }
.venture-header { display: flex; justify-content: space-between; align-items: baseline; }
.venture-name { display: flex; align-items: baseline; gap: 6px; }
.venture-link { font-family: 'Source Code Pro', monospace; font-size: 9px; color: var(--soft); text-decoration: none; }
.venture-link:hover { color: var(--accent); }
.venture p, .edu-detail { font-size: 9.5px; color: var(--body); line-height: 1.5; margin-top: 2px; }
.edu-school { display: block; font-weight: 600; font-size: 11px; color: var(--near-blk); margin-bottom: 1px; }
.edu-period { display: block; font-family: 'Source Code Pro', monospace; font-size: 9px; color: var(--soft); margin-bottom: 2px; }
.degree { font-size: 10px; color: var(--body); margin-top: 1px; }
.notable-item { font-size: 10px; line-height: 1.55; margin-bottom: 5px; }
.project { margin-bottom: 14px; }
.project strong, .project-link { font-size: 10px; color: var(--near-blk); font-weight: 600; }
.project-link { text-decoration: none; border-bottom: 1px solid var(--faint); }
.project-link:hover { color: var(--mid); }
.project p { font-size: 9px; color: var(--grey); line-height: 1.5; margin-top: 2px; }
.company-location { font-weight: 400; font-size: 10px; color: var(--grey); }
.speak-entry { display: flex; justify-content: space-between; font-size: 10px; margin-bottom: 5px; }
.speak-title { color: var(--body); }
.speak-year { font-size: 9px; color: var(--soft); }
.skill-group { margin-bottom: 12px; }
.skill-group h4 { font-weight: 500; font-size: 10px; color: var(--dark); margin-bottom: 3px; }
.skill-group p { font-size: 9px; color: var(--grey); line-height: 1.5; }
footer { text-align: center; padding: 24px; }
footer p { font-size: 8px; color: var(--soft); }
@media print {
  body { background: #fff; }
  .page { box-shadow: none; margin: 0; max-width: none; }
  .page-2 { page-break-before: always; }
}
@media screen {
  .page { box-shadow: 0 1px 8px rgba(0,0,0,0.06); margin: 20px auto; }
}
"""
