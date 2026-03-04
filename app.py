"""CV Tailor — local web app.

Run with:  uvicorn app:app --reload --port 8080
Then open: http://localhost:8080
"""

import copy
import os
import ssl
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional

import certifi
import yaml
from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"
MASTER_PROFILE = DATA_DIR / "master_profile.yaml"
OUTPUT_DIR = DATA_DIR / "output"
SETTINGS_FILE = DATA_DIR / "settings.yaml"

DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)

# ── SSL context (fixes macOS certificate issues) ──────────────────────────────
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

# ── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(title="CV Tailor")


# ── Models ───────────────────────────────────────────────────────────────────
class TailorRequest(BaseModel):
    url: str = ""
    jd_text: str = ""
    role: str = ""
    company: str = ""
    emphasis: list[str] = []
    use_ai: bool = True
    rewrite: bool = False
    provider: str = "auto"  # "auto" | "anthropic" | "openai"


class ExportRequest(BaseModel):
    content: Optional[dict] = None  # None = use master
    template: str = "ember"
    filename: str = "cv"


class SettingsModel(BaseModel):
    anthropic_api_key: str = ""
    openai_api_key: str = ""


# ── Profile ───────────────────────────────────────────────────────────────────
@app.get("/api/profile")
def get_profile():
    if not MASTER_PROFILE.exists():
        return _empty_profile()
    with open(MASTER_PROFILE) as f:
        data = yaml.safe_load(f) or {}
    return data


@app.put("/api/profile")
def save_profile(data: dict = Body(...)):
    # Remove private/internal keys before saving
    data.pop("_target", None)
    data.pop("_raw_import", None)
    with open(MASTER_PROFILE, "w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
    return {"status": "saved"}


# ── Templates ─────────────────────────────────────────────────────────────────
@app.get("/api/templates")
def list_templates_endpoint():
    from engine.templates import list_templates
    return [{"name": n, "description": d} for n, d in list_templates()]


# ── Settings ─────────────────────────────────────────────────────────────────
@app.get("/api/settings")
def get_settings():
    s = _load_settings()
    ant = s.get("anthropic_api_key", "")
    oai = s.get("openai_api_key", "")
    return {
        "anthropic_api_key_set": bool(ant),
        "anthropic_api_key_preview": f"{ant[:8]}…{ant[-4:]}" if len(ant) > 12 else ("set" if ant else ""),
        "openai_api_key_set": bool(oai),
        "openai_api_key_preview": f"{oai[:8]}…{oai[-4:]}" if len(oai) > 12 else ("set" if oai else ""),
    }


@app.put("/api/settings")
def save_settings(data: SettingsModel):
    settings = _load_settings()
    if data.anthropic_api_key:
        settings["anthropic_api_key"] = data.anthropic_api_key
        os.environ["ANTHROPIC_API_KEY"] = data.anthropic_api_key
    if data.openai_api_key:
        settings["openai_api_key"] = data.openai_api_key
        os.environ["OPENAI_API_KEY"] = data.openai_api_key
    with open(SETTINGS_FILE, "w") as f:
        yaml.dump(settings, f, allow_unicode=True)
    return {"status": "saved"}


def _load_settings() -> dict:
    if not SETTINGS_FILE.exists():
        return {}
    with open(SETTINGS_FILE) as f:
        return yaml.safe_load(f) or {}


def _apply_settings():
    """Load saved API keys into environment on startup."""
    s = _load_settings()
    ant = s.get("anthropic_api_key", "")
    oai = s.get("openai_api_key", "")
    if ant and not os.environ.get("ANTHROPIC_API_KEY"):
        os.environ["ANTHROPIC_API_KEY"] = ant
    if oai and not os.environ.get("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = oai


# Apply on import so the key is available before any request
_apply_settings()


# ── Tailor ────────────────────────────────────────────────────────────────────
@app.post("/api/tailor")
def tailor_cv(req: TailorRequest):
    if not MASTER_PROFILE.exists():
        raise HTTPException(400, "No master profile found. Go to Edit and save your CV first.")

    jd_text = req.jd_text
    url_warning = None

    if req.url:
        try:
            jd_text = _fetch_url_text(req.url)
        except Exception as e:
            # Don't hard-fail — warn and continue with keywords/JD text only
            url_warning = f"Could not fetch URL: {e}. Tailoring with keywords only."

    target = {
        "role": req.role,
        "company": req.company,
        "emphasis": req.emphasis,
        "jd_text": jd_text,
    }

    with open(MASTER_PROFILE) as f:
        master = yaml.safe_load(f) or {}

    errors = []
    if url_warning:
        errors.append(url_warning)

    try:
        from engine.tailor import tailor
        tailored, tailor_errors = tailor(
            str(MASTER_PROFILE), target,
            ai=req.use_ai, rewrite=req.rewrite, provider=req.provider,
        )
        errors.extend(tailor_errors)
    except Exception as e:
        raise HTTPException(500, f"Tailoring failed: {e}")

    diff = _compute_diff(master, tailored)
    fit, fit_errors = _analyze_fit(master, jd_text, req.emphasis, req.role, req.company, req.provider)
    errors.extend(fit_errors)

    return {
        "tailored": tailored,
        "diff": diff,
        "fit": fit,
        "jd_preview": jd_text[:500] if jd_text else "",
        "errors": errors,
    }


# ── Export ────────────────────────────────────────────────────────────────────
@app.post("/api/export/pdf")
def export_pdf(req: ExportRequest):
    if req.content is None:
        if not MASTER_PROFILE.exists():
            raise HTTPException(400, "No profile found.")
        with open(MASTER_PROFILE) as f:
            content = yaml.safe_load(f) or {}
    else:
        content = req.content

    safe_name = req.filename.replace(" ", "_").replace("/", "_")
    out_path = str(OUTPUT_DIR / f"{safe_name}.pdf")

    from engine.layout import render
    render(content, out_path, req.template)

    return FileResponse(out_path, media_type="application/pdf", filename=f"{safe_name}.pdf")


@app.post("/api/export/html")
def export_html_preview(req: ExportRequest):
    if req.content is None:
        if not MASTER_PROFILE.exists():
            raise HTTPException(400, "No profile found.")
        with open(MASTER_PROFILE) as f:
            content = yaml.safe_load(f) or {}
    else:
        content = req.content

    safe_name = req.filename.replace(" ", "_").replace("/", "_")
    out_path = str(OUTPUT_DIR / f"{safe_name}_preview.html")

    from engine.layout import render_html
    render_html(content, out_path, req.template)

    with open(out_path) as f:
        return {"html": f.read()}


# ── Helpers ───────────────────────────────────────────────────────────────────
class _TextExtractor(HTMLParser):
    """Minimal HTML → text converter."""
    def __init__(self):
        super().__init__()
        self.texts = []
        self._skip = False
        self._skip_tags = {"script", "style", "nav", "footer", "header", "noscript"}

    def handle_starttag(self, tag, attrs):
        if tag in self._skip_tags:
            self._skip = True

    def handle_endtag(self, tag):
        if tag in self._skip_tags:
            self._skip = False

    def handle_data(self, data):
        if not self._skip and data.strip():
            self.texts.append(data.strip())


def _fetch_url_text(url: str) -> str:
    import httpx
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
    }
    with httpx.Client(follow_redirects=True, timeout=15, verify=certifi.where()) as client:
        resp = client.get(url, headers=headers)
        resp.raise_for_status()
        html = resp.text
    extractor = _TextExtractor()
    extractor.feed(html)
    text = " ".join(extractor.texts)
    return text[:10000]


def _analyze_fit(profile: dict, jd_text: str, emphasis: list, role: str, company: str,
                 provider: str = "auto") -> tuple[dict, list[str]]:
    """AI-powered fit analysis. Returns (result, errors)."""
    errors = []

    if jd_text or role:
        use_anthropic = provider in ("auto", "anthropic") and os.environ.get("ANTHROPIC_API_KEY")
        use_openai    = provider in ("auto", "openai")    and os.environ.get("OPENAI_API_KEY")

        if use_anthropic:
            try:
                return _ai_fit_analysis(profile, jd_text, emphasis, role, company), errors
            except Exception as e:
                if provider == "anthropic":
                    errors.append(f"Anthropic fit analysis failed: {e}")
                # auto mode: silently try next provider

        if use_openai:
            try:
                return _openai_fit_analysis(profile, jd_text, emphasis, role, company), errors
            except Exception as e:
                if provider == "openai":
                    errors.append(f"OpenAI fit analysis failed: {e}")
                # auto mode: silently fall through to deterministic

    return _deterministic_fit_analysis(profile, jd_text, emphasis, role, company), errors


def _ai_fit_analysis(profile: dict, jd_text: str, emphasis: list, role: str, company: str) -> dict:
    """Use Claude to produce a structured fit analysis."""
    import anthropic
    import json

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # Build a compact CV summary for the prompt
    meta = profile.get("meta", {})
    summary = profile.get("summary", "")
    if isinstance(summary, dict):
        summary = summary.get("default", "")

    exp_lines = []
    for entry in profile.get("experience", [])[:6]:
        company_name = entry.get("company", "")
        roles = [r.get("title", "") for r in entry.get("roles", [])]
        bullets = [b.get("text", "") if isinstance(b, dict) else str(b)
                   for b in entry.get("bullets", [])[:3]]
        exp_lines.append(f"- {company_name} | {', '.join(roles)}")
        for b in bullets:
            exp_lines.append(f"  · {b}")

    skills_lines = []
    skills = profile.get("skills", {})
    for g in (skills.get("groups", []) if isinstance(skills, dict) else [])[:4]:
        items = ", ".join(g.get("items", [])[:6])
        skills_lines.append(f"- {g.get('name', '')}: {items}")

    cv_digest = f"""Name/Role: {meta.get('name', '')} — {meta.get('tagline', '')}
Summary: {summary[:400]}
Experience:
{chr(10).join(exp_lines)}
Skills:
{chr(10).join(skills_lines)}"""

    target_desc = f"Role: {role}\nCompany: {company}"
    if emphasis:
        target_desc += f"\nEmphasis: {', '.join(emphasis)}"
    if jd_text:
        target_desc += f"\n\nJob Description:\n{jd_text[:3000]}"

    prompt = f"""You are an expert CV reviewer and recruiter. Analyse how well this CV fits the target role.

TARGET:
{target_desc}

CANDIDATE CV DIGEST:
{cv_digest}

Return ONLY a JSON object (no markdown, no explanation) with exactly this structure:
{{
  "fit_score": <integer 0-100>,
  "fit_label": <"Excellent Match"|"Strong Match"|"Good Match"|"Partial Match"|"Weak Match">,
  "fit_summary": "<2-3 sentences: what makes them a match or not, be specific and honest>",
  "key_points": [
    "<specific point to hit on the CV or in the application — actionable, e.g. 'Lead with the €X pipeline impact at Company Y'>",
    ...
  ],
  "strengths": [
    "<specific strength from the CV that fits this role>",
    ...
  ],
  "gaps": [
    "<specific requirement from the JD that is absent or weak in the CV>",
    ...
  ],
  "suggestions": [
    "<concrete, specific edit to the CV — e.g. 'Add Salesforce to your skills section' or 'Quantify team size in the Acme role'>",
    ...
  ],
  "recommendations": [
    {{
      "section": "<one of: summary|experience|metrics|skills|speaking|ventures|education>",
      "location": "<specific location e.g. 'Aiven experience' or 'Profile summary' or 'Skills — Technical'>",
      "suggestion": "<one actionable sentence: exactly what to add or change and why it helps for this role>",
      "draft": "<optional: a concrete example sentence or phrase they could paste in — leave empty string if not applicable>"
    }},
    ...
  ]
}}

Rules:
- key_points: 3-5 items, each is a SPECIFIC action tied to the JD (not generic advice)
- strengths: 3-5 items grounded in the actual CV content
- gaps: 2-4 honest gaps; if genuinely few, say so
- suggestions: 3-5 concrete edits, section-specific where possible
- recommendations: 3-5 items — these are PROACTIVE CV edits directly addressing the gaps above.
  Each must name the exact section and location, give a one-sentence action, and optionally a draft phrase.
  These should be more specific than suggestions — tied to the actual CV content.
- fit_score: be realistic — a 90+ means near-perfect, 50-70 is a real candidate with gaps"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1200,
        messages=[{"role": "user", "content": prompt}],
    )

    text = message.content[0].text.strip()
    # Strip markdown fences if present
    if text.startswith("```"):
        text = "\n".join(l for l in text.split("\n") if not l.startswith("```"))

    result = json.loads(text)

    # Validate and coerce required keys
    result.setdefault("fit_score", 50)
    result.setdefault("fit_label", "Partial Match")
    result.setdefault("fit_summary", "")
    result.setdefault("key_points", [])
    result.setdefault("strengths", [])
    result.setdefault("gaps", [])
    result.setdefault("suggestions", [])
    result.setdefault("recommendations", [])
    result["fit_score"] = max(0, min(100, int(result["fit_score"])))
    return result


def _openai_fit_analysis(profile: dict, jd_text: str, emphasis: list, role: str, company: str) -> dict:
    """Use OpenAI gpt-4o-mini to produce a structured fit analysis."""
    import json
    from openai import OpenAI

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    # Reuse the same CV digest logic
    meta = profile.get("meta", {})
    summary = profile.get("summary", "")
    if isinstance(summary, dict):
        summary = summary.get("default", "")

    exp_lines = []
    for entry in profile.get("experience", [])[:6]:
        roles = [r.get("title", "") for r in entry.get("roles", [])]
        bullets = [b.get("text", "") if isinstance(b, dict) else str(b)
                   for b in entry.get("bullets", [])[:3]]
        exp_lines.append(f"- {entry.get('company', '')} | {', '.join(roles)}")
        for b in bullets:
            exp_lines.append(f"  · {b}")

    skills_lines = []
    skills = profile.get("skills", {})
    for g in (skills.get("groups", []) if isinstance(skills, dict) else [])[:4]:
        skills_lines.append(f"- {g.get('name', '')}: {', '.join(g.get('items', [])[:6])}")

    cv_digest = f"""Name/Role: {meta.get('name', '')} — {meta.get('tagline', '')}
Summary: {summary[:400]}
Experience:
{chr(10).join(exp_lines)}
Skills:
{chr(10).join(skills_lines)}"""

    target_desc = f"Role: {role}\nCompany: {company}"
    if emphasis:
        target_desc += f"\nEmphasis: {', '.join(emphasis)}"
    if jd_text:
        target_desc += f"\n\nJob Description:\n{jd_text[:3000]}"

    system_msg = (
        "You are an expert CV reviewer and recruiter. "
        "Return only a JSON object — no markdown, no explanation."
    )
    user_msg = f"""Analyse how well this CV fits the target role.

TARGET:
{target_desc}

CANDIDATE CV DIGEST:
{cv_digest}

Return a JSON object with exactly this structure:
{{
  "fit_score": <integer 0-100>,
  "fit_label": <"Excellent Match"|"Strong Match"|"Good Match"|"Partial Match"|"Weak Match">,
  "fit_summary": "<2-3 sentences: specific and honest>",
  "key_points": ["<specific action tied to the JD>", ...],
  "strengths": ["<specific strength from the CV>", ...],
  "gaps": ["<specific gap between JD and CV>", ...],
  "suggestions": ["<concrete CV edit>", ...],
  "recommendations": [
    {{
      "section": "<summary|experience|metrics|skills|speaking|ventures|education>",
      "location": "<e.g. 'Aiven experience' or 'Profile summary'>",
      "suggestion": "<one actionable sentence: exactly what to add or change>",
      "draft": "<example phrase they could paste in, or empty string>"
    }}
  ]
}}

Rules: key_points 3-5, strengths 3-5, gaps 2-4, suggestions 3-5, recommendations 3-5. Be specific and tie recommendations to actual CV sections."""

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=1000,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
    )

    result = json.loads(resp.choices[0].message.content)
    result.setdefault("fit_score", 50)
    result.setdefault("fit_label", "Partial Match")
    result.setdefault("fit_summary", "")
    result.setdefault("key_points", [])
    result.setdefault("strengths", [])
    result.setdefault("gaps", [])
    result.setdefault("suggestions", [])
    result.setdefault("recommendations", [])
    result["fit_score"] = max(0, min(100, int(result["fit_score"])))
    return result


def _deterministic_fit_analysis(profile: dict, jd_text: str, emphasis: list, role: str, company: str) -> dict:
    """Keyword-based fallback fit analysis when no AI key is available."""
    import re
    from collections import Counter

    # Build a text blob from the CV
    cv_text_parts = []
    summary = profile.get("summary", "")
    if isinstance(summary, dict):
        summary = summary.get("default", "")
    cv_text_parts.append(summary)

    for entry in profile.get("experience", []):
        cv_text_parts.append(entry.get("company", ""))
        for r in entry.get("roles", []):
            cv_text_parts.append(r.get("title", ""))
        for b in entry.get("bullets", []):
            cv_text_parts.append(b.get("text", "") if isinstance(b, dict) else str(b))

    skills = profile.get("skills", {})
    for g in (skills.get("groups", []) if isinstance(skills, dict) else []):
        cv_text_parts.extend(g.get("items", []))

    cv_text = " ".join(cv_text_parts).lower()

    # Extract meaningful JD keywords
    stopwords = {
        "the", "and", "for", "with", "you", "our", "that", "this", "are",
        "will", "have", "from", "your", "about", "who", "can", "all", "not",
        "they", "was", "been", "more", "role", "work", "team", "help", "able",
        "make", "well", "good", "must", "should", "would", "their", "also",
        "into", "over", "both", "each", "some", "what", "when", "which",
    }
    jd_words = re.findall(r"[a-zA-Z]{4,}", (jd_text or "").lower())
    freq = Counter(w for w in jd_words if w not in stopwords)
    jd_keywords = [w for w, c in freq.most_common(20) if c >= 2]

    # Emphasis keywords always count as JD keywords
    emphasis_words = [e.lower().strip() for e in emphasis if e.strip()]
    for ew in emphasis_words:
        if ew not in jd_keywords:
            jd_keywords.insert(0, ew)

    # Score: fraction of JD keywords present in CV
    if jd_keywords:
        matched = [kw for kw in jd_keywords if kw in cv_text]
        score = int(len(matched) / len(jd_keywords) * 100)
    else:
        score = 50
        matched = []

    unmatched = [kw for kw in jd_keywords if kw not in cv_text]

    if score >= 80:
        label = "Excellent Match"
    elif score >= 65:
        label = "Strong Match"
    elif score >= 50:
        label = "Good Match"
    elif score >= 35:
        label = "Partial Match"
    else:
        label = "Weak Match"

    key_points = []
    if role:
        key_points.append(f"Position yourself explicitly for the {role} role in your summary.")
    if emphasis:
        key_points.append(f"Make sure '{emphasis[0]}' is prominent in your experience bullets.")
    if unmatched:
        key_points.append(f"Address missing keywords: {', '.join(unmatched[:3])}.")
    if company:
        key_points.append(f"Mirror {company}'s language and values in your summary.")

    strengths = [f"CV matches {len(matched)} of {len(jd_keywords)} key JD terms"] if matched else []
    if matched:
        strengths += [f"Strong alignment on: {', '.join(matched[:4])}"]

    gaps = [f"Not found in CV: {kw}" for kw in unmatched[:4]]

    suggestions = []
    if unmatched:
        suggestions.append(f"Add missing terms to relevant bullets: {', '.join(unmatched[:3])}.")
    if role:
        suggestions.append(f"Tailor your summary opening to name the {role} role specifically.")
    if company:
        suggestions.append(f"Research {company}'s recent news and reflect their priorities.")
    suggestions.append("Quantify every achievement with a specific metric if not already done.")

    return {
        "fit_score": score,
        "fit_label": label,
        "fit_summary": f"Keyword analysis found {len(matched)} of {len(jd_keywords)} JD terms in your CV. Enable AI tailoring for a deeper semantic assessment.",
        "key_points": key_points,
        "strengths": strengths,
        "gaps": gaps,
        "suggestions": suggestions,
        "recommendations": [],
    }


def _compute_diff(master: dict, tailored: dict) -> list:
    """Return a human-readable list of changes between master and tailored."""
    changes = []

    # ── Summary ──
    master_sum = master.get("summary", {})
    master_sum_text = master_sum.get("default", "") if isinstance(master_sum, dict) else str(master_sum)
    tailored_sum = tailored.get("summary", "")
    if master_sum_text.strip() != str(tailored_sum).strip():
        changes.append({
            "section": "summary",
            "label": "Profile Summary",
            "type": "modified",
            "original": master_sum_text,
            "tailored": str(tailored_sum),
        })

    # ── Metrics ──
    m_metrics = master.get("metrics", [])
    t_metrics = tailored.get("metrics", [])
    if m_metrics != t_metrics:
        removed = max(0, len(m_metrics) - len(t_metrics))
        changes.append({
            "section": "metrics",
            "label": "Key Metrics",
            "type": "trimmed",
            "removed_count": removed,
            "original_count": len(m_metrics),
            "tailored_count": len(t_metrics),
        })

    # ── Experience ──
    m_exp = master.get("experience", [])
    t_exp = tailored.get("experience", [])
    m_order = [e.get("company", "") for e in m_exp]
    t_order = [e.get("company", "") for e in t_exp]

    bullet_changes = []
    for t_entry in t_exp:
        company = t_entry.get("company", "")
        m_entry = next((e for e in m_exp if e.get("company") == company), None)
        if m_entry:
            m_bullets = [b.get("text", "") if isinstance(b, dict) else str(b) for b in m_entry.get("bullets", [])]
            t_bullets = [b.get("text", "") if isinstance(b, dict) else str(b) for b in t_entry.get("bullets", [])]
            removed = [b for b in m_bullets if b not in t_bullets]
            if removed:
                bullet_changes.append({
                    "company": company,
                    "removed": removed,
                    "kept": t_bullets,
                })

    if m_order != t_order or bullet_changes:
        changes.append({
            "section": "experience",
            "label": "Experience",
            "type": "reordered" if m_order != t_order else "trimmed",
            "order_changed": m_order != t_order,
            "original_order": m_order,
            "tailored_order": t_order,
            "bullet_changes": bullet_changes,
        })

    # ── Skills ──
    m_skills = master.get("skills", {})
    t_skills = tailored.get("skills", {})
    if isinstance(m_skills, dict) and isinstance(t_skills, dict):
        m_groups = [g.get("name", "") for g in m_skills.get("groups", [])]
        t_groups = [g.get("name", "") for g in t_skills.get("groups", [])]
        if m_groups != t_groups:
            changes.append({
                "section": "skills",
                "label": "Skills",
                "type": "reordered",
                "original_order": m_groups,
                "tailored_order": t_groups,
            })

    # ── Speaking ──
    m_speaking = master.get("speaking", [])
    t_speaking = tailored.get("speaking", [])
    if len(m_speaking) != len(t_speaking):
        changes.append({
            "section": "speaking",
            "label": "Speaking",
            "type": "trimmed",
            "removed_count": max(0, len(m_speaking) - len(t_speaking)),
            "original_count": len(m_speaking),
            "tailored_count": len(t_speaking),
        })

    return changes


def _empty_profile() -> dict:
    return {
        "meta": {
            "name": "",
            "tagline": "",
            "email": "",
            "phone": "",
            "web": "",
            "linkedin": "",
            "location": "",
        },
        "summary": {"default": "", "variants": {}},
        "metrics": [],
        "experience": [],
        "education": [],
        "skills": {"groups": []},
        "speaking": [],
        "ventures": [],
        "notable": [],
    }


# ── Static files (last — catches all remaining routes) ───────────────────────
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
