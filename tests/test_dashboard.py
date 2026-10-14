import re
"""Dashboard smoke tests — index page lists reports, report page renders."""
import csv
import json
from pathlib import Path

import pytest

from auditor.dashboard import app as dashboard_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    reports = tmp_path / "reports"
    reports.mkdir()
    # Synthetic minimal CSV + provenance.
    rows = [
        ["run_id", "condition", "spec_name", "spec_version", "metric", "value", "unit", "timestamp"],
        ["test_001", "human_control", "s", "1", "complexity_mean", "1.5", "cc", "2026-05-27T00:00:00+00:00"],
        ["test_001", "claude_code", "s", "1", "complexity_mean", "2.0", "cc", "2026-05-27T00:00:00+00:00"],
    ]
    with open(reports / "test_001.csv", "w", newline="") as f:
        csv.writer(f).writerows(rows)
    (reports / "test_001.provenance.json").write_text(json.dumps({
        "kind": "pilot",
        "warning": "synthetic data",
        "is_dissertation_result": False,
        "spec_files": ["specs/synthetic_spec.yaml"],
    }))
    monkeypatch.setattr(dashboard_app, "REPORTS_DIR", reports)
    dashboard_app.app.config["TESTING"] = True
    return dashboard_app.app.test_client()


def test_index_lists_reports(client):
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "test_001" in body
    assert "pilot" in body.lower()


def test_report_page_renders_table(client):
    resp = client.get("/report/test_001")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "complexity_mean" in body
    assert "human_control" in body
    assert "claude_code" in body
    assert "Pilot data" in body  # banner shown
    assert "synthetic data" in body


def test_report_page_exposes_view_mode_controls(client):
    resp = client.get("/report/test_001")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Calibrated scores" in body
    assert "Raw values" in body


def test_report_page_surfaces_provenance_spec_summary(client):
    resp = client.get("/report/test_001")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Spec set" in body


def test_report_page_shows_metric_guidance_and_adoption_summary(client):
    resp = client.get("/report/test_001")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Decision guidance" in body
    assert "Adoption implication" in body


def test_unknown_report_is_404(client):
    assert client.get("/report/does_not_exist").status_code == 404


# ------------------------------------------------- public surface is read-only

def test_the_public_dashboard_serves_no_write_or_scan_routes():
    """This viewer is on the open internet with no authentication.

    It once carried copies of the local live server's /api/scan and
    /api/drift/acknowledge. /api/scan would walk any path the container
    could read and describe it back to an anonymous caller; the drift route
    would write to spec.yaml on the server. Nothing in the UI called either.
    """
    from auditor.dashboard.app import app
    unsafe = [
        r for r in app.url_map.iter_rules()
        if r.methods & {"POST", "PUT", "PATCH", "DELETE"}
        and r.rule not in ("/pilot",)          # the waitlist form, and only that
    ]
    assert unsafe == [], f"public dashboard exposes write routes: {[r.rule for r in unsafe]}"


def test_no_page_offers_an_action_the_app_cannot_perform():
    """An 'Auto-Fix Issues' button shipped here POSTing to /api/remediate,
    a route this app has never served. Every click ended in an alert()."""
    from auditor.dashboard.app import app
    served = {r.rule for r in app.url_map.iter_rules()}
    c = app.test_client()
    for path in ("/", "/pilot", "/report/main_001_plus_human"):
        body = c.get(path).get_data(as_text=True)
        for called in re.findall(r"""fetch\(\s*['"](/[^'"?]+)""", body):
            assert called in served, f"{path} fetches {called}, which is not routed"


# --------------------------------------------------------------- the redesign
#
# These exist because rebuilding the templates for the 0.6.0 look silently
# dropped four things that were there for a reason, one of them a disclosure
# about what the data is. A redesign is allowed to move anything except the
# things below.

def test_a_provenance_warning_is_always_shown(client):
    """The disclosure must not depend on the rest of the page being rich.

    It was rendered inside an `{% if spec_summary %}` block, so the one case
    where it mattered most -- a thin report with little else on the page --
    was the case where it vanished.
    """
    body = client.get("/report/test_001").get_data(as_text=True)
    assert "synthetic data" in body
    assert "Caution" in body


def test_both_themes_are_available_on_every_page(client):
    for path in ("/", "/report/test_001"):
        body = client.get(path).get_data(as_text=True)
        assert 'data-theme-set="light"' in body, path
        assert 'data-theme-set="dark"' in body, path
        # Resolved before first paint: a deferred script flashes white.
        assert "auditor-theme" in body, path


def test_the_shared_stylesheet_is_served(client):
    # Served from auditor.assets, not from this app's own static directory,
    # because the live page serves the identical file at the same path.
    resp = client.get("/theme.css")
    assert resp.status_code == 200
    css = resp.get_data(as_text=True)
    # Both themes, and the dark one reachable by preference and by choice.
    assert ":root[data-theme=\"dark\"]" in css
    assert "prefers-color-scheme: dark" in css
    assert "@media print" in css


def test_bands_do_not_rely_on_colour_alone(client):
    """A projected slide and a greyscale print both lose the hue."""
    css = client.get("/theme.css").get_data(as_text=True)
    for band in ("band-good", "band-warn", "band-critical", "band-unknown"):
        assert f".{band}::before" in css, band


def test_accessibility_work_survived_the_redesign(client):
    for path in ("/", "/report/test_001"):
        body = client.get(path).get_data(as_text=True)
        assert "skip-link" in body, path
        assert "focus-visible" in body, path
        assert "prefers-reduced-motion" in body, path


def test_the_charts_are_rebuilt_when_the_theme_changes(client):
    """Plotly bakes colours in, so a toggle leaves them behind unless told."""
    body = client.get("/report/test_001").get_data(as_text=True)
    assert "themechange" in body
    assert "getPropertyValue" in body      # colours read from the stylesheet


def test_the_live_page_and_the_dashboard_serve_one_stylesheet(client, tmp_path):
    """They are separate Flask apps, which is how they drifted apart before."""
    from auditor.live.server import LiveSession, create_app

    (tmp_path / "a.py").write_text("x = 1\n")
    live = create_app(LiveSession(tmp_path)).test_client()
    assert live.get("/theme.css").get_data() == client.get("/theme.css").get_data()
