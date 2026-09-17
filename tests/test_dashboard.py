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
