"""Verdant — Classic elegant CV template.

Personality: McKinsey partner's resume. Forest green headings, gold
horizontal rules, serif name treatment, restrained sophistication.
Timeless and authoritative.
"""

import os
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas

from engine.templates.base import BaseTemplate

PAGE_W, PAGE_H = A4
ML, MR, MB = 24 * mm, 22 * mm, 16 * mm
CW = PAGE_W - ML - MR
RE = ML + CW
CENTER = PAGE_W / 2

GREEN   = HexColor("#1B4332")
GREEN_M = HexColor("#2D6A4F")
GREEN_L = HexColor("#40916C")
GOLD    = HexColor("#D4A843")
GOLD_LT = HexColor("#E8D5A0")
NEAR_BLK= HexColor("#1A1A1A")
DARK    = HexColor("#2C2C2C")
BODY    = HexColor("#3D3D3D")
GREY    = HexColor("#6B6B6B")
SOFT    = HexColor("#999999")
LIGHT   = HexColor("#CCCCCC")
WHITE   = HexColor("#FFFFFF")


class VerdantTemplate(BaseTemplate):
    name = "verdant"
    description = "Classic elegant - forest green, gold rules, serif headings"

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
        t = f"{self.s(m.get('name', ''))}  |  {self.s(m.get('email', ''))}  |  Page {pg}"
        c.setFont("Poppins-Regular", 6); c.setFillColor(SOFT)
        c.drawCentredString(CENTER, MB - 8, t)

    def _gold_rule(self, c, x, y, w):
        c.setStrokeColor(GOLD); c.setLineWidth(0.6)
        c.line(x, y, x + w, y)

    def _section(self, c, y, title):
        y -= 14
        c.setFont("DMSerifText-Regular", 12); c.setFillColor(GREEN)
        c.drawString(ML, y, self.s(title))
        y -= 6
        self._gold_rule(c, ML, y, CW)
        return y - 10

    def _col_section(self, c, x, y, w, title):
        y -= 14
        c.setFont("DMSerifText-Regular", 12); c.setFillColor(GREEN)
        c.drawString(x, y, self.s(title))
        y -= 6
        self._gold_rule(c, x, y, w)
        return y - 10

    # ── PAGE 1 ───────────────────────────────────────────────────────

    def _page1(self, c, ct):
        meta = ct.get("meta", {})

        # Centered name block
        y = PAGE_H - 32 * mm
        c.setFont("DMSerifText-Regular", 30); c.setFillColor(GREEN)
        c.drawCentredString(CENTER, y, self.s(meta.get("name", "")))
        y -= 14

        tagline = self.s(meta.get("tagline", ""))
        if tagline:
            c.setFont("Poppins-Light", 9.5); c.setFillColor(GREY)
            c.drawCentredString(CENTER, y, tagline)
            y -= 12

        # Gold rule under name
        y -= 4
        self._gold_rule(c, ML + CW * 0.2, y, CW * 0.6)
        y -= 10

        # Contact centered
        parts = [meta.get(k, "") for k in ("location", "email", "web", "linkedin")]
        parts = [self.s(p) for p in parts if p]
        if parts:
            c.setFont("Poppins-Regular", 7); c.setFillColor(SOFT)
            c.drawCentredString(CENTER, y, " \u00b7 ".join(parts))
            y -= 8

        # Summary
        summary = ct.get("summary", "")
        if isinstance(summary, dict):
            summary = summary.get("default", "")
        if summary:
            y = self._section(c, y, "Summary")
            st = self.make_style("s", "Poppins-Regular", 8, BODY, leading=13)
            h = self.draw_wrapped(c, summary, st, ML, y, CW)
            y -= h + 4

        # Metrics row
        metrics = ct.get("metrics", [])[:4]
        if metrics:
            y -= 6
            n = len(metrics)
            cw = CW / n
            # Gold top rule
            c.setStrokeColor(GOLD_LT); c.setLineWidth(0.3)
            c.line(ML, y + 4, RE, y + 4)
            by = y - 36
            for i, m in enumerate(metrics):
                cx = ML + cw * i + cw / 2
                c.setFont("Poppins-SemiBold", 15); c.setFillColor(GREEN)
                c.drawCentredString(cx, y - 12, self.s(m.get("value", "")))
                c.setFont("Poppins-Regular", 6.5); c.setFillColor(SOFT)
                c.drawCentredString(cx, y - 25, self.s(m.get("label", "")).upper())
                if i < n - 1:
                    sx = ML + cw * (i + 1)
                    c.setStrokeColor(GOLD_LT); c.setLineWidth(0.3)
                    c.line(sx, y, sx, by + 4)
            c.setStrokeColor(GOLD_LT); c.setLineWidth(0.3)
            c.line(ML, by, RE, by)
            y = by - 8

        # Experience
        exp = [e for e in ct.get("experience", []) if not e.get("_hidden")]
        if exp:
            y = self._section(c, y, "Experience")
            for i, entry in enumerate(exp):
                eh = self._measure_exp(entry)
                if y - eh < MB + 24:
                    self._footer(c, ct, self._pg)
                    c.showPage(); self._pg += 1
                    y = PAGE_H - 20 * mm
                    y = self._section(c, y, "Experience (continued)")
                y = self._draw_exp(c, y, entry)
                if i < len(exp) - 1:
                    y -= 16

        self._footer(c, ct, self._pg)

    def _draw_exp(self, c, y, entry):
        company = self.s(entry.get("company", ""))
        subtitle = self.s(entry.get("subtitle", ""))
        location = self.s(entry.get("location", ""))
        roles = entry.get("roles", [])
        bullets = entry.get("bullets", [])

        c.setFont("Poppins-SemiBold", 9.5); c.setFillColor(NEAR_BLK)
        company_str = company
        if location:
            company_str += f"  \u00b7  {location}"
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
            c.setFont("Poppins-Medium", 8.5); c.setFillColor(DARK)
            c.drawString(ML, y, rt)
            c.setFont("Poppins-Regular", 6.5); c.setFillColor(SOFT)
            c.drawRightString(RE, y + 1, self.s(role.get("period", "")))
            y -= 13

        y -= 0
        bst = self.make_style("b", "Poppins-Regular", 7.5, BODY, leading=11)
        for b in bullets:
            txt = self.s(b.get("text", "") if isinstance(b, dict) else str(b))
            if not txt:
                continue
            # Small green dot bullet - aligned with first line
            c.setFillColor(GREEN_L)
            c.circle(ML + 3, y - 7, 1.5, fill=1, stroke=0)
            h = self.draw_wrapped(c, txt, bst, ML + 12, y, CW - 12)
            y -= h + 2.5
        return y

    def _measure_exp(self, entry):
        h = 12 + (11 if entry.get("subtitle") else 0)
        h += len(entry.get("roles", [])) * 13 + 0
        bst = self.make_style("m", "Poppins-Regular", 7.5, BODY, leading=11)
        for b in entry.get("bullets", []):
            txt = b.get("text", "") if isinstance(b, dict) else str(b)
            if txt:
                h += self.measure_text(txt, bst, CW - 12) + 2.5
        return h

    # ── PAGE 2 ───────────────────────────────────────────────────────

    def _page2(self, c, ct):
        has_p2 = (ct.get("ventures") or ct.get("education") or ct.get("notable")
                  or ct.get("speaking") or ct.get("projects")
                  or (ct.get("skills",{}).get("groups") if isinstance(ct.get("skills",{}), dict) else False))
        if not has_p2:
            return
        c.showPage(); self._pg += 1
        y = PAGE_H - 20 * mm

        gap = 24
        lw = CW * 0.55
        rw = CW - lw - gap
        rx = ML + lw + gap

        # Left: ventures, education, notable
        ly = y
        ventures = [v for v in ct.get("ventures", []) if not v.get("_hidden")]
        if ventures:
            ly = self._col_section(c, ML, ly, lw, "Ventures & Advisory")
            for v in ventures:
                c.setFont("Poppins-SemiBold", 9); c.setFillColor(NEAR_BLK)
                c.drawString(ML, ly, self.s(v.get("name", "")))
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
            ly = self._col_section(c, ML, ly, lw, "Education")
            for e in edu:
                c.setFont("Poppins-SemiBold", 9); c.setFillColor(NEAR_BLK)
                c.drawString(ML, ly, self.s(e.get("school", "")))
                ly -= 12
                deg = self.s(e.get("degree", ""))
                per = self.s(e.get("period", ""))
                if deg:
                    c.setFont("Poppins-Regular", 7.5); c.setFillColor(BODY)
                    c.drawString(ML, ly, deg)
                    if per:
                        c.setFont("Poppins-Regular", 7); c.setFillColor(SOFT)
                        c.drawRightString(ML + lw, ly + 1, per)
                    ly -= 11
                elif per:
                    c.setFont("Poppins-Regular", 7); c.setFillColor(SOFT)
                    c.drawString(ML, ly, per); ly -= 11
                details = e.get("details", [])
                if isinstance(details, str):
                    details = [details] if details else []
                for d in details:
                    st = self.make_style("ed", "Poppins-Regular", 6.5, GREY, leading=9)
                    h = self.draw_wrapped(c, d, st, ML + 4, ly, lw - 4)
                    ly -= h + 2
                ly -= 8

        projects = ct.get("projects", [])
        if projects:
            ly -= 4
            ly = self._col_section(c, ML, ly, lw, "Other Projects")
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
            ly = self._col_section(c, ML, ly, lw, "Beyond Work")
            for item in notable:
                c.setFillColor(GREEN_L)
                c.circle(ML + 3, ly - 3, 1.5, fill=1, stroke=0)
                st = self.make_style("nt", "Poppins-Regular", 7, BODY, leading=10)
                h = self.draw_wrapped(c, item, st, ML + 14, ly, lw - 14)
                ly -= h + 5

        # Right: speaking, skills
        ry = y
        speaking = ct.get("speaking", [])
        if speaking:
            ry = self._col_section(c, rx, ry, rw, "Speaking")
            for s in speaking:
                title = self.s(s.get("title", "") if isinstance(s, dict) else str(s))
                yr = str(s.get("year", "")) if isinstance(s, dict) else ""
                st = self.make_style("sp", "Poppins-Regular", 7, BODY, leading=9.5)
                h = self.draw_wrapped(c, title, st, rx + 8, ry, rw - 38)
                if yr:
                    c.setFont("Poppins-Regular", 7); c.setFillColor(SOFT)
                    c.drawRightString(rx + rw, ry, yr)
                c.setFillColor(GREEN_L)
                c.circle(rx + 3, ry - 3, 1.2, fill=1, stroke=0)
                ry -= h + 5
            ry -= 6

        skills = ct.get("skills", {})
        groups = [g for g in (skills.get("groups", []) if isinstance(skills, dict) else []) if not g.get("_hidden")]
        if groups:
            ry = self._col_section(c, rx, ry, rw, "Expertise")
            for g in groups:
                c.setFont("Poppins-Medium", 7.5); c.setFillColor(GREEN_M)
                c.drawString(rx, ry, self.s(g.get("name", "")))
                ry -= 11
                items = " \u00b7 ".join(self.s(i) for i in g.get("items", []))
                st = self.make_style("sk", "Poppins-Regular", 6.5, GREY, leading=9.5)
                h = self.draw_wrapped(c, items, st, rx, ry, rw)
                ry -= h + 10

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

        metrics_html = ""
        for m in ct.get("metrics", [])[:4]:
            metrics_html += f'<div class="metric"><span class="metric-value">{self.h(m.get("value", ""))}</span><span class="metric-label">{self.h(m.get("label", ""))}</span></div>\n'

        html = self.html_head(
            f"{name} - CV",
            VERDANT_CSS,
            "https://fonts.googleapis.com/css2?family=DM+Serif+Text&family=Poppins:wght@300;400;500;600;700&family=Source+Code+Pro&display=swap"
        )
        html += f"""
<body>
<div class="page page-1">
  <header>
    <h1>{name}</h1>
    <p class="tagline">{tagline}</p>
    <hr class="gold-rule">
    <p class="contact">{contact}</p>
  </header>
  <section class="summary"><h2>Summary</h2><p>{self.h(summary)}</p></section>
  <section class="metrics"><div class="metrics-row">{metrics_html}</div></section>
  <section class="experience"><h2>Experience</h2>{self.html_experience(ct.get("experience", []))}</section>
</div>
<div class="page page-2">
  <div class="two-col">
    <div class="col-left">
      <section class="ventures"><h2>Ventures &amp; Advisory</h2>{self.html_ventures(ct.get("ventures", []))}</section>
      <section class="education"><h2>Education</h2>{self.html_education(ct.get("education", []))}</section>
      <section class="projects"><h2>Other Projects</h2>{self.html_projects(ct.get("projects", []))}</section>
      <section class="notable"><h2>Beyond Work</h2>{self.html_notable(ct.get("notable", []))}</section>
    </div>
    <div class="col-right">
      <section class="speaking"><h2>Speaking</h2>{self.html_speaking(ct.get("speaking", []))}</section>
      <section class="skills"><h2>Expertise</h2>{self.html_skills(ct.get("skills", {}))}</section>
    </div>
  </div>
  <footer><p>{name} &middot; {self.h(meta.get("email", ""))}</p></footer>
</div>
</body></html>"""
        return self._write_html(html, output_path)


VERDANT_CSS = """
:root {
  --green: #1B4332; --green-m: #2D6A4F; --green-l: #40916C;
  --gold: #D4A843; --gold-lt: #E8D5A0;
  --near-blk: #1A1A1A; --dark: #2C2C2C; --body: #3D3D3D;
  --grey: #6B6B6B; --soft: #999; --light: #CCC;
}
@page { size: A4; margin: 0; }
body { background: #EDEDE9; font-family: 'Poppins', sans-serif; color: var(--body); line-height: 1.5; }
.page { background: #fff; max-width: 210mm; margin: 0 auto; padding: 0; position: relative; }
.page-1 { min-height: 297mm; }
.page-2 { min-height: 297mm; padding-top: 32px; }
header { text-align: center; padding: 52px 68px 0; }
header h1 { font-family: 'DM Serif Text', serif; font-size: 34px; color: var(--green); font-weight: 400;
  letter-spacing: -0.3px; margin-bottom: 6px; }
header .tagline { font-weight: 300; font-size: 12px; color: var(--grey); margin-bottom: 10px; }
hr.gold-rule { border: none; height: 1px; background: var(--gold); width: 60%; margin: 0 auto 10px; }
header .contact { font-size: 9px; color: var(--soft); margin-bottom: 0; }
h2 { font-family: 'DM Serif Text', serif; font-size: 14px; color: var(--green); font-weight: 400;
     border-bottom: 1px solid var(--gold); padding-bottom: 6px; margin-bottom: 16px; }
section { padding: 20px 68px 0; }
.summary p { font-size: 11px; line-height: 1.65; }
.metrics-row { display: flex; border-top: 1px solid var(--gold-lt); border-bottom: 1px solid var(--gold-lt); padding: 14px 0; }
.metric { flex: 1; text-align: center; border-right: 1px solid var(--gold-lt); }
.metric:last-child { border-right: none; }
.metric-value { display: block; font-weight: 600; font-size: 18px; color: var(--green); }
.metric-label { display: block; font-size: 8px; color: var(--soft); text-transform: uppercase; letter-spacing: 0.5px; margin-top: 2px; }
.exp-entry { margin-bottom: 14px; }
.exp-header { display: flex; justify-content: space-between; align-items: baseline; }
.company { font-weight: 600; font-size: 12px; color: var(--near-blk); }
.company-years { font-weight: 500; font-size: 11px; color: var(--dark); }
.period { font-size: 9px; color: var(--soft); }
.subtitle { font-size: 9.5px; color: var(--grey); margin: 1px 0 3px; }
.role { display: flex; justify-content: space-between; margin-bottom: 2px; }
.role-title { font-weight: 500; font-size: 11px; color: var(--dark); }
.role-location { font-weight: 400; color: var(--grey); }
.role-period { font-size: 9px; color: var(--soft); }
ul.bullets { list-style: none; padding: 4px 0 0; }
ul.bullets li { font-size: 10px; line-height: 1.55; color: var(--body); padding: 2px 0 2px 16px; position: relative; }
ul.bullets li::before { content: ''; width: 5px; height: 5px; background: var(--green-l); border-radius: 50%;
  position: absolute; left: 2px; top: 8px; }
.two-col { display: grid; grid-template-columns: 55% 1fr; gap: 28px; padding: 0 68px; }
.col-left section, .col-right section { padding: 0; margin-bottom: 20px; }
.venture, .edu-entry { margin-bottom: 16px; }
.venture-header, .edu-header { display: flex; justify-content: space-between; align-items: baseline; }
.venture p, .edu-detail { font-size: 9.5px; line-height: 1.5; margin-top: 2px; }
.degree { font-size: 10px; margin-top: 1px; }
.notable-item { font-size: 10px; line-height: 1.55; padding-left: 16px; position: relative; margin-bottom: 5px; }
.notable-item::before { content: ''; width: 5px; height: 5px; background: var(--green-l); border-radius: 50%;
  position: absolute; left: 2px; top: 7px; }
.project { margin-bottom: 14px; }
.project strong, .project-link { font-size: 10px; color: var(--near-blk); font-weight: 600; }
.project-link { text-decoration: none; border-bottom: 1px solid var(--gold-lt); }
.project-link:hover { color: var(--green); border-color: var(--green); }
.project p { font-size: 9px; color: var(--grey); line-height: 1.5; margin-top: 2px; }
.company-location { font-weight: 400; font-size: 10px; color: var(--grey); }
.speak-entry { display: flex; justify-content: space-between; font-size: 10px; margin-bottom: 5px; }
.speak-title { color: var(--body); padding-left: 12px; position: relative; }
.speak-title::before { content: ''; width: 4px; height: 4px; background: var(--green-l); border-radius: 50%;
  position: absolute; left: 2px; top: 7px; }
.speak-year { font-size: 9px; color: var(--soft); }
.skill-group { margin-bottom: 10px; }
.skill-group h4 { font-weight: 500; font-size: 10px; color: var(--green-m); margin-bottom: 3px; }
.skill-group p { font-size: 9px; color: var(--grey); line-height: 1.5; }
footer { text-align: center; padding: 20px; }
footer p { font-size: 8px; color: var(--soft); }
@media print {
  body { background: #fff; }
  .page { box-shadow: none; margin: 0; max-width: none; }
  .page-2 { page-break-before: always; }
}
@media screen {
  .page { box-shadow: 0 1px 10px rgba(0,0,0,0.07); margin: 20px auto; }
}
"""
