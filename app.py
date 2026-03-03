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


class ExportRequest(BaseModel):
    content: Optional[dict] = None  # None = use master
    template: str = "ember"
    filename: str = "cv"


class SettingsModel(BaseModel):
    anthropic_api_key: str = ""


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
    key = s.get("anthropic_api_key", "")
    return {
        "anthropic_api_key": key,
        "anthropic_api_key_set": bool(key),
        "anthropic_api_key_preview": f"{key[:8]}…{key[-4:]}" if len(key) > 12 else ("set" if key else ""),
    }


@app.put("/api/settings")
def save_settings(data: SettingsModel):
    settings = _load_settings()
    if data.anthropic_api_key:
        settings["anthropic_api_key"] = data.anthropic_api_key
        os.environ["ANTHROPIC_API_KEY"] = data.anthropic_api_key
    with open(SETTINGS_FILE, "w") as f:
        yaml.dump(settings, f, allow_unicode=True)
    return {"status": "saved"}


def _load_settings() -> dict:
    if not SETTINGS_FILE.exists():
        return {}
    with open(SETTINGS_FILE) as f:
        return yaml.safe_load(f) or {}


def _apply_settings():
    """Load saved API key into environment on startup."""
    s = _load_settings()
    key = s.get("anthropic_api_key", "")
    if key and not os.environ.get("ANTHROPIC_API_KEY"):
        os.environ["ANTHROPIC_API_KEY"] = key


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

    try:
        from engine.tailor import tailor
        tailored = tailor(str(MASTER_PROFILE), target, ai=req.use_ai, rewrite=req.rewrite)
    except Exception as e:
        raise HTTPException(500, f"Tailoring failed: {e}")

    diff = _compute_diff(master, tailored)

    return {
        "tailored": tailored,
        "diff": diff,
        "jd_preview": jd_text[:500] if jd_text else "",
        "url_warning": url_warning,
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
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15, context=SSL_CONTEXT) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    extractor = _TextExtractor()
    extractor.feed(html)
    text = " ".join(extractor.texts)
    return text[:10000]


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
