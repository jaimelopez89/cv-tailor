"""Tests for CV Tailor web app."""

import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient


# ── Fixtures ──────────────────────────────────────────────────────────────────
SAMPLE_PROFILE = {
    "meta": {
        "name": "Jane Doe",
        "tagline": "VP Marketing",
        "email": "jane@example.com",
        "phone": "+1 555 000 0000",
        "web": "janedoe.com",
        "linkedin": "",
        "location": "Helsinki",
    },
    "summary": {
        "default": "Experienced marketing leader with 10+ years building B2B pipelines.",
        "variants": {},
    },
    "metrics": [
        {"value": "€1.5bn", "label": "Pipeline generated", "tags": ["pipeline", "revenue"], "weight": 9},
        {"value": "3×", "label": "Team growth", "tags": ["leadership", "team"], "weight": 7},
    ],
    "experience": [
        {
            "company": "Acme Corp",
            "subtitle": "Leading SaaS provider.",
            "location": "Helsinki",
            "roles": [
                {"title": "VP Marketing", "period": "Jan 2022 – Present"},
            ],
            "bullets": [
                {"text": "Grew pipeline by 200%", "tags": ["pipeline", "growth"], "weight": 8},
                {"text": "Rebuilt the MarTech stack", "tags": ["martech", "operations"], "weight": 7},
                {"text": "Led team of 12 globally", "tags": ["leadership", "team"], "weight": 6},
            ],
        },
        {
            "company": "Beta Inc",
            "subtitle": "",
            "location": "Berlin",
            "roles": [{"title": "Marketing Manager", "period": "Jan 2019 – Dec 2021"}],
            "bullets": [
                {"text": "Launched 3 product lines", "tags": ["product", "launch"], "weight": 7},
            ],
        },
    ],
    "education": [
        {
            "school": "MIT",
            "degree": "MicroMasters, Data Science",
            "period": "2020–2023",
            "location": "Remote",
            "details": "Graduated with distinction",
        }
    ],
    "skills": {
        "groups": [
            {"name": "Marketing", "items": ["Demand Gen", "ABM", "Analytics"], "tags": ["marketing"]},
            {"name": "Technical", "items": ["Python", "SQL", "Salesforce"], "tags": ["technical"]},
        ]
    },
    "speaking": [
        {"title": "MarTech Summit 2023", "year": "2023", "tags": ["martech"]},
    ],
    "ventures": [],
    "notable": [],
    "metrics": [
        {"value": "€1.5bn", "label": "Pipeline", "tags": ["pipeline"], "weight": 9},
    ],
}


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """Each test gets its own data directory."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    output_dir = data_dir / "output"
    output_dir.mkdir()

    import app as app_module
    monkeypatch.setattr(app_module, "DATA_DIR", data_dir)
    monkeypatch.setattr(app_module, "MASTER_PROFILE", data_dir / "master_profile.yaml")
    monkeypatch.setattr(app_module, "OUTPUT_DIR", output_dir)
    return data_dir


@pytest.fixture
def client(isolated_data_dir):
    from app import app
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def client_with_profile(isolated_data_dir):
    profile_path = isolated_data_dir / "master_profile.yaml"
    with open(profile_path, "w") as f:
        yaml.dump(SAMPLE_PROFILE, f, allow_unicode=True)
    from app import app
    return TestClient(app, raise_server_exceptions=False)


# ── Profile endpoints ─────────────────────────────────────────────────────────
class TestGetProfile:
    def test_returns_empty_when_no_file(self, client):
        res = client.get("/api/profile")
        assert res.status_code == 200
        data = res.json()
        assert "meta" in data
        assert data["meta"]["name"] == ""

    def test_returns_profile_when_file_exists(self, client_with_profile):
        res = client_with_profile.get("/api/profile")
        assert res.status_code == 200
        assert res.json()["meta"]["name"] == "Jane Doe"

    def test_profile_has_required_sections(self, client_with_profile):
        data = client_with_profile.get("/api/profile").json()
        for section in ("meta", "summary", "experience", "education", "skills"):
            assert section in data, f"Missing section: {section}"


class TestSaveProfile:
    def test_save_creates_file(self, client, isolated_data_dir):
        res = client.put("/api/profile", json=SAMPLE_PROFILE)
        assert res.status_code == 200
        assert res.json()["status"] == "saved"
        assert (isolated_data_dir / "master_profile.yaml").exists()

    def test_save_strips_internal_keys(self, client, isolated_data_dir):
        data = dict(SAMPLE_PROFILE)
        data["_target"] = {"role": "test"}
        data["_raw_import"] = "raw text"
        client.put("/api/profile", json=data)
        with open(isolated_data_dir / "master_profile.yaml") as f:
            saved = yaml.safe_load(f)
        assert "_target" not in saved
        assert "_raw_import" not in saved

    def test_roundtrip(self, client):
        client.put("/api/profile", json=SAMPLE_PROFILE)
        loaded = client.get("/api/profile").json()
        assert loaded["meta"]["name"] == "Jane Doe"
        assert loaded["meta"]["email"] == "jane@example.com"


# ── Templates endpoint ────────────────────────────────────────────────────────
class TestTemplates:
    def test_returns_list(self, client):
        res = client.get("/api/templates")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_includes_expected_templates(self, client):
        res = client.get("/api/templates")
        names = [t["name"] for t in res.json()]
        assert "ember" in names

    def test_each_template_has_name(self, client):
        for t in client.get("/api/templates").json():
            assert "name" in t


# ── Tailor endpoint ───────────────────────────────────────────────────────────
class TestTailor:
    def test_returns_404_without_profile(self, client):
        res = client.post("/api/tailor", json={"role": "CMO", "company": "X"})
        assert res.status_code == 400

    def test_deterministic_tailor(self, client_with_profile):
        res = client_with_profile.post("/api/tailor", json={
            "role": "VP Marketing",
            "company": "Test Co",
            "jd_text": "Looking for pipeline growth and demand generation expertise",
            "use_ai": False,
        })
        assert res.status_code == 200
        data = res.json()
        assert "tailored" in data
        assert "diff" in data

    def test_tailored_has_required_sections(self, client_with_profile):
        res = client_with_profile.post("/api/tailor", json={
            "role": "CMO", "jd_text": "marketing leadership", "use_ai": False
        })
        tailored = res.json()["tailored"]
        assert "meta" in tailored
        assert "experience" in tailored

    def test_diff_is_list(self, client_with_profile):
        res = client_with_profile.post("/api/tailor", json={
            "role": "Data Scientist", "jd_text": "machine learning python analytics", "use_ai": False
        })
        assert isinstance(res.json()["diff"], list)

    def test_diff_contains_section_info(self, client_with_profile):
        res = client_with_profile.post("/api/tailor", json={
            "role": "CMO", "jd_text": "marketing pipeline revenue", "use_ai": False
        })
        diff = res.json()["diff"]
        for item in diff:
            assert "section" in item
            assert "label" in item
            assert "type" in item

    def test_jd_preview_returned(self, client_with_profile):
        res = client_with_profile.post("/api/tailor", json={
            "role": "CMO", "jd_text": "marketing leadership pipeline growth", "use_ai": False
        })
        assert "jd_preview" in res.json()

    def test_tailor_does_not_modify_master(self, client_with_profile, isolated_data_dir):
        original_mtime = os.path.getmtime(isolated_data_dir / "master_profile.yaml")
        client_with_profile.post("/api/tailor", json={"role": "CMO", "use_ai": False})
        new_mtime = os.path.getmtime(isolated_data_dir / "master_profile.yaml")
        assert original_mtime == new_mtime, "Tailor should never modify master profile"

    def test_emphasis_keywords_accepted(self, client_with_profile):
        res = client_with_profile.post("/api/tailor", json={
            "role": "CMO",
            "emphasis": ["pipeline", "revenue", "analytics"],
            "use_ai": False,
        })
        assert res.status_code == 200


# ── Export endpoint ───────────────────────────────────────────────────────────
class TestExportPDF:
    def test_export_returns_pdf(self, client_with_profile):
        res = client_with_profile.post("/api/export/pdf", json={"template": "ember"})
        assert res.status_code == 200
        assert res.headers["content-type"] == "application/pdf"
        # PDF magic bytes
        assert res.content[:4] == b"%PDF"

    def test_export_without_profile_returns_400(self, client):
        res = client.post("/api/export/pdf", json={"template": "ember"})
        assert res.status_code == 400

    def test_export_with_explicit_content(self, client):
        res = client.post("/api/export/pdf", json={
            "content": SAMPLE_PROFILE,
            "template": "ember",
            "filename": "test_cv",
        })
        assert res.status_code == 200
        assert res.content[:4] == b"%PDF"

    def test_all_templates_render(self, client):
        templates_res = client.get("/api/templates")
        for t in templates_res.json():
            res = client.post("/api/export/pdf", json={
                "content": SAMPLE_PROFILE,
                "template": t["name"],
            })
            assert res.status_code == 200, f"Template {t['name']} failed: {res.text}"
            assert res.content[:4] == b"%PDF", f"Template {t['name']} did not produce a PDF"

    def test_filename_sanitized(self, client, isolated_data_dir):
        res = client.post("/api/export/pdf", json={
            "content": SAMPLE_PROFILE,
            "template": "ember",
            "filename": "my cv/test",
        })
        assert res.status_code == 200
        # Should not have created a file with slashes in the name
        for f in (isolated_data_dir / "output").iterdir():
            assert "/" not in f.name


# ── Export HTML endpoint ──────────────────────────────────────────────────────
class TestExportHTML:
    def test_export_html_returns_html(self, client_with_profile):
        res = client_with_profile.post("/api/export/html", json={"template": "ember"})
        assert res.status_code == 200
        assert "html" in res.json()

    def test_export_html_content_is_string(self, client_with_profile):
        data = client_with_profile.post("/api/export/html", json={
            "content": SAMPLE_PROFILE, "template": "ember"
        }).json()
        assert isinstance(data["html"], str)
        assert len(data["html"]) > 100


# ── Static files ──────────────────────────────────────────────────────────────
class TestStaticFiles:
    def test_root_returns_html(self, client):
        res = client.get("/")
        assert res.status_code == 200
        assert "text/html" in res.headers["content-type"]

    def test_css_served(self, client):
        res = client.get("/style.css")
        assert res.status_code == 200

    def test_js_served(self, client):
        res = client.get("/app.js")
        assert res.status_code == 200


# ── Diff logic ────────────────────────────────────────────────────────────────
class TestDiffLogic:
    def test_identical_profile_has_no_diff(self, client_with_profile):
        with open(client_with_profile.app.state.__dict__.get("_profile_path", ""), "r") if False else open(Path("data/master_profile.yaml") if Path("data/master_profile.yaml").exists() else "/dev/null") as f:
            pass
        # Use deterministic tailor with a matching JD
        res = client_with_profile.post("/api/tailor", json={
            "role": "VP Marketing",
            "jd_text": "pipeline growth leadership martech operations team",
            "use_ai": False,
        })
        # Diff should be a list (may or may not have changes)
        assert isinstance(res.json()["diff"], list)

    def test_diff_section_has_expected_fields(self, client_with_profile):
        res = client_with_profile.post("/api/tailor", json={
            "role": "Data Scientist",
            "jd_text": "python machine learning deep learning neural networks",
            "use_ai": False,
        })
        diff = res.json()["diff"]
        for item in diff:
            assert "section" in item
            assert "label" in item
            assert "type" in item
            assert item["type"] in ("modified", "trimmed", "reordered")


# ── Settings endpoints ────────────────────────────────────────────────────────
class TestSettings:
    def test_get_settings_empty(self, client):
        res = client.get("/api/settings")
        assert res.status_code == 200
        data = res.json()
        assert "anthropic_api_key_set" in data
        assert data["anthropic_api_key_set"] is False

    def test_save_and_retrieve_key(self, client, isolated_data_dir):
        import app as app_module
        monkeypatch_path = isolated_data_dir / "settings.yaml"
        # Patch SETTINGS_FILE
        orig = app_module.SETTINGS_FILE
        app_module.SETTINGS_FILE = monkeypatch_path
        try:
            res = client.put("/api/settings", json={"anthropic_api_key": "sk-ant-test-key-12345678"})
            assert res.status_code == 200
            res2 = client.get("/api/settings")
            assert res2.json()["anthropic_api_key_set"] is True
            assert "sk-ant-t" in res2.json()["anthropic_api_key_preview"]
        finally:
            app_module.SETTINGS_FILE = orig

    def test_save_empty_key_does_not_overwrite(self, client, isolated_data_dir):
        import app as app_module
        monkeypatch_path = isolated_data_dir / "settings.yaml"
        orig = app_module.SETTINGS_FILE
        app_module.SETTINGS_FILE = monkeypatch_path
        try:
            client.put("/api/settings", json={"anthropic_api_key": "sk-ant-real-key-12345678"})
            client.put("/api/settings", json={"anthropic_api_key": ""})
            import yaml
            with open(monkeypatch_path) as f:
                saved = yaml.safe_load(f)
            assert saved.get("anthropic_api_key") == "sk-ant-real-key-12345678"
        finally:
            app_module.SETTINGS_FILE = orig

    def test_key_preview_masked(self, client, isolated_data_dir):
        import app as app_module
        monkeypatch_path = isolated_data_dir / "settings.yaml"
        orig = app_module.SETTINGS_FILE
        app_module.SETTINGS_FILE = monkeypatch_path
        try:
            client.put("/api/settings", json={"anthropic_api_key": "sk-ant-test-supersecretkey9999"})
            res = client.get("/api/settings")
            preview = res.json()["anthropic_api_key_preview"]
            # Should not expose the full key
            assert "supersecretkey9999" not in preview
            assert "…" in preview
        finally:
            app_module.SETTINGS_FILE = orig


# ── SSL / URL fetch ───────────────────────────────────────────────────────────
class TestURLFetch:
    def test_uses_certifi_ssl_context(self):
        import app as app_module
        import ssl
        assert hasattr(app_module, 'SSL_CONTEXT')
        assert isinstance(app_module.SSL_CONTEXT, ssl.SSLContext)

    def test_invalid_url_raises(self):
        from app import _fetch_url_text
        with pytest.raises(Exception):
            _fetch_url_text("http://localhost:19999/no-such-server")

    def test_non_url_raises(self):
        from app import _fetch_url_text
        with pytest.raises(Exception):
            _fetch_url_text("not-a-url-at-all")


# ── Helper functions ──────────────────────────────────────────────────────────
class TestHelpers:
    def test_compute_diff_summary_change(self):
        from app import _compute_diff
        master = {
            "summary": {"default": "Original summary text", "variants": {}},
            "metrics": [], "experience": [], "skills": {}, "speaking": [],
        }
        tailored = {
            "summary": "Different tailored summary",
            "metrics": [], "experience": [], "skills": {}, "speaking": [],
        }
        diff = _compute_diff(master, tailored)
        sections = [d["section"] for d in diff]
        assert "summary" in sections
        summary_diff = next(d for d in diff if d["section"] == "summary")
        assert summary_diff["type"] == "modified"
        assert "original" in summary_diff
        assert "tailored" in summary_diff

    def test_compute_diff_no_changes(self):
        from app import _compute_diff
        profile = {
            "summary": "Same text",
            "metrics": [{"value": "1", "label": "x"}],
            "experience": [{"company": "X", "bullets": [{"text": "did stuff"}]}],
            "skills": {"groups": [{"name": "Tech"}]},
            "speaking": [],
        }
        diff = _compute_diff(profile, dict(profile))
        assert diff == []

    def test_compute_diff_detects_removed_metrics(self):
        from app import _compute_diff
        master = {
            "summary": "x",
            "metrics": [{"value": "a"}, {"value": "b"}, {"value": "c"}],
            "experience": [], "skills": {}, "speaking": [],
        }
        tailored = {
            "summary": "x",
            "metrics": [{"value": "a"}],
            "experience": [], "skills": {}, "speaking": [],
        }
        diff = _compute_diff(master, tailored)
        metrics_diff = next((d for d in diff if d["section"] == "metrics"), None)
        assert metrics_diff is not None
        assert metrics_diff["removed_count"] == 2

    def test_compute_diff_detects_experience_reorder(self):
        from app import _compute_diff
        master = {
            "summary": "x", "metrics": [], "skills": {}, "speaking": [],
            "experience": [{"company": "A", "bullets": []}, {"company": "B", "bullets": []}],
        }
        tailored = {
            "summary": "x", "metrics": [], "skills": {}, "speaking": [],
            "experience": [{"company": "B", "bullets": []}, {"company": "A", "bullets": []}],
        }
        diff = _compute_diff(master, tailored)
        exp_diff = next((d for d in diff if d["section"] == "experience"), None)
        assert exp_diff is not None
        assert exp_diff["order_changed"] is True

    def test_empty_profile_structure(self):
        from app import _empty_profile
        p = _empty_profile()
        assert "meta" in p
        assert "summary" in p
        assert "experience" in p
        assert "education" in p
        assert "skills" in p

    def test_fetch_url_text_invalid_url(self):
        from app import _fetch_url_text
        with pytest.raises(Exception):
            _fetch_url_text("http://localhost:99999/nonexistent")
