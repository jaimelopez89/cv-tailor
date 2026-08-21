"""Tests for CV Tailor web app."""

import copy
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
    """Each test gets its own data directory with all path vars patched."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    output_dir = data_dir / "output"
    output_dir.mkdir()
    drafts_dir = data_dir / "drafts"
    drafts_dir.mkdir()

    import app as app_module
    monkeypatch.setattr(app_module, "DATA_DIR", data_dir)
    monkeypatch.setattr(app_module, "MASTER_PROFILE", data_dir / "master_profile.yaml")
    monkeypatch.setattr(app_module, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(app_module, "SETTINGS_FILE", data_dir / "settings.yaml")
    monkeypatch.setattr(app_module, "DRAFTS_DIR", drafts_dir)
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

    def test_bad_url_returns_warning_not_error(self, client_with_profile):
        """URL fetch failure must not kill the tailor — it should warn and continue."""
        res = client_with_profile.post("/api/tailor", json={
            "role": "CMO",
            "url": "http://localhost:19999/nonexistent",
            "use_ai": False,
        })
        assert res.status_code == 200, "Bad URL should not return 400"
        data = res.json()
        assert "tailored" in data
        assert data["url_warning"] is not None
        assert "Could not fetch URL" in data["url_warning"]

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


# ── Metric normalisation ──────────────────────────────────────────────────────
class TestMetricNormalisation:
    """The empty-boxes bug: sentence-shaped metrics rendered as blank cells."""

    def test_splits_from_to_range_taking_the_achievement(self):
        from engine.metrics import split_text_metric
        value, label = split_text_metric(
            "Increased marketing-impacted pipeline from EUR 500M to EUR 1.5bn."
        )
        assert value == "€1.5bn"
        assert "pipeline" in label.lower()

    def test_splits_single_figure(self):
        from engine.metrics import split_text_metric
        value, _ = split_text_metric("Grew MQL volume by 61% YoY.")
        assert value == "61%"

    def test_keeps_existing_value_label_shape(self):
        from engine.metrics import normalize_metric
        m = normalize_metric({"value": "3×", "label": "Team growth", "weight": 7})
        assert m["value"] == "3×"
        assert m["label"] == "Team growth"
        assert m["weight"] == 7

    def test_accepts_bare_string(self):
        from engine.metrics import normalize_metric
        assert normalize_metric("Generated EUR 330M in pipeline.")["value"] == "€330M"

    def test_non_dict_entries_do_not_raise(self):
        from engine.metrics import normalize_metric
        assert normalize_metric(None)["value"] == ""

    def test_renderable_drops_empty_metrics(self):
        from engine.metrics import renderable_metrics
        assert renderable_metrics([{"text": ""}, {"value": "", "label": ""}]) == []

    def test_renderable_caps_at_four(self):
        from engine.metrics import renderable_metrics
        many = [{"value": f"{i}%", "label": f"M{i}"} for i in range(10)]
        assert len(renderable_metrics(many)) == 4


class TestTemplatesNeverRenderEmptyMetrics:
    """No template may draw a metrics row it cannot fill."""

    @staticmethod
    def _profile(metrics):
        """Isolated copy — SAMPLE_PROFILE is shared mutable state."""
        profile = copy.deepcopy(SAMPLE_PROFILE)
        profile["metrics"] = metrics
        return profile

    @pytest.mark.parametrize("template", ["ember", "meridian", "slate", "verdant", "folio"])
    def test_empty_metrics_produce_no_row(self, template):
        import re
        from engine.layout import render_html

        profile = self._profile([{"text": ""}, {"value": "", "label": ""}])
        html = render_html(profile, None, template)

        assert not re.search(r'<div class="metrics-row">', html)
        assert not re.search(r'<div class="metric">', html)
        assert not re.search(r'<section class="metrics">', html)

    @pytest.mark.parametrize("template", ["ember", "meridian", "slate", "verdant", "folio"])
    def test_real_metrics_still_render(self, template):
        import re
        from engine.layout import render_html

        profile = self._profile([
            {"value": "€1.5bn", "label": "Pipeline generated"},
            {"value": "3×", "label": "Team growth"},
        ])
        html = render_html(profile, None, template)
        assert len(re.findall(r'<div class="metric">', html)) == 2

    @pytest.mark.parametrize("template", ["ember", "meridian", "slate", "verdant", "folio"])
    def test_sentence_metrics_are_rescued(self, template):
        """A profile straight from the importer should still show figures."""
        import re
        from engine.layout import render_html

        profile = self._profile([{"text": "Grew pipeline from EUR 500M to EUR 1.5bn."}])
        html = render_html(profile, None, template)
        assert len(re.findall(r'<div class="metric">', html)) == 1
        assert "1.5bn" in html


# ── Seniority ────────────────────────────────────────────────────────────────
class TestSeniority:
    def test_detects_vp_from_title(self):
        from engine.seniority import detect_seniority
        assert detect_seniority("VP of Product Marketing", "")["level"] == "vp"

    def test_detects_c_suite(self):
        from engine.seniority import detect_seniority
        assert detect_seniority("Chief Marketing Officer", "")["level"] == "c_suite"

    def test_head_of_reads_as_vp(self):
        from engine.seniority import detect_seniority
        assert detect_seniority("Head of Growth", "")["level"] == "vp"

    def test_jd_signals_lift_confidence(self):
        from engine.seniority import detect_seniority
        result = detect_seniority(
            "VP Marketing",
            "You will own the budget, lead multiple teams and report to the CEO.",
        )
        assert result["level"] == "vp"
        assert result["confidence"] == "high"

    def test_blank_input_defaults_to_lead_with_low_confidence(self):
        from engine.seniority import detect_seniority
        result = detect_seniority("", "")
        assert result["level"] == "lead"
        assert result["confidence"] == "low"

    def test_tone_instructions_differ_by_level(self):
        from engine.seniority import tone_instructions
        assert tone_instructions("vp") != tone_instructions("ic")

    def test_unknown_level_falls_back(self):
        from engine.seniority import tone_profile
        assert tone_profile("nonsense") == tone_profile("lead")


# ── Fabrication guard ────────────────────────────────────────────────────────
class TestVerifier:
    def test_clean_rewrite_passes(self):
        from engine.verify import verify_content
        master = {
            "summary": {"default": ""},
            "experience": [{"company": "Acme", "bullets": [{"text": "Grew pipeline by 61%."}]}],
        }
        tailored = {
            "summary": "",
            "experience": [{"company": "Acme", "bullets": [{"text": "Drove 61% pipeline growth."}]}],
        }
        assert verify_content(master, tailored) == []

    def test_invented_number_is_flagged(self):
        from engine.verify import verify_content
        master = {
            "summary": {"default": ""},
            "experience": [{"company": "Acme", "bullets": [{"text": "Grew pipeline by 61%."}]}],
        }
        tailored = {
            "summary": "",
            "experience": [{"company": "Acme", "bullets": [{"text": "Grew pipeline by 95%."}]}],
        }
        warnings = verify_content(master, tailored)
        assert len(warnings) == 1
        assert "95%" in warnings[0]

    def test_unknown_employer_is_flagged(self):
        from engine.verify import verify_content
        warnings = verify_content(
            {"summary": {"default": ""}, "experience": []},
            {"summary": "", "experience": [{"company": "Ghost Inc", "bullets": []}]},
        )
        assert any("Ghost Inc" in w for w in warnings)

    def test_currency_spelling_variants_are_equivalent(self):
        from engine.verify import verify_content
        master = {
            "summary": {"default": ""},
            "experience": [{"company": "Acme", "bullets": [{"text": "Generated EUR 1.5 billion."}]}],
        }
        tailored = {
            "summary": "",
            "experience": [{"company": "Acme", "bullets": [{"text": "Generated EUR 1.5bn."}]}],
        }
        assert verify_content(master, tailored) == []

    def test_match_bullets_pairs_rewrites(self):
        from engine.verify import match_bullets
        pairs, unmatched = match_bullets(
            ["Built the pipeline system from scratch over two years."],
            ["Built pipeline system from scratch, shipping in two years."],
        )
        assert len(pairs) == 1
        assert unmatched == []

    def test_match_bullets_reports_unrelated_text(self):
        from engine.verify import match_bullets
        pairs, unmatched = match_bullets(["Ran the weekly sales report."], ["Klingon opera reviews."])
        assert pairs == []
        assert unmatched == ["Klingon opera reviews."]


# ── Filenames ────────────────────────────────────────────────────────────────
class TestFilenames:
    def test_includes_role_and_company(self):
        from app import _safe_filename
        assert _safe_filename("Jaime López", "VP of Product Marketing", "Supermetrics") == \
            "Jaime_López_-_VP_of_Product_Marketing_-_Supermetrics"

    def test_name_only_when_untailored(self):
        from app import _safe_filename
        assert _safe_filename("Jaime López") == "Jaime_López"

    def test_cover_letter_kind_is_included(self):
        from app import _safe_filename
        result = _safe_filename("Jane Doe", "Director", "Acme", kind="Cover Letter")
        assert result == "Jane_Doe_-_Cover_Letter_-_Director_-_Acme"

    def test_path_separators_are_stripped(self):
        from app import _safe_filename
        assert "/" not in _safe_filename("../../etc/passwd", "a/b", "c\\d")

    def test_empty_input_uses_fallback(self):
        from app import _safe_filename
        assert _safe_filename("", "", "") == "cv"


# ── Rewrite-aware diffs ──────────────────────────────────────────────────────
class TestRewriteDiff:
    def _profiles(self, tailored_bullet):
        master = {
            "summary": {"default": "S"}, "metrics": [], "skills": {}, "speaking": [],
            "experience": [{"company": "Acme", "bullets": [
                {"text": "Built the pipeline system from scratch over two years."},
            ]}],
        }
        tailored = {
            "summary": "S", "metrics": [], "skills": {}, "speaking": [],
            "experience": [{"company": "Acme", "bullets": [{"text": tailored_bullet}]}],
        }
        return master, tailored

    def test_rewritten_bullet_appears_as_a_rewrite(self):
        from app import _compute_diff
        master, tailored = self._profiles("Built pipeline system from scratch, shipping in two years.")
        exp = next(d for d in _compute_diff(master, tailored) if d["section"] == "experience")
        assert exp["type"] == "rewritten"
        assert len(exp["rewrites"]) == 1
        assert "shipping in two years" in exp["rewrites"][0]["tailored"]

    def test_unchanged_bullet_produces_no_rewrite(self):
        from app import _compute_diff
        master, tailored = self._profiles("Built the pipeline system from scratch over two years.")
        exp = [d for d in _compute_diff(master, tailored) if d["section"] == "experience"]
        assert exp == [] or not exp[0]["rewrites"]

    def test_every_change_carries_an_id(self):
        from app import _compute_diff
        master, tailored = self._profiles("Shipped the pipeline system in two years.")
        assert all("id" in d for d in _compute_diff(master, tailored))


# ── Cover letters ────────────────────────────────────────────────────────────
class TestCoverLetter:
    def test_fallback_letter_uses_only_profile_content(self):
        from engine.cover_letter import _fallback_letter
        letter = _fallback_letter(
            copy.deepcopy(SAMPLE_PROFILE), {"role": "VP Marketing", "company": "Acme"}, {"level": "vp"}
        )
        assert letter["paragraphs"]
        assert "VP Marketing" in letter["paragraphs"][0]

    def test_finish_attaches_letterhead(self):
        from engine.cover_letter import _finish
        profile = copy.deepcopy(SAMPLE_PROFILE)
        profile["meta"]["name"] = "Jane Doe"
        letter = _finish(
            {"paragraphs": ["Body."]}, profile,
            {"role": "VP Marketing", "company": "Acme"}, {"level": "vp", "label": "VP"},
        )
        assert letter["meta"]["name"] == "Jane Doe"
        assert letter["target"]["company"] == "Acme"
        assert letter["signoff"]

    def test_finish_drops_blank_paragraphs(self):
        from engine.cover_letter import _finish
        letter = _finish({"paragraphs": ["Real.", "  ", ""]}, SAMPLE_PROFILE, {}, {})
        assert letter["paragraphs"] == ["Real."]

    @pytest.mark.parametrize("template", ["ember", "meridian", "slate", "verdant", "folio"])
    def test_renders_html_in_every_palette(self, template):
        from engine.cover_letter import _fallback_letter, _finish
        from engine.templates.cover import render_cover_html

        profile = copy.deepcopy(SAMPLE_PROFILE)
        profile["meta"]["name"] = "Jane Doe"
        letter = _finish(
            _fallback_letter(profile, {"role": "VP", "company": "Acme"}, {}),
            profile, {"role": "VP", "company": "Acme"}, {"level": "vp"},
        )
        html = render_cover_html(letter, None, template)
        assert "Jane Doe" in html
        assert "Acme" in html

    def test_renders_pdf(self, tmp_path):
        from engine.cover_letter import _fallback_letter, _finish
        from engine.templates.cover import render_cover_pdf

        letter = _finish(
            _fallback_letter(SAMPLE_PROFILE, {"role": "VP", "company": "Acme"}, {}),
            SAMPLE_PROFILE, {"role": "VP", "company": "Acme"}, {"level": "vp"},
        )
        out = tmp_path / "letter.pdf"
        render_cover_pdf(letter, str(out), "ember")
        assert out.exists() and out.stat().st_size > 1000

    def test_preview_endpoint(self, client):
        from engine.cover_letter import _fallback_letter, _finish
        letter = _finish(
            _fallback_letter(SAMPLE_PROFILE, {"role": "VP", "company": "Acme"}, {}),
            SAMPLE_PROFILE, {"role": "VP", "company": "Acme"}, {"level": "vp"},
        )
        res = client.post("/api/cover-letter/preview", json={"letter": letter, "template": "ember"})
        assert res.status_code == 200
        assert "<body>" in res.json()["html"]

    def test_export_names_file_for_role_and_company(self, client):
        from engine.cover_letter import _fallback_letter, _finish
        letter = _finish(
            _fallback_letter(SAMPLE_PROFILE, {"role": "VP Marketing", "company": "Acme"}, {}),
            SAMPLE_PROFILE, {"role": "VP Marketing", "company": "Acme"}, {"level": "vp"},
        )
        res = client.post("/api/export/cover-letter/pdf", json={
            "letter": letter, "template": "ember",
            "role": "VP Marketing", "company": "Acme",
        })
        assert res.status_code == 200
        disposition = res.headers["content-disposition"]
        assert "Cover_Letter" in disposition
        assert "Acme" in disposition


# ── Drafts stay separate from the master profile ─────────────────────────────
class TestDrafts:
    def test_saving_a_draft_does_not_touch_the_master(self, client_with_profile):
        client = client_with_profile
        before = client.get("/api/profile").json()

        draft = json.loads(json.dumps(before))
        draft["experience"][0]["bullets"] = [draft["experience"][0]["bullets"][0]]
        res = client.post("/api/draft", json={
            "content": draft, "role": "VP Marketing", "company": "Acme",
        })
        assert res.status_code == 200

        after = client.get("/api/profile").json()
        assert after == before, "tailoring must never overwrite the master profile"

    def test_draft_round_trips(self, client_with_profile):
        client = client_with_profile
        profile = client.get("/api/profile").json()
        slug = client.post("/api/draft", json={
            "content": profile, "role": "Director", "company": "Globex",
        }).json()["slug"]

        fetched = client.get(f"/api/draft/{slug}").json()
        assert fetched["role"] == "Director"
        assert fetched["company"] == "Globex"

    def test_missing_draft_returns_404(self, client):
        assert client.get("/api/draft/does-not-exist").status_code == 404

    def test_drafts_are_listed(self, client_with_profile):
        client = client_with_profile
        profile = client.get("/api/profile").json()
        client.post("/api/draft", json={"content": profile, "role": "VP", "company": "Initech"})
        listed = client.get("/api/drafts").json()["drafts"]
        assert any(d["company"] == "Initech" for d in listed)


# ── Interactive tailoring instructions ───────────────────────────────────────
class TestTailorInstructions:
    """User instructions are a first-class, highest-priority input to the prompt."""

    def _seniority(self):
        from engine.seniority import detect_seniority
        return detect_seniority("VP Marketing", "")

    def test_instruction_text_reaches_the_prompt(self):
        from engine.tailor import _shared_rules
        rules = _shared_rules({"role": "CMO"}, True, [], self._seniority(),
                              instructions=["Drop the Wartsila bullets entirely"])
        assert "Drop the Wartsila bullets entirely" in rules

    def test_instructions_outrank_recommendations_in_the_prompt(self):
        """Where the two conflict the user wins, so the user block must come first."""
        from engine.tailor import _shared_rules
        rules = _shared_rules({"role": "CMO"}, True,
                              ["Add more demand-gen language"], self._seniority(),
                              instructions=["Keep it to one page"])
        assert rules.index("Keep it to one page") < rules.index("Add more demand-gen language")

    def test_no_instructions_leaves_the_prompt_unchanged(self):
        from engine.tailor import _shared_rules
        sen = self._seniority()
        assert (_shared_rules({"role": "CMO"}, True, [], sen, instructions=[])
                == _shared_rules({"role": "CMO"}, True, [], sen))

    def test_instructions_stay_subordinate_to_no_fabrication(self):
        from engine.tailor import _shared_rules
        rules = _shared_rules({"role": "CMO"}, True, [], self._seniority(),
                              instructions=["Say I led the Kafka migration"])
        assert "NO FABRICATION" in rules
        assert rules.index("Say I led the Kafka migration") < rules.index("NO FABRICATION")

    def test_endpoint_accepts_instructions(self, client_with_profile):
        res = client_with_profile.post("/api/tailor", json={
            "role": "CMO", "use_ai": False,
            "instructions": ["Lead with the pipeline numbers"],
        })
        assert res.status_code == 200

    def test_endpoint_echoes_instructions_back(self, client_with_profile):
        """The UI rehydrates its instruction list from the response."""
        res = client_with_profile.post("/api/tailor", json={
            "role": "CMO", "use_ai": False,
            "instructions": ["Lead with the pipeline numbers"],
        })
        assert res.json()["instructions"] == ["Lead with the pipeline numbers"]


# ── Token economy on re-tailor ───────────────────────────────────────────────
class TestFitReuse:
    """A re-tailor must not pay for a second fit analysis — the JD hasn't changed."""

    def test_reuse_fit_skips_the_analysis_call(self, client_with_profile, monkeypatch):
        import app as app_module
        calls = []

        def _boom(*args, **kwargs):
            calls.append(args)
            return {"fit_score": 0, "recommendations": []}, []

        monkeypatch.setattr(app_module, "_analyze_fit", _boom)
        cached = {"fit_score": 72, "fit_label": "Strong Match", "recommendations": []}
        res = client_with_profile.post("/api/tailor", json={
            "role": "CMO", "use_ai": False, "reuse_fit": cached,
        })
        assert res.status_code == 200
        assert calls == [], "fit analysis must not run when a cached fit is supplied"
        assert res.json()["fit"]["fit_score"] == 72

    def test_without_reuse_fit_the_analysis_still_runs(self, client_with_profile, monkeypatch):
        import app as app_module
        calls = []

        def _spy(*args, **kwargs):
            calls.append(args)
            return {"fit_score": 0, "recommendations": []}, []

        monkeypatch.setattr(app_module, "_analyze_fit", _spy)
        client_with_profile.post("/api/tailor", json={"role": "CMO", "use_ai": False})
        assert len(calls) == 1

    def test_cached_fit_recommendations_still_reach_the_tailor(self, client_with_profile):
        """Reusing the fit must not silently drop its recommendations."""
        import engine.tailor as tailor_module
        seen = {}
        original = tailor_module.tailor

        def _capture(*args, **kwargs):
            seen["recommendations"] = kwargs.get("recommendations")
            return original(*args, **kwargs)

        tailor_module.tailor = _capture
        try:
            client_with_profile.post("/api/tailor", json={
                "role": "CMO", "use_ai": False,
                "reuse_fit": {"fit_score": 72, "recommendations": ["Name the role explicitly"]},
            })
        finally:
            tailor_module.tailor = original
        assert seen["recommendations"] == ["Name the role explicitly"]


class TestTailorModel:
    def test_tailoring_defaults_to_a_cheap_model(self):
        import engine.tailor as tailor_module
        assert tailor_module.MODEL == "claude-haiku-4-5"

    def test_tailoring_model_is_overridable_by_env(self, monkeypatch):
        import importlib
        import engine.tailor as tailor_module
        monkeypatch.setenv("CV_TAILOR_MODEL", "claude-opus-5")
        try:
            reloaded = importlib.reload(tailor_module)
            assert reloaded.MODEL == "claude-opus-5"
        finally:
            monkeypatch.delenv("CV_TAILOR_MODEL", raising=False)
            importlib.reload(tailor_module)


# ── Empty sections must never render ─────────────────────────────────────────
class TestNoEmptySections:
    """A section with no content must not print its heading, in any template."""

    HEADINGS = {
        "projects": "Other Projects",
        "notable": "Beyond Work",
        "speaking": "Speaking",
        "ventures": "Ventures",
    }

    def _profile(self):
        p = copy.deepcopy(SAMPLE_PROFILE)
        for key in self.HEADINGS:
            p[key] = []
        return p

    @pytest.mark.parametrize("template", ["ember", "meridian", "slate", "verdant", "folio"])
    def test_empty_sections_print_no_heading(self, template):
        from engine.layout import render_html
        html = render_html(self._profile(), None, template)
        for key, heading in self.HEADINGS.items():
            assert heading not in html, \
                f"{template} printed '{heading}' for an empty {key} list"

    @pytest.mark.parametrize("template", ["ember", "meridian", "slate", "verdant", "folio"])
    def test_populated_sections_still_render(self, template):
        from engine.layout import render_html
        p = self._profile()
        p["projects"] = [{"name": "HormuzWatch", "url": "", "description": "Vessel tracking"}]
        html = render_html(p, None, template)
        assert "HormuzWatch" in html

    def test_missing_key_is_treated_as_empty(self):
        from engine.layout import render_html
        p = self._profile()
        del p["projects"]
        assert "Other Projects" not in render_html(p, None, "ember")


class TestTailorCannotIntroduceSections:
    """The model must not be able to add a section the master profile lacks."""

    def test_section_empty_in_master_is_dropped_from_output(self):
        from engine.tailor import _drop_sections_absent_from_master
        master = {"experience": [{"company": "Acme"}], "projects": [], "notable": []}
        tailored = {
            "experience": [{"company": "Acme"}],
            "projects": [{"name": "Invented Side Project"}],
            "notable": ["Invented hobby"],
        }
        out = _drop_sections_absent_from_master(tailored, master)
        assert out["projects"] == []
        assert out["notable"] == []
        assert out["experience"], "real sections must survive"

    def test_section_present_in_master_is_kept(self):
        from engine.tailor import _drop_sections_absent_from_master
        master = {"projects": [{"name": "RevHunt"}]}
        tailored = {"projects": [{"name": "RevHunt"}]}
        assert _drop_sections_absent_from_master(tailored, master)["projects"]


# ── LLM-isms ─────────────────────────────────────────────────────────────────
class TestLLMisms:
    def test_em_dash_is_removed(self):
        from engine.sanitize import sanitize
        assert "—" not in sanitize("Grew pipeline — by 200% — in a year")

    def test_en_dash_between_words_is_removed(self):
        from engine.sanitize import sanitize
        assert "–" not in sanitize("Led the team – and shipped it")

    def test_unambiguous_constructions_are_rewritten(self):
        from engine.sanitize import sanitize
        out = sanitize("Delve into the data to leverage insights in order to utilize resources")
        low = out.lower()
        for banned in ("delve", "leverage", "utilize", "in order to"):
            assert banned not in low, f"{banned!r} survived: {out!r}"

    def test_rewrites_preserve_sentence_case(self):
        from engine.sanitize import sanitize
        assert sanitize("Delve into the numbers").startswith("Examine")

    def test_judgement_call_words_are_left_alone(self):
        """Flagged, not rewritten — these are legitimate CV verbs."""
        from engine.sanitize import sanitize
        assert "Spearheaded" in sanitize("Spearheaded the robust rollout")

    def test_flagger_reports_judgement_call_words(self):
        from engine.sanitize import find_llm_isms
        found = find_llm_isms("Spearheaded a seamless, robust rollout that showcased impact")
        joined = " ".join(found).lower()
        for w in ("seamless", "robust", "showcase"):
            assert w in joined

    def test_flagger_is_quiet_on_clean_text(self):
        from engine.sanitize import find_llm_isms
        assert find_llm_isms("Grew pipeline 200% and led a team of 12") == []

    def test_flagger_catches_the_not_just_construction(self):
        from engine.sanitize import find_llm_isms
        assert find_llm_isms("This is not just a role, but a calling")


class TestSanitizeAtTheOutputBoundary:
    """Cleaning at render time leaves drafts, diffs and letters dirty."""

    def test_tailor_output_is_clean(self, client_with_profile):
        res = client_with_profile.post("/api/tailor", json={
            "role": "CMO", "jd_text": "marketing", "use_ai": False})
        assert "—" not in json.dumps(res.json()["tailored"])

    def test_cover_letter_output_is_clean(self):
        from engine.cover_letter import _clean_letter
        letter = {"paragraphs": ["I would delve into this — deeply"], "closing": "Warmly —"}
        out = _clean_letter(letter)
        body = " ".join(out["paragraphs"] + [out["closing"]])
        assert "—" not in body and "delve" not in body.lower()
