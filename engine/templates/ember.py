"""Ember — Warm, editorial CV template.

Personality: Coffee-table book. Cream background, dark header band,
rust accents, gold tagline. Typography-driven hierarchy.
"""

import os
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph

from engine.templates.base import BaseTemplate

PAGE_W, PAGE_H = A4
ML, MR, MB = 24 * mm, 22 * mm, 16 * mm
CW = PAGE_W - ML - MR
RE = ML + CW

INK     = HexColor("#1C1C28")
CHARCOAL= HexColor("#2A2A3E")
SLATE   = HexColor("#3A3A50")
RUST    = HexColor("#B8522A")
GOLD    = HexColor("#C8872A")
DIM     = HexColor("#7A7A8A")
LIGHT   = HexColor("#A0A0AE")
CREAM   = HexColor("#FEFBF5")
RULE    = HexColor("#E0DDD5")
WHITE   = HexColor("#FFFFFF")


class EmberTemplate(BaseTemplate):
    name = "ember"
    description = "Warm editorial - cream background, rust accents, serif headings"

    def render_pdf(self, content: dict, output_path: str) -> str:
        content = self.prep(content)
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        c = Canvas(output_path, pagesize=A4)
        self._c = c
        self._content = content
        self._pg = 1
        self._page1(c, content)
        self._page2(c, content)
        c.save()
        return output_path

    def _bg(self, c):
        c.setFillColor(CREAM); c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    def _footer(self, c, content, pg):
        m = content.get("meta", {})
        t = f"{self.s(m.get('name',''))}  |  {self.s(m.get('email',''))}  |  Page {pg}"
        c.setFont("SourceCodePro-Regular", 6.5); c.setFillColor(LIGHT)
        c.drawCentredString(PAGE_W/2, MB - 8, t)

    def _section(self, c, y, title):
        y -= 8
        c.setFont("DMSerifText-Regular", 11); c.setFillColor(RUST)
        c.drawString(ML, y, self.s(title))
        ry = y - 3*mm
        c.setStrokeColor(RULE); c.setLineWidth(0.5)
        c.line(ML, ry, RE, ry)
        return ry - 5*mm

    def _col_section(self, c, x, y, w, title):
        y -= 8
        c.setFont("DMSerifText-Regular", 11); c.setFillColor(RUST)
        c.drawString(x, y, self.s(title))
        ry = y - 3*mm
        c.setStrokeColor(RULE); c.setLineWidth(0.5)
        c.line(x, ry, x+w, ry)
        return ry - 5*mm

    # ── PAGE 1 ───────────────────────────────────────────────────────

    def _page1(self, c, ct):
        self._bg(c)
        # Accent bar
        c.setFillColor(RUST); c.rect(0, PAGE_H-2, PAGE_W, 2, fill=1, stroke=0)
        # Header band
        hh = 96; ht = PAGE_H-2; hb = ht-hh
        c.setFillColor(INK); c.rect(0, hb, PAGE_W, hh, fill=1, stroke=0)
        meta = ct.get("meta", {})
        c.setFont("DMSerifText-Regular", 32); c.setFillColor(WHITE)
        c.drawString(ML, hb+52, self.s(meta.get("name","")))
        c.setFont("Poppins-Light", 10); c.setFillColor(GOLD)
        c.drawString(ML, hb+33, self.s(meta.get("tagline","")))
        cp = [meta.get(k,"") for k in ("location","email","web","linkedin")]
        c.setFont("SourceCodePro-Regular", 6.5); c.setFillColor(LIGHT)
        c.drawString(ML, hb+14, " \u00b7 ".join(self.s(p) for p in cp if p))

        y = hb - 16

        # Summary
        summary = ct.get("summary","")
        if isinstance(summary, dict): summary = summary.get("default","")
        if summary:
            y = self._section(c, y, "Summary")
            st = self.make_style("s", "Poppins-Regular", 7.8, SLATE, leading=12.5)
            h = self.draw_wrapped(c, summary, st, ML, y, CW)
            y -= h + 8

        # Metrics
        metrics = ct.get("metrics", [])[:4]
        if metrics:
            n = len(metrics); cw = CW/n
            ty = y + 2
            c.setStrokeColor(RULE); c.setLineWidth(0.4); c.line(ML, ty, RE, ty)
            by = ty - 38
            for i, m in enumerate(metrics):
                cx = ML + cw*i + cw/2
                c.setFont("Poppins-SemiBold", 15); c.setFillColor(INK)
                c.drawCentredString(cx, ty-16, self.s(m.get("value","")))
                c.setFont("Poppins-Regular", 6.5); c.setFillColor(DIM)
                c.drawCentredString(cx, ty-29, self.s(m.get("label","")).upper())
                if i < n-1:
                    sx = ML + cw*(i+1)
                    c.setStrokeColor(RULE); c.setLineWidth(0.3)
                    c.line(sx, ty-6, sx, by+6)
            c.setStrokeColor(RULE); c.setLineWidth(0.4); c.line(ML, by, RE, by)
            y = by - 8

        # Experience
        exp = [e for e in ct.get("experience",[]) if not e.get("_hidden")]
        if exp:
            y = self._section(c, y, "Experience")
            for i, entry in enumerate(exp):
                eh = self._measure_exp(entry)
                if y - eh < MB + 24:
                    self._footer(c, ct, self._pg)
                    c.showPage(); self._pg += 1; self._bg(c)
                    c.setFillColor(RUST); c.rect(0, PAGE_H-1.5, PAGE_W, 1.5, fill=1, stroke=0)
                    y = PAGE_H - 20*mm
                    y = self._section(c, y, "Experience (continued)")
                y = self._draw_exp(c, y, entry)
                if i < len(exp)-1: y -= 16

        self._footer(c, ct, self._pg)

    def _draw_exp(self, c, y, entry):
        company = self.s(entry.get("company",""))
        subtitle = self.s(entry.get("subtitle",""))
        location = self.s(entry.get("location",""))
        roles = entry.get("roles",[])
        bullets = entry.get("bullets",[])

        c.setFont("Poppins-SemiBold", 9.5); c.setFillColor(INK)
        company_str = company
        if location:
            company_str += f"  \u00b7  {location}"
        c.drawString(ML, y, company_str)
        yr = self.year_range(roles)
        if yr:
            c.setFont("Poppins-Medium", 9); c.setFillColor(CHARCOAL)
            c.drawRightString(RE, y+1, yr)
        y -= 12
        if subtitle:
            c.setFont("Poppins-Regular", 7); c.setFillColor(DIM)
            c.drawString(ML, y, subtitle); y -= 12
        for j, role in enumerate(roles):
            rt = self.s(role.get("title",""))
            c.setFont("Poppins-Medium", 8.5); c.setFillColor(CHARCOAL)
            c.drawString(ML, y, rt)
            c.setFont("SourceCodePro-Regular", 6.5); c.setFillColor(LIGHT)
            c.drawRightString(RE, y+1, self.s(role.get("period","")))
            y -= 13
        y -= 1
        bst = self.make_style("b", "Poppins-Regular", 7.5, SLATE, leading=11)
        for b in bullets:
            txt = self.s(b.get("text","") if isinstance(b, dict) else str(b))
            if not txt: continue
            c.setFont("Poppins-Regular", 7.5); c.setFillColor(RUST)
            c.drawString(ML, y-7, "\u2022")
            h = self.draw_wrapped(c, txt, bst, ML+10, y, CW-10)
            y -= h + 2.5
        return y

    def _measure_exp(self, entry):
        h = 12
        if entry.get("subtitle"): h += 12
        h += len(entry.get("roles",[]))*13 + 1
        bst = self.make_style("m", "Poppins-Regular", 7.5, SLATE, leading=11)
        for b in entry.get("bullets",[]):
            txt = b.get("text","") if isinstance(b, dict) else str(b)
            if txt: h += self.measure_text(txt, bst, CW-10) + 2.5
        return h

    # ── PAGE 2 ───────────────────────────────────────────────────────

    def _page2(self, c, ct):
        # Check if there's any content for page 2
        has_p2 = (ct.get("ventures") or ct.get("education") or ct.get("notable")
                  or ct.get("speaking") or ct.get("projects")
                  or (ct.get("skills",{}).get("groups") if isinstance(ct.get("skills",{}), dict) else False))
        if not has_p2:
            return
        c.showPage(); self._pg += 1; self._bg(c)
        c.setFillColor(RUST); c.rect(0, PAGE_H-1.5, PAGE_W, 1.5, fill=1, stroke=0)
        top = PAGE_H - 20*mm
        gap = 20; lw = CW*0.56; rw = CW-lw-gap; rx = ML+lw+gap

        # Left column
        y = top
        for v in [v for v in ct.get("ventures",[]) if not v.get("_hidden")]:
            if y == top: y = self._col_section(c, ML, y, lw, "Ventures & Advisory")
            c.setFont("Poppins-SemiBold", 9.5); c.setFillColor(INK)
            c.drawString(ML, y, self.s(v.get("name","")))
            per = self.s(v.get("period",""))
            if per:
                c.setFont("SourceCodePro-Regular", 6.5); c.setFillColor(LIGHT)
                c.drawRightString(ML+lw, y+1, per)
            y -= 12
            desc = self.s(v.get("description",""))
            if desc:
                st = self.make_style("vd", "Poppins-Regular", 7, SLATE, leading=9.8)
                h = self.draw_wrapped(c, desc, st, ML, y, lw); y -= h
            y -= 14

        edu = ct.get("education",[])
        if edu:
            y -= 4; y = self._col_section(c, ML, y, lw, "Education")
            for e in edu:
                c.setFont("Poppins-SemiBold", 9.5); c.setFillColor(INK)
                c.drawString(ML, y, self.s(e.get("school","")))
                per = self.s(e.get("period",""))
                if per:
                    c.setFont("SourceCodePro-Regular", 6.5); c.setFillColor(LIGHT)
                    c.drawRightString(ML+lw, y+1, per)
                y -= 13
                deg = self.s(e.get("degree",""))
                if deg:
                    c.setFont("Poppins-Regular", 7.5); c.setFillColor(SLATE)
                    c.drawString(ML, y, deg)
                    y -= 11
                details = e.get("details", [])
                if isinstance(details, str):
                    details = [x.strip() for x in details.split(";") if x.strip()]
                for d in details:
                    st = self.make_style("ed", "Poppins-Regular", 6.5, DIM, leading=9)
                    h = self.draw_wrapped(c, d, st, ML+6, y, lw-6); y -= h + 2
                y -= 8

        projects = ct.get("projects",[])
        if projects:
            y -= 4; y = self._col_section(c, ML, y, lw, "Other Projects")
            for proj in projects:
                name = self.s(proj.get("name",""))
                url = proj.get("url","")
                c.setFont("Poppins-SemiBold", 8); c.setFillColor(INK)
                c.drawString(ML, y, name)
                if url:
                    c.setFont("Poppins-Regular", 6); c.setFillColor(LIGHT)
                    c.drawString(ML + c.stringWidth(name, "Poppins-SemiBold", 8) + 6, y + 0.5, url)
                y -= 10
                desc = self.s(proj.get("description",""))
                if desc:
                    st = self.make_style("pd", "Poppins-Regular", 6.5, DIM, leading=9)
                    h = self.draw_wrapped(c, desc, st, ML, y, lw); y -= h + 12
                else:
                    y -= 10

        notable = ct.get("notable",[])
        if notable:
            y -= 4; y = self._col_section(c, ML, y, lw, "Beyond Work")
            for item in notable:
                c.setFillColor(RUST); c.setFont("Poppins-Regular", 4)
                c.drawString(ML, y-1.5, "\u25c6")
                st = self.make_style("n", "Poppins-Regular", 7.3, SLATE, leading=10)
                h = self.draw_wrapped(c, item, st, ML+14, y, lw-14); y -= h + 5

        # Right column
        y = top
        speaking = ct.get("speaking",[])
        if speaking:
            y = self._col_section(c, rx, y, rw, "Speaking & Thought Leadership")
            for s in speaking:
                title = self.s(s.get("title","") if isinstance(s, dict) else str(s))
                yr = str(s.get("year","")) if isinstance(s, dict) else ""
                c.setFillColor(RUST); c.setFont("Poppins-Medium", 7)
                c.drawString(rx, y, "\u203a")
                st = self.make_style("sp", "Poppins-Regular", 7, SLATE, leading=9.5)
                h = self.draw_wrapped(c, title, st, rx+10, y, rw-10)
                if yr:
                    c.setFont("SourceCodePro-Regular", 6.5); c.setFillColor(LIGHT)
                    c.drawRightString(rx+rw, y, yr)
                y -= h + 5
            y -= 6

        skills = ct.get("skills",{})
        groups = [g for g in (skills.get("groups",[]) if isinstance(skills, dict) else []) if not g.get("_hidden")]
        if groups:
            y = self._col_section(c, rx, y, rw, "Expertise")
            for g in groups:
                c.setFont("Poppins-Medium", 7.5); c.setFillColor(CHARCOAL)
                c.drawString(rx, y, self.s(g.get("name",""))); y -= 12
                items = " \u00b7 ".join(self.s(i) for i in g.get("items",[]))
                st = self.make_style("sk", "Poppins-Regular", 6.5, DIM, leading=9.5)
                h = self.draw_wrapped(c, items, st, rx, y, rw); y -= h + 10

        self._footer(c, ct, self._pg)

    # ── HTML ─────────────────────────────────────────────────────────

    def render_html(self, content: dict, output_path: str) -> str:
        ct = self.prep(content)
        meta = ct.get("meta",{})
        name = self.h(meta.get("name",""))
        tagline = self.h(meta.get("tagline",""))
        contact = " &middot; ".join(self.h(meta.get(k,"")) for k in ("location","email","web","linkedin") if meta.get(k))
        summary = ct.get("summary","")
        if isinstance(summary, dict): summary = summary.get("default","")

        html = self.html_head(
            f"{name} - CV",
            EMBER_CSS,
            "https://fonts.googleapis.com/css2?family=DM+Serif+Text&family=Poppins:wght@300;400;500;600;700&family=Source+Code+Pro&display=swap"
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
  <section class="summary"><h2>Summary</h2><p>{self.h(summary)}</p></section>
  <section class="metrics">{self.html_metrics(ct.get("metrics",[])[:4])}</section>
  <section class="experience"><h2>Experience</h2>{self.html_experience(ct.get("experience",[]))}</section>
</div>
<div class="page page-2">
  <div class="accent-bar thin"></div>
  <div class="two-col">
    <div class="col-left">
      <section class="ventures"><h2>Ventures &amp; Advisory</h2>{self.html_ventures(ct.get("ventures",[]))}</section>
      <section class="education"><h2>Education</h2>{self.html_education(ct.get("education",[]))}</section>
      <section class="projects"><h2>Other Projects</h2>{self.html_projects(ct.get("projects",[]))}</section>
      <section class="notable"><h2>Beyond Work</h2>{self.html_notable(ct.get("notable",[]))}</section>
    </div>
    <div class="col-right">
      <section class="speaking"><h2>Speaking &amp; Thought Leadership</h2>{self.html_speaking(ct.get("speaking",[]))}</section>
      <section class="skills"><h2>Expertise</h2>{self.html_skills(ct.get("skills",{}))}</section>
    </div>
  </div>
  <footer><p>{name} &middot; {self.h(meta.get("email",""))}</p></footer>
</div>
</body></html>"""
        return self._write_html(html, output_path)


EMBER_CSS = """
:root {
  --ink: #1C1C28; --charcoal: #2A2A3E; --slate: #3A3A50;
  --rust: #B8522A; --gold: #C8872A; --dim: #7A7A8A;
  --light: #A0A0AE; --cream: #FEFBF5; --rule: #E0DDD5;
}
@page { size: A4; margin: 0; }
body { background: #e8e5de; font-family: 'Poppins', sans-serif; color: var(--slate); line-height: 1.5; }
.page { background: var(--cream); max-width: 210mm; margin: 0 auto; padding: 0; position: relative; }
.page-1 { min-height: 297mm; }
.page-2 { min-height: 297mm; padding: 32px 0; }
.accent-bar { height: 3px; background: var(--rust); }
.accent-bar.thin { height: 2px; }
header { background: var(--ink); padding: 36px 68px 28px 68px; }
header h1 { font-family: 'DM Serif Text', serif; font-size: 34px; color: #fff; font-weight: 400; margin-bottom: 4px; letter-spacing: -0.3px; }
header .tagline { font-weight: 300; font-size: 13px; color: var(--gold); margin-bottom: 6px; }
header .contact { font-family: 'Source Code Pro', monospace; font-size: 10px; color: var(--light); }
h2 { font-family: 'DM Serif Text', serif; font-size: 14px; color: var(--rust); font-weight: 400;
     border-bottom: 1px solid var(--rule); padding-bottom: 6px; margin-bottom: 16px; }
section { padding: 20px 68px 0; }
.summary p { font-size: 11px; line-height: 1.65; color: var(--slate); }
.metrics-row { display: flex; border-top: 1px solid var(--rule); border-bottom: 1px solid var(--rule); padding: 14px 0; }
.metric { flex: 1; text-align: center; border-right: 1px solid var(--rule); }
.metric:last-child { border-right: none; }
.metric-value { display: block; font-weight: 600; font-size: 18px; color: var(--ink); }
.metric-label { display: block; font-size: 9px; color: var(--dim); text-transform: uppercase; letter-spacing: 0.5px; margin-top: 2px; }
.exp-entry { margin-bottom: 16px; }
.exp-header { display: flex; justify-content: space-between; align-items: baseline; }
.company { font-weight: 600; font-size: 12px; color: var(--ink); }
.company-location { font-weight: 400; font-size: 10px; color: var(--dim); }
.company-years { font-weight: 500; font-size: 11px; color: var(--charcoal); }
.period { font-family: 'Source Code Pro', monospace; font-size: 9px; color: var(--light); }
.subtitle { font-size: 9.5px; color: var(--dim); margin: 1px 0 4px; }
.role { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 2px; }
.role-title { font-weight: 500; font-size: 11px; color: var(--charcoal); }
.role-location { font-weight: 400; color: var(--dim); }
.role-period { font-family: 'Source Code Pro', monospace; font-size: 9px; color: var(--light); }
ul.bullets { list-style: none; padding: 4px 0 0 0; }
ul.bullets li { font-size: 10px; line-height: 1.55; color: var(--slate); padding: 2px 0 2px 14px; position: relative; }
ul.bullets li::before { content: '\\2022'; color: var(--rust); position: absolute; left: 0; font-size: 10px; }
.two-col { display: grid; grid-template-columns: 56% 1fr; gap: 28px; padding: 0 68px; }
.col-left section, .col-right section { padding: 0; margin-bottom: 20px; }
.venture, .edu-entry { margin-bottom: 16px; }
.venture-header { display: flex; justify-content: space-between; align-items: baseline; }
.venture p, .edu-detail { font-size: 9.5px; color: var(--slate); line-height: 1.5; margin-top: 2px; }
.edu-school { display: block; font-weight: 600; font-size: 12px; color: var(--ink); margin-bottom: 2px; }
.edu-degree-row { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
.edu-degree-row .degree { flex: 1; min-width: 0; }
.edu-degree-row .period { flex-shrink: 0; white-space: nowrap; }
.degree { font-size: 10px; color: var(--slate); margin-top: 1px; }
.notable-item { font-size: 10px; line-height: 1.5; padding-left: 16px; position: relative; margin-bottom: 4px; }
.notable-item::before { content: '\\25c6'; color: var(--rust); position: absolute; left: 0; font-size: 6px; top: 3px; }
.project { margin-bottom: 14px; }
.project strong, .project-link { font-size: 10px; color: var(--ink); font-weight: 600; }
.project-link { text-decoration: none; border-bottom: 1px solid var(--rule); }
.project-link:hover { color: var(--rust); border-color: var(--rust); }
.project p { font-size: 9px; color: var(--dim); line-height: 1.5; margin-top: 2px; }
.speak-entry { display: flex; justify-content: space-between; font-size: 9.5px; margin-bottom: 5px; }
.speak-title { color: var(--slate); padding-left: 12px; position: relative; }
.speak-title::before { content: '\\203a'; color: var(--rust); position: absolute; left: 0; font-weight: 500; }
.speak-year { font-family: 'Source Code Pro', monospace; font-size: 9px; color: var(--light); }
.skill-group { margin-bottom: 10px; }
.skill-group h4 { font-weight: 500; font-size: 10px; color: var(--charcoal); margin-bottom: 3px; }
.skill-group p { font-size: 9px; color: var(--dim); line-height: 1.5; }
footer { text-align: center; padding: 20px; }
footer p { font-family: 'Source Code Pro', monospace; font-size: 9px; color: var(--light); }
@media print {
  body { background: var(--cream); }
  .page { box-shadow: none; margin: 0; max-width: none; }
  .page-2 { page-break-before: always; }
}
@media screen {
  .page { box-shadow: 0 1px 10px rgba(0,0,0,0.08); margin: 20px auto; }
}
"""
