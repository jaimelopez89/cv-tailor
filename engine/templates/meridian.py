"""Meridian — Modern professional CV with sidebar layout.

Two-column: navy sidebar (contact, skills, education, languages)
+ white main area (summary, experience, ventures).
"""

import os
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas

from engine.templates.base import BaseTemplate

PAGE_W, PAGE_H = A4
MB = 14 * mm

NAVY    = HexColor("#1E293B")
NAVY_LT = HexColor("#334155")
CYAN    = HexColor("#0891B2")
SLATE_D = HexColor("#1E293B")
SLATE   = HexColor("#334155")
BODY    = HexColor("#475569")
DIM     = HexColor("#94A3B8")
LIGHT   = HexColor("#CBD5E1")
FAINT   = HexColor("#E2E8F0")
WHITE   = HexColor("#FFFFFF")
BG      = HexColor("#F8FAFC")

SIDEBAR_W = 170
MAIN_X = SIDEBAR_W + 24
MAIN_W = PAGE_W - MAIN_X - 22*mm


class MeridianTemplate(BaseTemplate):
    name = "meridian"
    description = "Modern professional - navy sidebar, clean layout"

    def render_pdf(self, content: dict, output_path: str) -> str:
        ct = self.prep(content)
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        c = Canvas(output_path, pagesize=A4)
        self._page1(c, ct)
        self._page2(c, ct)
        c.save()
        return output_path

    def _sidebar_bg(self, c):
        c.setFillColor(NAVY); c.rect(0, 0, SIDEBAR_W, PAGE_H, fill=1, stroke=0)

    def _main_bg(self, c):
        c.setFillColor(WHITE); c.rect(SIDEBAR_W, 0, PAGE_W-SIDEBAR_W, PAGE_H, fill=1, stroke=0)

    def _sidebar_section(self, c, y, title):
        y -= 6
        c.setFont("Poppins-SemiBold", 7.5); c.setFillColor(CYAN)
        c.drawString(20, y, self.s(title).upper())
        y -= 4
        c.setStrokeColor(NAVY_LT); c.setLineWidth(0.5)
        c.line(20, y, SIDEBAR_W-20, y)
        return y - 10

    def _main_section(self, c, y, title):
        y -= 10
        c.setFont("Poppins-SemiBold", 10); c.setFillColor(SLATE_D)
        c.drawString(MAIN_X, y, self.s(title))
        y -= 3
        c.setStrokeColor(CYAN); c.setLineWidth(1)
        c.line(MAIN_X, y, MAIN_X+32, y)
        c.setStrokeColor(FAINT); c.setLineWidth(0.4)
        c.line(MAIN_X+32, y, MAIN_X+MAIN_W, y)
        return y - 12

    def _page1(self, c, ct):
        self._sidebar_bg(c); self._main_bg(c)
        meta = ct.get("meta",{})

        # Sidebar: name + contact
        y = PAGE_H - 36
        c.setFont("Poppins-Bold", 14); c.setFillColor(WHITE)
        name = self.s(meta.get("name",""))
        # Wrap long names
        if len(name) > 16:
            parts = name.split(" ", 1)
            c.drawString(20, y, parts[0])
            if len(parts) > 1: y -= 18; c.drawString(20, y, parts[1])
        else:
            c.drawString(20, y, name)
        y -= 10
        tagline = self.s(meta.get("tagline",""))
        if tagline:
            c.setFont("Poppins-Light", 7); c.setFillColor(LIGHT)
            # Wrap tagline
            st = self.make_style("tg", "Poppins-Light", 7, LIGHT, leading=9.5)
            h = self.draw_wrapped(c, tagline, st, 20, y, SIDEBAR_W-40)
            y -= h + 8

        # Contact
        y = self._sidebar_section(c, y, "Contact")
        for k, icon in [("location","\u25cb"), ("email","\u2709"), ("web","\u25cb"), ("linkedin","\u25cb")]:
            v = self.s(meta.get(k,""))
            if not v: continue
            c.setFont("Poppins-Regular", 7); c.setFillColor(LIGHT)
            c.drawString(20, y, v)
            y -= 12

        # Skills in sidebar
        skills = ct.get("skills",{})
        groups = [g for g in (skills.get("groups",[]) if isinstance(skills, dict) else []) if not g.get("_hidden")]
        if groups:
            y -= 4; y = self._sidebar_section(c, y, "Expertise")
            for g in groups:
                c.setFont("Poppins-Medium", 7); c.setFillColor(CYAN)
                c.drawString(20, y, self.s(g.get("name",""))); y -= 11
                for item in g.get("items",[]):
                    c.setFont("Poppins-Regular", 6.5); c.setFillColor(LIGHT)
                    c.drawString(28, y, self.s(item)); y -= 10
                y -= 4

        # Education in sidebar
        edu = ct.get("education",[])
        if edu:
            from reportlab.pdfbase.pdfmetrics import stringWidth
            from reportlab.lib.utils import simpleSplit
            sw = SIDEBAR_W - 40
            y -= 4; y = self._sidebar_section(c, y, "Education")
            for ei, e in enumerate(edu):
                # School name - manual line wrapping
                school = self.s(e.get("school",""))
                c.setFont("Poppins-Medium", 7); c.setFillColor(WHITE)
                lines = simpleSplit(school, "Poppins-Medium", 7, sw)
                for line in lines:
                    c.drawString(20, y, line); y -= 10
                y -= 2
                # Degree
                deg = self.s(e.get("degree",""))
                if deg:
                    c.setFont("Poppins-Regular", 6.5); c.setFillColor(LIGHT)
                    lines = simpleSplit(deg, "Poppins-Regular", 6.5, sw)
                    for line in lines:
                        c.drawString(20, y, line); y -= 9
                    y -= 2
                # Period
                c.setFont("SourceCodePro-Regular", 6); c.setFillColor(DIM)
                c.drawString(20, y, self.s(e.get("period","")))
                y -= 18

        # Notable in sidebar
        notable = ct.get("notable",[])
        if notable:
            y -= 4; y = self._sidebar_section(c, y, "Beyond Work")
            for item in notable:
                st = self.make_style("nt", "Poppins-Regular", 6.5, LIGHT, leading=9)
                h = self.draw_wrapped(c, item, st, 20, y, SIDEBAR_W-40); y -= h + 5

        # Main area: summary + experience
        y = PAGE_H - 36

        summary = ct.get("summary","")
        if isinstance(summary, dict): summary = summary.get("default","")
        if summary:
            y = self._main_section(c, y, "Summary")
            st = self.make_style("sum", "Poppins-Regular", 8, BODY, leading=12.5)
            h = self.draw_wrapped(c, summary, st, MAIN_X, y, MAIN_W); y -= h + 6

        # Metrics
        metrics = ct.get("metrics",[])[:4]
        if metrics:
            y -= 4
            n = len(metrics); mw = MAIN_W/n
            for i, m in enumerate(metrics):
                mx = MAIN_X + mw*i
                c.setFont("Poppins-SemiBold", 16); c.setFillColor(CYAN)
                c.drawString(mx, y, self.s(m.get("value","")))
                c.setFont("Poppins-Regular", 6.5); c.setFillColor(DIM)
                c.drawString(mx, y-13, self.s(m.get("label","")).upper())
            y -= 28

        # Experience
        exp = [e for e in ct.get("experience",[]) if not e.get("_hidden")]
        if exp:
            y = self._main_section(c, y, "Experience")
            for i, entry in enumerate(exp):
                eh = self._measure_exp(entry)
                if y - eh < MB + 20:
                    c.showPage(); self._main_bg(c)
                    self._sidebar_bg(c)
                    y = PAGE_H - 24
                    y = self._main_section(c, y, "Experience (continued)")
                y = self._draw_exp(c, y, entry)
                if i < len(exp)-1: y -= 16

        # Footer
        c.setFont("SourceCodePro-Regular", 6); c.setFillColor(DIM)
        c.drawCentredString(MAIN_X+MAIN_W/2, MB-6, f"{self.s(meta.get('name',''))}  |  Page 1")

    def _draw_exp(self, c, y, entry):
        company = self.s(entry.get("company",""))
        location = self.s(entry.get("location",""))
        c.setFont("Poppins-SemiBold", 9.5); c.setFillColor(SLATE_D)
        company_str = company
        if location:
            company_str += f"  \u00b7  {location}"
        c.drawString(MAIN_X, y, company_str)
        roles = entry.get("roles",[])
        yr = self.year_range(roles)
        if yr:
            c.setFont("Poppins-Medium", 9); c.setFillColor(SLATE)
            c.drawRightString(MAIN_X+MAIN_W, y+1, yr)
        y -= 11
        sub = self.s(entry.get("subtitle",""))
        if sub:
            c.setFont("Poppins-Regular", 7); c.setFillColor(DIM)
            c.drawString(MAIN_X, y, sub); y -= 11
        for role in roles:
            rt = self.s(role.get("title",""))
            c.setFont("Poppins-Medium", 8.5); c.setFillColor(SLATE)
            c.drawString(MAIN_X, y, rt)
            c.setFont("SourceCodePro-Regular", 6.5); c.setFillColor(DIM)
            c.drawRightString(MAIN_X+MAIN_W, y+1, self.s(role.get("period","")))
            y -= 12
        y -= 1
        bst = self.make_style("mb", "Poppins-Regular", 7.5, BODY, leading=11)
        for b in entry.get("bullets",[]):
            txt = self.s(b.get("text","") if isinstance(b, dict) else str(b))
            if not txt: continue
            # Cyan dot in margin, text aligned with company/roles
            c.setFillColor(CYAN)
            c.circle(MAIN_X - 5, y - 7, 1.2, fill=1, stroke=0)
            h = self.draw_wrapped(c, txt, bst, MAIN_X, y, MAIN_W); y -= h + 2.5
        return y

    def _measure_exp(self, entry):
        h = 11 + (11 if entry.get("subtitle") else 0) + len(entry.get("roles",[]))*12 + 1
        bst = self.make_style("mm", "Poppins-Regular", 7.5, BODY, leading=11)
        for b in entry.get("bullets",[]):
            txt = b.get("text","") if isinstance(b, dict) else str(b)
            if txt: h += self.measure_text(txt, bst, MAIN_W) + 2.5
        return h

    def _page2(self, c, ct):
        has_p2 = (ct.get("ventures") or ct.get("projects") or ct.get("speaking"))
        if not has_p2:
            return
        c.showPage(); self._main_bg(c)
        self._sidebar_bg(c)
        # Ventures and speaking on page 2 main area
        y = PAGE_H - 24
        ventures = [v for v in ct.get("ventures",[]) if not v.get("_hidden")]
        if ventures:
            y = self._main_section(c, y, "Ventures & Advisory")
            for v in ventures:
                c.setFont("Poppins-SemiBold", 9); c.setFillColor(SLATE_D)
                c.drawString(MAIN_X, y, self.s(v.get("name","")))
                per = self.s(v.get("period",""))
                if per:
                    c.setFont("SourceCodePro-Regular", 6.5); c.setFillColor(DIM)
                    c.drawRightString(MAIN_X+MAIN_W, y+1, per)
                y -= 12
                desc = self.s(v.get("description",""))
                if desc:
                    st = self.make_style("vd", "Poppins-Regular", 7.5, BODY, leading=10.5)
                    h = self.draw_wrapped(c, desc, st, MAIN_X, y, MAIN_W); y -= h
                y -= 14

        projects = ct.get("projects",[])
        if projects:
            y -= 4; y = self._main_section(c, y, "Other Projects")
            for proj in projects:
                name = self.s(proj.get("name",""))
                url = proj.get("url","")
                c.setFont("Poppins-SemiBold", 8.5); c.setFillColor(SLATE_D)
                c.drawString(MAIN_X, y, name)
                if url:
                    c.setFont("Poppins-Regular", 6); c.setFillColor(DIM)
                    c.drawString(MAIN_X + c.stringWidth(name, "Poppins-SemiBold", 8.5) + 6, y + 0.5, url)
                y -= 11
                desc = self.s(proj.get("description",""))
                if desc:
                    st = self.make_style("pd", "Poppins-Regular", 7, BODY, leading=10.5)
                    h = self.draw_wrapped(c, desc, st, MAIN_X, y, MAIN_W); y -= h + 10
                else:
                    y -= 10

        speaking = ct.get("speaking",[])
        if speaking:
            y -= 4; y = self._main_section(c, y, "Speaking")
            for s in speaking:
                title = self.s(s.get("title","") if isinstance(s, dict) else str(s))
                yr = str(s.get("year","")) if isinstance(s, dict) else ""
                c.setFont("Poppins-Regular", 7.5); c.setFillColor(BODY)
                c.drawString(MAIN_X+8, y, title)
                if yr:
                    c.setFont("SourceCodePro-Regular", 6.5); c.setFillColor(DIM)
                    c.drawRightString(MAIN_X+MAIN_W, y, yr)
                y -= 12

        meta = ct.get("meta",{})
        c.setFont("SourceCodePro-Regular", 6); c.setFillColor(DIM)
        c.drawCentredString(MAIN_X+MAIN_W/2, MB-6, f"{self.s(meta.get('name',''))}  |  Page 2")

    # ── HTML ─────────────────────────────────────────────────────────

    def render_html(self, content: dict, output_path: str) -> str:
        ct = self.prep(content)
        meta = ct.get("meta",{})
        name = self.h(meta.get("name",""))
        tagline = self.h(meta.get("tagline",""))
        summary = ct.get("summary","")
        if isinstance(summary, dict): summary = summary.get("default","")

        contact_html = ""
        for k in ("location","email","web","linkedin"):
            v = self.h(meta.get(k,""))
            if v: contact_html += f'<p class="contact-item">{v}</p>\n'

        skills_html = ""
        skills = ct.get("skills",{})
        groups = [g for g in (skills.get("groups",[]) if isinstance(skills, dict) else []) if not g.get("_hidden")]
        for g in groups:
            gname = self.h(g.get("name",""))
            items = "".join(f"<li>{self.h(i)}</li>" for i in g.get("items",[]))
            skills_html += f'<div class="sidebar-group"><h4>{gname}</h4><ul>{items}</ul></div>\n'

        edu_html = ""
        for e in ct.get("education",[]):
            edu_html += f"""<div class="sidebar-edu">
<strong>{self.h(e.get("school",""))}</strong>
<p>{self.h(e.get("degree",""))}</p>
<span class="period">{self.h(e.get("period",""))}</span></div>\n"""

        notable_html = "".join(f'<p class="sidebar-notable">{self.h(n)}</p>' for n in ct.get("notable",[]))

        metrics_html = ""
        for m in ct.get("metrics",[])[:4]:
            metrics_html += f'<div class="metric"><span class="metric-value">{self.h(m.get("value",""))}</span><span class="metric-label">{self.h(m.get("label",""))}</span></div>\n'

        html = self.html_head(f"{name} - CV", MERIDIAN_CSS,
            "https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&family=Source+Code+Pro&display=swap")
        html += f"""
<body>
<div class="cv">
  <aside class="sidebar">
    <div class="sidebar-header"><h1>{name}</h1><p class="tagline">{tagline}</p></div>
    <div class="sidebar-section"><h3>Contact</h3>{contact_html}</div>
    <div class="sidebar-section"><h3>Expertise</h3>{skills_html}</div>
    <div class="sidebar-section"><h3>Education</h3>{edu_html}</div>
    <div class="sidebar-section"><h3>Beyond Work</h3>{notable_html}</div>
  </aside>
  <main>
    <section class="summary"><h2>Summary</h2><p>{self.h(summary)}</p></section>
    <section class="metrics"><div class="metrics-row">{metrics_html}</div></section>
    <section class="experience"><h2>Experience</h2>{self.html_experience(ct.get("experience",[]))}</section>
    <section class="ventures"><h2>Ventures &amp; Advisory</h2>{self.html_ventures(ct.get("ventures",[]))}</section>
    <section class="projects"><h2>Other Projects</h2>{self.html_projects(ct.get("projects",[]))}</section>
    <section class="speaking"><h2>Speaking</h2>{self.html_speaking(ct.get("speaking",[]))}</section>
  </main>
</div>
</body></html>"""
        return self._write_html(html, output_path)


MERIDIAN_CSS = """
:root {
  --navy: #1E293B; --cyan: #0891B2; --slate: #334155;
  --body: #475569; --dim: #94A3B8; --light: #CBD5E1; --faint: #E2E8F0; --bg: #F8FAFC;
}
@page { size: A4; margin: 0; }
body { background: #e2e8f0; font-family: 'Poppins', sans-serif; color: var(--body); margin: 0; }
.cv { display: grid; grid-template-columns: 220px 1fr; max-width: 210mm; margin: 0 auto; min-height: 297mm; }
.sidebar { background: var(--navy); color: var(--light); padding: 32px 22px; }
.sidebar-header h1 { font-size: 20px; font-weight: 700; color: #fff; line-height: 1.2; margin-bottom: 6px; }
.sidebar-header .tagline { font-weight: 300; font-size: 9px; color: var(--dim); line-height: 1.4; margin-bottom: 20px; }
.sidebar-section { margin-bottom: 20px; }
.sidebar-section h3 { font-size: 8px; font-weight: 600; color: var(--cyan); text-transform: uppercase;
  letter-spacing: 1.5px; margin-bottom: 8px; padding-bottom: 4px; border-bottom: 1px solid #334155; }
.contact-item { font-size: 9px; margin-bottom: 5px; color: var(--light); }
.sidebar-group { margin-bottom: 10px; }
.sidebar-group h4 { font-size: 9px; font-weight: 500; color: var(--cyan); margin-bottom: 3px; }
.sidebar-group ul { list-style: none; }
.sidebar-group li { font-size: 8.5px; color: var(--light); padding: 1px 0; }
.sidebar-edu { margin-bottom: 10px; }
.sidebar-edu strong { font-size: 9px; font-weight: 500; color: #fff; display: block; }
.sidebar-edu p { font-size: 8.5px; margin-top: 1px; }
.sidebar-edu .period { font-family: 'Source Code Pro', monospace; font-size: 8px; color: var(--dim); }
.sidebar-notable { font-size: 8.5px; line-height: 1.4; margin-bottom: 5px; }
main { background: #fff; padding: 32px 36px; }
main h2 { font-size: 12px; font-weight: 600; color: var(--slate); margin-bottom: 4px;
  padding-bottom: 6px; border-bottom: 2px solid var(--cyan); display: inline-block; }
main h2::after { content: ''; display: block; }
main section { margin-bottom: 22px; }
.summary p { font-size: 10.5px; line-height: 1.6; margin-top: 10px; }
.metrics-row { display: flex; gap: 16px; margin-top: 8px; }
.metric { flex: 1; }
.metric-value { display: block; font-size: 20px; font-weight: 600; color: var(--cyan); }
.metric-label { font-size: 8px; text-transform: uppercase; letter-spacing: 0.5px; color: var(--dim); }
.exp-entry { margin-bottom: 14px; margin-top: 10px; }
.exp-header { display: flex; justify-content: space-between; align-items: baseline; }
.company { font-size: 11px; font-weight: 600; color: var(--slate); }
.company-years { font-weight: 500; font-size: 11px; color: var(--slate); }
.period { font-family: 'Source Code Pro', monospace; font-size: 8.5px; color: var(--dim); }
.subtitle { font-size: 9px; color: var(--dim); margin: 1px 0 3px; }
.role { display: flex; justify-content: space-between; margin-bottom: 2px; }
.role-title { font-size: 10px; font-weight: 500; color: var(--slate); }
.role-period { font-family: 'Source Code Pro', monospace; font-size: 8.5px; color: var(--dim); }
ul.bullets { list-style: none; padding: 3px 0 0; }
ul.bullets li { font-size: 9.5px; line-height: 1.5; padding: 2px 0 2px 0; color: var(--body); }
.venture, .edu-entry { margin-bottom: 16px; }
.venture-header, .edu-header { display: flex; justify-content: space-between; align-items: baseline; }
.venture p { font-size: 9px; margin-top: 2px; }
.speak-entry { display: flex; justify-content: space-between; font-size: 9.5px; margin-bottom: 4px; }
.speak-year { font-family: 'Source Code Pro', monospace; font-size: 8.5px; color: var(--dim); }
.project { margin-bottom: 14px; }
.project strong, .project-link { font-size: 10px; color: var(--slate); font-weight: 600; }
.project-link { text-decoration: none; border-bottom: 1px solid var(--faint); }
.project-link:hover { color: var(--cyan); border-color: var(--cyan); }
.project p { font-size: 9px; color: var(--body); line-height: 1.5; margin-top: 2px; }
.company-location { font-weight: 400; font-size: 9px; color: var(--dim); }
@media print { body { background: #fff; } .cv { box-shadow: none; } }
@media screen { .cv { box-shadow: 0 1px 12px rgba(0,0,0,0.1); margin: 20px auto; } }
"""
