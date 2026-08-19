"""Folio — Magazine editorial CV with asymmetric date column.

Personality: Monocle magazine meets annual report. Wide left date/period
column (25%) with right-aligned dates, content in the remaining 75%.
Terracotta accent, warm white background, bold typographic hierarchy.
"""

import os
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas

from engine.metrics import renderable_metrics
from engine.templates.base import BaseTemplate

PAGE_W, PAGE_H = A4
ML, MR, MB = 22 * mm, 20 * mm, 16 * mm
CW = PAGE_W - ML - MR
RE = ML + CW

# Date column layout
DATE_W = CW * 0.22
CONTENT_X = ML + DATE_W + 12
CONTENT_W = CW - DATE_W - 12

CHARCOAL  = HexColor("#1F1F1F")
DARK      = HexColor("#2D2D2D")
BODY      = HexColor("#404040")
GREY      = HexColor("#6B6B6B")
SOFT      = HexColor("#999999")
LIGHT     = HexColor("#CCCCCC")
TERRA     = HexColor("#C04000")
TERRA_LT  = HexColor("#D4714A")
WARM_BG   = HexColor("#FAFAF8")
RULE      = HexColor("#E8E6E2")
WHITE     = HexColor("#FFFFFF")


class FolioTemplate(BaseTemplate):
    name = "folio"
    description = "Editorial asymmetric - terracotta accent, date column layout"

    def render_pdf(self, content: dict, output_path: str) -> str:
        ct = self.prep(content)
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        c = Canvas(output_path, pagesize=A4)
        self._pg = 1
        self._y_after_exp = None
        self._page1(c, ct)
        self._page2(c, ct)
        c.save()
        return output_path

    def _bg(self, c):
        c.setFillColor(WARM_BG)
        c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    def _footer(self, c, ct, pg):
        m = ct.get("meta", {})
        c.setFont("Poppins-Regular", 6); c.setFillColor(SOFT)
        c.drawString(ML, MB - 8, self.s(m.get("name", "")))
        c.drawRightString(RE, MB - 8, f"Page {pg}")

    def _section(self, c, y, title):
        y -= 16
        # Section title in date column area, right-aligned
        c.setFont("Poppins-SemiBold", 7); c.setFillColor(TERRA)
        c.drawRightString(ML + DATE_W, y, self.s(title).upper())
        # Rule across content area
        c.setStrokeColor(RULE); c.setLineWidth(0.4)
        c.line(CONTENT_X, y - 2, RE, y - 2)
        return y - 14

    # ── PAGE 1 ───────────────────────────────────────────────────────

    def _page1(self, c, ct):
        self._bg(c)
        meta = ct.get("meta", {})

        # Terracotta accent strip at top
        c.setFillColor(TERRA)
        c.rect(0, PAGE_H - 3, PAGE_W, 3, fill=1, stroke=0)

        # Header: name bold, large
        y = PAGE_H - 34 * mm
        c.setFont("Poppins-Bold", 30); c.setFillColor(CHARCOAL)
        c.drawString(ML, y, self.s(meta.get("name", "")))
        y -= 16

        tagline = self.s(meta.get("tagline", ""))
        if tagline:
            c.setFont("Poppins-Light", 10); c.setFillColor(GREY)
            c.drawString(ML, y, tagline)
            y -= 14

        # Contact in terracotta
        parts = [meta.get(k, "") for k in ("location", "email", "web", "linkedin")]
        parts = [self.s(p) for p in parts if p]
        if parts:
            c.setFont("Poppins-Regular", 7); c.setFillColor(TERRA_LT)
            c.drawString(ML, y, " \u00b7 ".join(parts))
            y -= 6

        # Thick rule
        y -= 6
        c.setStrokeColor(CHARCOAL); c.setLineWidth(1.5)
        c.line(ML, y, RE, y)
        y -= 4

        # Summary - spans full width
        summary = ct.get("summary", "")
        if isinstance(summary, dict):
            summary = summary.get("default", "")
        if summary:
            y -= 12
            c.setFont("Poppins-SemiBold", 7); c.setFillColor(TERRA)
            c.drawRightString(ML + DATE_W, y, "SUMMARY")
            st = self.make_style("s", "Poppins-Regular", 8, BODY, leading=13)
            h = self.draw_wrapped(c, summary, st, CONTENT_X, y, CONTENT_W)
            y -= h + 4

        # Metrics - in date column style
        metrics = renderable_metrics(ct.get("metrics"))
        if metrics:
            y -= 8
            c.setFont("Poppins-SemiBold", 7); c.setFillColor(TERRA)
            c.drawRightString(ML + DATE_W, y, "KEY METRICS")
            n = len(metrics)
            mw = CONTENT_W / n
            for i, m in enumerate(metrics):
                mx = CONTENT_X + mw * i
                c.setFont("Poppins-SemiBold", 15); c.setFillColor(CHARCOAL)
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
                if y - eh < MB + 24:
                    self._footer(c, ct, self._pg)
                    c.showPage(); self._pg += 1; self._bg(c)
                    c.setFillColor(TERRA)
                    c.rect(0, PAGE_H - 1.5, PAGE_W, 1.5, fill=1, stroke=0)
                    y = PAGE_H - 20 * mm
                    y = self._section(c, y, "Experience")
                y = self._draw_exp(c, y, entry)
                if i < len(exp) - 1:
                    y -= 18

        self._y_after_exp = y
        self._footer(c, ct, self._pg)

    def _draw_exp(self, c, y, entry):
        company = self.s(entry.get("company", ""))
        subtitle = self.s(entry.get("subtitle", ""))
        location = self.s(entry.get("location", ""))
        roles = entry.get("roles", [])
        bullets = entry.get("bullets", [])

        # Year range in date column
        yr = self.year_range(roles)
        if yr:
            c.setFont("Poppins-Medium", 8); c.setFillColor(DARK)
            c.drawRightString(ML + DATE_W, y + 1, yr)

        # Company + location in content column
        c.setFont("Poppins-SemiBold", 9.5); c.setFillColor(CHARCOAL)
        company_str = company
        if location:
            company_str += f"  \u00b7  {location}"
        c.drawString(CONTENT_X, y, company_str)
        y -= 12

        if subtitle:
            c.setFont("Poppins-Regular", 7); c.setFillColor(GREY)
            c.drawString(CONTENT_X, y, subtitle)
            y -= 16

        for role in roles:
            rt = self.s(role.get("title", ""))
            c.setFont("Poppins-Medium", 8.5); c.setFillColor(DARK)
            c.drawString(CONTENT_X, y, rt)
            per = self.s(role.get("period", ""))
            c.setFont("Poppins-Regular", 6.5); c.setFillColor(SOFT)
            c.drawRightString(ML + DATE_W, y + 1, per)
            y -= 13

        y -= 0
        bst = self.make_style("b", "Poppins-Regular", 7.5, BODY, leading=11)
        for b in bullets:
            txt = self.s(b.get("text", "") if isinstance(b, dict) else str(b))
            if not txt:
                continue
            # Triangle bullet in margin, text aligned with company/roles
            c.setFillColor(TERRA_LT)
            c.setFont("Poppins-Regular", 6)
            c.drawString(CONTENT_X - 8, y - 7, "\u25b8")
            h = self.draw_wrapped(c, txt, bst, CONTENT_X, y, CONTENT_W)
            y -= h + 2.5
        return y

    def _measure_exp(self, entry):
        h = 12 + (11 if entry.get("subtitle") else 0)
        h += len(entry.get("roles", [])) * 13 + 0
        bst = self.make_style("m", "Poppins-Regular", 7.5, BODY, leading=11)
        for b in entry.get("bullets", []):
            txt = b.get("text", "") if isinstance(b, dict) else str(b)
            if txt:
                h += self.measure_text(txt, bst, CONTENT_W) + 2.5
        return h

    # ── PAGE 2 ───────────────────────────────────────────────────────

    def _page2(self, c, ct):
        has_p2 = (ct.get("ventures") or ct.get("education") or ct.get("notable")
                  or ct.get("speaking") or ct.get("projects")
                  or (ct.get("skills",{}).get("groups") if isinstance(ct.get("skills",{}), dict) else False))
        if not has_p2:
            return
        # If experience overflowed and there's room left, continue on same page
        if self._pg > 1 and self._y_after_exp and self._y_after_exp > MB + 120:
            y = self._y_after_exp - 8
        else:
            c.showPage(); self._pg += 1; self._bg(c)
            c.setFillColor(TERRA)
            c.rect(0, PAGE_H - 1.5, PAGE_W, 1.5, fill=1, stroke=0)
            y = PAGE_H - 20 * mm

        # Ventures - with date column
        ventures = [v for v in ct.get("ventures", []) if not v.get("_hidden")]
        if ventures:
            y = self._section(c, y, "Ventures")
            for v in ventures:
                per = self.s(v.get("period", ""))
                c.setFont("Poppins-Regular", 7); c.setFillColor(SOFT)
                c.drawRightString(ML + DATE_W, y + 1, per)
                vname = self.s(v.get("name", ""))
                c.setFont("Poppins-SemiBold", 9); c.setFillColor(CHARCOAL)
                c.drawString(CONTENT_X, y, vname)
                vurl = self.s(v.get("url", ""))
                if vurl:
                    x_url = CONTENT_X + c.stringWidth(vname, "Poppins-SemiBold", 9) + 6
                    c.setFont("SourceCodePro-Regular", 6.5); c.setFillColor(SOFT)
                    c.drawString(x_url, y + 0.5, vurl)
                y -= 12
                desc = self.s(v.get("description", ""))
                if desc:
                    st = self.make_style("vd", "Poppins-Regular", 7, BODY, leading=10)
                    h = self.draw_wrapped(c, desc, st, CONTENT_X, y, CONTENT_W)
                    y -= h
                y -= 14

        edu = ct.get("education", [])
        if edu:
            y = self._section(c, y, "Education")
            for e in edu:
                c.setFont("Poppins-SemiBold", 9); c.setFillColor(CHARCOAL)
                c.drawString(CONTENT_X, y, self.s(e.get("school", "")))
                y -= 12
                deg = self.s(e.get("degree", ""))
                per = self.s(e.get("period", ""))
                if deg:
                    c.setFont("Poppins-Regular", 7.5); c.setFillColor(BODY)
                    c.drawString(CONTENT_X, y, deg)
                    if per:
                        c.setFont("Poppins-Regular", 7); c.setFillColor(SOFT)
                        c.drawRightString(ML + DATE_W, y + 1, per)
                    y -= 11
                elif per:
                    c.setFont("Poppins-Regular", 7); c.setFillColor(SOFT)
                    c.drawRightString(ML + DATE_W, y + 1, per); y -= 11
                y -= 8

        projects = ct.get("projects", [])
        if projects:
            y = self._section(c, y, "Other Projects")
            for proj in projects:
                name = self.s(proj.get("name", ""))
                url = proj.get("url", "")
                c.setFont("Poppins-SemiBold", 8); c.setFillColor(CHARCOAL)
                c.drawString(CONTENT_X, y, name)
                if url:
                    c.setFont("Poppins-Regular", 6); c.setFillColor(SOFT)
                    c.drawString(CONTENT_X + c.stringWidth(name, "Poppins-SemiBold", 8) + 6, y + 0.5, url)
                y -= 10
                desc = self.s(proj.get("description", ""))
                if desc:
                    st = self.make_style("pd", "Poppins-Regular", 6.5, GREY, leading=9)
                    h = self.draw_wrapped(c, desc, st, CONTENT_X, y, CONTENT_W)
                    y -= h + 10

        # Bottom section: skills + speaking side by side
        y -= 4
        gap = 24
        half = (CW - gap) / 2
        rx = ML + half + gap

        skills = ct.get("skills", {})
        groups = [g for g in (skills.get("groups", []) if isinstance(skills, dict) else []) if not g.get("_hidden")]
        if groups:
            sy = y
            sy -= 12
            c.setFont("Poppins-SemiBold", 7); c.setFillColor(TERRA)
            c.drawString(ML, sy, "EXPERTISE")
            sy -= 4
            c.setStrokeColor(RULE); c.setLineWidth(0.4)
            c.line(ML, sy, ML + half, sy)
            sy -= 10
            for g in groups:
                c.setFont("Poppins-Medium", 7.5); c.setFillColor(DARK)
                c.drawString(ML, sy, self.s(g.get("name", "")))
                sy -= 11
                items = " \u00b7 ".join(self.s(i) for i in g.get("items", []))
                st = self.make_style("sk", "Poppins-Regular", 6.5, GREY, leading=9.5)
                h = self.draw_wrapped(c, items, st, ML, sy, half)
                sy -= h + 10

        speaking = ct.get("speaking", [])
        notable = ct.get("notable", [])
        if speaking or notable:
            sy = y
            sy -= 12
            c.setFont("Poppins-SemiBold", 7); c.setFillColor(TERRA)
            c.drawString(rx, sy, "SPEAKING & NOTABLE")
            sy -= 4
            c.setStrokeColor(RULE); c.setLineWidth(0.4)
            c.line(rx, sy, rx + half, sy)
            sy -= 10
            for s in speaking:
                title = self.s(s.get("title", "") if isinstance(s, dict) else str(s))
                yr = str(s.get("year", "")) if isinstance(s, dict) else ""
                c.setFillColor(TERRA_LT); c.setFont("Poppins-Regular", 6)
                c.drawString(rx, sy - 1, "\u25b8")
                st = self.make_style("sp", "Poppins-Regular", 7, BODY, leading=9.5)
                h = self.draw_wrapped(c, title, st, rx + 10, sy, half - 40)
                if yr:
                    c.setFont("Poppins-Regular", 7); c.setFillColor(SOFT)
                    c.drawRightString(rx + half, sy, yr)
                sy -= h + 5
            if notable:
                sy -= 6
                for item in notable:
                    c.setFillColor(TERRA_LT); c.setFont("Poppins-Regular", 6)
                    c.drawString(rx, sy - 1, "\u25b8")
                    st = self.make_style("nt", "Poppins-Regular", 7, BODY, leading=9.5)
                    h = self.draw_wrapped(c, item, st, rx + 10, sy, half - 10)
                    sy -= h + 5

        self._footer(c, ct, self._pg)

    # ── HTML ─────────────────────────────────────────────────────────

    def render_html(self, content: dict, output_path: str) -> str:
        ct = self.prep(content)
        meta = ct.get("meta", {})
        name = self.h(meta.get("name", ""))
        tagline = self.h(meta.get("tagline", ""))
        contact = " &middot; ".join(self.h(meta.get(k, "")) for k in ("location", "email", "web", "linkedin") if meta.get(k))
        summary = ct.get("summary", "")
        if isinstance(summary, dict):
            summary = summary.get("default", "")

        # Build experience with date column
        exp_html = ""
        for entry in ct.get("experience", []):
            if entry.get("_hidden"):
                continue
            roles = entry.get("roles", [])
            period = self.h(self.year_range(roles))
            company = self.h(entry.get("company", ""))
            subtitle = self.h(entry.get("subtitle", ""))
            location = self.h(entry.get("location", ""))
            loc_str = f' <span class="company-location">{location}</span>' if location else ""

            roles_html = ""
            for role in roles:
                t = self.h(role.get("title", ""))
                roles_html += f'<div class="role"><span class="role-title">{t}</span></div>\n'

            bullets_html = ""
            for b in entry.get("bullets", []):
                text = self.h(b.get("text", "") if isinstance(b, dict) else str(b))
                if text:
                    bullets_html += f"<li>{text}</li>\n"

            exp_html += f"""<div class="entry-row">
<div class="date-col">{period}</div>
<div class="content-col">
  <h3 class="company">{company}{loc_str}</h3>
  {"<p class='subtitle'>" + subtitle + "</p>" if subtitle else ""}
  {roles_html}
  <ul class="bullets">{bullets_html}</ul>
</div></div>\n"""

        # Build ventures with date column
        ventures_html = ""
        for v in ct.get("ventures", []):
            if v.get("_hidden"):
                continue
            vurl = v.get("url", "")
            url_html = f' <a href="https://{self.h(vurl)}" class="venture-link">{self.h(vurl)}</a>' if vurl else ""
            ventures_html += f"""<div class="entry-row">
<div class="date-col">{self.h(v.get("period", ""))}</div>
<div class="content-col"><span class="venture-name"><strong>{self.h(v.get("name", ""))}</strong>{url_html}</span><p>{self.h(v.get("description", ""))}</p></div></div>\n"""

        # Build education with date column (no details — location info is superfluous in Folio)
        edu_html = ""
        for e in ct.get("education", []):
            edu_html += f"""<div class="entry-row">
<div class="date-col">{self.h(e.get("period", ""))}</div>
<div class="content-col"><strong>{self.h(e.get("school", ""))}</strong><p class="degree">{self.h(e.get("degree", ""))}</p></div></div>\n"""

        metrics_html = ""
        for m in renderable_metrics(ct.get("metrics")):
            metrics_html += f'<div class="metric"><span class="metric-value">{self.h(m.get("value", ""))}</span><span class="metric-label">{self.h(m.get("label", ""))}</span></div>\n'

        metrics_section = (
            '<section class="metrics"><div class="entry-row">'
            '<div class="date-col label">KEY METRICS</div>'
            f'<div class="content-col"><div class="metrics-row">{metrics_html}</div></div>'
            '</div></section>'
        ) if metrics_html else ""

        html = self.html_head(
            f"{name} - CV",
            FOLIO_CSS,
            "https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&family=Source+Code+Pro&display=swap"
        )
        html += f"""
<body>
<div class="page page-1">
  <div class="accent-bar"></div>
  <header>
    <h1>{name}</h1>
    <p class="tagline">{tagline}</p>
    <p class="contact">{contact}</p>
  </header>
  <hr class="thick-rule">
  <section class="summary">
    <div class="entry-row"><div class="date-col label">SUMMARY</div><div class="content-col"><p>{self.h(summary)}</p></div></div>
  </section>
  {metrics_section}
  <section class="experience"><div class="section-header"><div class="date-col label">EXPERIENCE</div><div class="content-col"><hr></div></div>{exp_html}</section>
</div>
<div class="page page-2">
  <div class="accent-bar thin"></div>
  <section class="ventures"><div class="section-header"><div class="date-col label">VENTURES</div><div class="content-col"><hr></div></div>{ventures_html}</section>
  <section class="education"><div class="section-header"><div class="date-col label">EDUCATION</div><div class="content-col"><hr></div></div>{edu_html}</section>
  <section class="projects"><div class="section-header"><div class="date-col label">PROJECTS</div><div class="content-col"><hr></div></div>{"".join(f'<div class="entry-row"><div class="date-col"></div><div class="content-col"><strong>{self.h(p.get("name",""))}</strong><p class="subtitle">{self.h(p.get("description",""))}</p></div></div>' for p in ct.get("projects",[]))}</section>
  <div class="two-col">
    <section class="skills"><h2>Expertise</h2>{self.html_skills(ct.get("skills", {}))}</section>
    <section class="speaking-notable"><h2>Speaking &amp; Notable</h2>{self.html_speaking(ct.get("speaking", []))}{self.html_notable(ct.get("notable", []))}</section>
  </div>
  <footer><span>{name}</span><span>Page 2</span></footer>
</div>
</body></html>"""
        return self._write_html(html, output_path)


FOLIO_CSS = """
:root {
  --charcoal: #1F1F1F; --dark: #2D2D2D; --body: #404040;
  --grey: #6B6B6B; --soft: #999; --light: #CCC;
  --terra: #C04000; --terra-lt: #D4714A;
  --warm-bg: #FAFAF8; --rule: #E8E6E2;
}
@page { size: A4; margin: 0; }
body { background: #E8E6E2; font-family: 'Poppins', sans-serif; color: var(--body); line-height: 1.5; }
.page { background: var(--warm-bg); max-width: 210mm; margin: 0 auto; padding: 0; position: relative; }
.page-1 { min-height: 297mm; }
.page-2 { min-height: 297mm; padding-top: 20px; }
.accent-bar { height: 4px; background: var(--terra); }
.accent-bar.thin { height: 2px; }
header { padding: 40px 62px 0; }
header h1 { font-size: 32px; font-weight: 700; color: var(--charcoal); letter-spacing: -0.5px; margin-bottom: 4px; }
header .tagline { font-weight: 300; font-size: 12px; color: var(--grey); margin-bottom: 6px; }
header .contact { font-size: 9px; color: var(--terra-lt); margin-bottom: 0; }
hr.thick-rule { border: none; height: 2px; background: var(--charcoal); margin: 16px 62px 0; }
.entry-row { display: grid; grid-template-columns: 22% 1fr; gap: 14px; align-items: start; }
.date-col { font-size: 9px; color: var(--soft); text-align: right; padding-top: 2px; }
.date-col.label { font-size: 8px; font-weight: 600; color: var(--terra); letter-spacing: 1px; }
.content-col { }
.section-header { margin-bottom: 10px; }
.section-header hr { border: none; border-top: 1px solid var(--rule); margin-top: 6px; }
h2 { font-size: 8px; font-weight: 600; color: var(--terra); text-transform: uppercase;
     letter-spacing: 1px; border-bottom: 1px solid var(--rule); padding-bottom: 6px; margin-bottom: 12px; }
section { padding: 14px 62px 0; }
.summary p { font-size: 11px; line-height: 1.65; }
.metrics-row { display: flex; gap: 0; }
.metric { flex: 1; }
.metric-value { display: block; font-weight: 600; font-size: 18px; color: var(--charcoal); }
.metric-label { display: block; font-size: 8px; color: var(--soft); text-transform: uppercase; letter-spacing: 0.5px; margin-top: 2px; }
.company { font-weight: 600; font-size: 12px; color: var(--charcoal); }
.company-years { font-weight: 500; font-size: 11px; color: var(--dark); }
.subtitle { font-size: 9.5px; color: var(--grey); margin: 1px 0 3px; }
.role { margin-bottom: 2px; }
.role-title { font-weight: 500; font-size: 10.5px; color: var(--dark); }
.role-loc { font-weight: 400; color: var(--grey); }
ul.bullets { list-style: none; padding: 4px 0 0; }
ul.bullets li { font-size: 10px; line-height: 1.55; color: var(--body); padding: 2px 0 2px 14px; position: relative; }
ul.bullets li::before { content: '\\25b8'; color: var(--terra-lt); position: absolute; left: 0; font-size: 9px; }
.exp-entry, .entry-row { margin-bottom: 12px; }
.venture p, .edu-detail { font-size: 9.5px; line-height: 1.5; margin-top: 2px; }
.venture-name { display: flex; align-items: baseline; gap: 6px; }
.venture-link { font-family: 'Source Code Pro', monospace; font-size: 9px; color: var(--soft); text-decoration: none; }
.venture-link:hover { color: var(--terra); }
.degree { font-size: 10px; margin-top: 1px; }
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 28px; padding: 20px 62px 0; padding-bottom: 40px; }
.two-col section { padding: 0; }
footer { display: flex; justify-content: space-between; padding: 12px 62px; font-family: 'Source Code Pro', monospace; font-size: 9px; color: var(--soft); border-top: 1px solid var(--rule); margin-top: 4px; }
.skill-group { margin-bottom: 10px; }
.skill-group h4 { font-weight: 500; font-size: 10px; color: var(--dark); margin-bottom: 3px; }
.skill-group p { font-size: 9px; color: var(--grey); line-height: 1.5; }
.speak-entry { display: flex; justify-content: space-between; font-size: 9.5px; margin-bottom: 4px; }
.speak-title { color: var(--body); padding-left: 12px; position: relative; }
.speak-title::before { content: '\\25b8'; color: var(--terra-lt); position: absolute; left: 0; font-size: 8px; }
.speak-year { font-size: 8.5px; color: var(--soft); }
.notable-item { font-size: 9.5px; line-height: 1.5; padding-left: 12px; position: relative; margin-bottom: 4px; }
.notable-item::before { content: '\\25b8'; color: var(--terra-lt); position: absolute; left: 0; font-size: 8px; top: 2px; }
.project { margin-bottom: 14px; }
.project strong, .project-link { font-size: 10px; color: var(--charcoal); font-weight: 600; }
.project-link { text-decoration: none; border-bottom: 1px solid var(--rule); }
.project-link:hover { color: var(--terra); border-color: var(--terra); }
.project p { font-size: 9px; color: var(--grey); line-height: 1.5; margin-top: 2px; }
.company-location { font-weight: 400; font-size: 10px; color: var(--grey); }
footer { display: flex; justify-content: space-between; padding: 24px 62px; font-size: 8px; color: var(--soft); }
@media print {
  body { background: var(--warm-bg); }
  .page { box-shadow: none; margin: 0; max-width: none; }
  .page-2 { page-break-before: always; }
}
@media screen {
  .page { box-shadow: 0 1px 10px rgba(0,0,0,0.07); margin: 20px auto; }
}
"""
