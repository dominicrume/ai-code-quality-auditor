"""The local history, and the opt-in share.

The promise in SECURITY.md is that running the tool sends nothing. These tests hold that promise
to the code: a scan writes only to the user's own machine, the share command is the single path
that can reach a network, and what it sends carries no path, no folder name and no specification
name. The allowlist is tested from the outside, by adding a field and checking it stays home.
"""
import json
import sys

import pytest
from click.testing import CliRunner

from auditor.core import history, share
from auditor.core.cli import main


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv(history.ENV_HOME, str(tmp_path / "home"))
    monkeypatch.delenv(history.ENV_OFF, raising=False)
    return tmp_path / "home"


@pytest.fixture
def project(tmp_path):
    """A tiny codebase with a recognisable folder name, so a leak would be obvious."""
    p = tmp_path / "acme-secret-client"
    p.mkdir()
    (p / "app.py").write_text("def add(a, b):\n    return a + b\n")
    return p


def scan(project, *extra):
    return CliRunner().invoke(main, ["scan", str(project), *extra])


# ---- the local half ----
def test_a_scan_is_recorded_on_this_machine_and_reaches_no_network(home, project):
    sys.modules.pop("auditor.core.share", None)
    assert scan(project).exit_code == 0

    rows = history.rows()
    assert len(rows) == 1
    row = rows[0]
    assert row["files"] == 1 and row["loc"] > 0
    assert row["path"] == str(project.resolve())        # kept locally, for the person's own reading
    assert row["spec_supplied"] is False
    assert "security_density" in row["metrics"]
    assert "auditor.core.share" not in sys.modules, "an ordinary scan must not even import the sender"
    assert (home / "history.jsonl").exists()


def test_the_folder_id_is_salted_so_it_means_nothing_on_another_machine(home, project, tmp_path):
    first = history.project_id(project)
    assert first == history.project_id(project), "stable here, so trends work"
    assert first != history.project_id(tmp_path), "a different folder is a different id"
    assert str(project) not in first and "acme" not in first

    history.identity_path().unlink()                    # a new machine, or after `forget --all`
    assert history.project_id(project) != first


def test_history_can_be_switched_off_entirely(home, project, monkeypatch):
    monkeypatch.setenv(history.ENV_OFF, "1")
    assert scan(project).exit_code == 0
    assert history.rows() == [] and not history.history_path().exists()


def test_the_flag_switches_off_one_scan(home, project):
    assert scan(project, "--no-history").exit_code == 0
    assert history.rows() == []


def test_a_damaged_line_never_costs_the_rest(home, project):
    scan(project)
    with history.history_path().open("a") as fh:
        fh.write("{not json at all\n\n")
    scan(project)
    assert len(history.rows()) == 2


def test_a_person_can_delete_one_project_or_everything(home, project, tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    (other / "b.py").write_text("x = 1\n")
    scan(project)
    scan(other)
    assert len(history.rows()) == 2

    assert history.forget("other") == 1
    assert [row["files"] for row in history.rows()] == [1]

    assert history.forget() == 1
    assert not history.history_path().exists()
    assert not history.identity_path().exists(), "forget --all takes the random ids too"


def test_the_trend_reports_movement_between_scans(home, project):
    scan(project)
    (project / "app.py").write_text("def add(a, b):\n    return a + b\n\n\ndef sub(a, b):\n    return a - b\n")
    scan(project)
    rows = history.trend(history.project_id(project))
    assert rows[0]["delta"] == {}
    assert rows[1]["delta"]["loc"] > 0


# ---- the sharing half ----
def test_what_a_share_carries_and_what_it_never_carries(home, project):
    scan(project)
    rows = history.rows()
    payload = share.build(rows, install="test-install")
    text = json.dumps(payload)

    assert payload["scans"] == 1 and payload["projects"] == 1
    assert payload["rows"][0]["metrics"]["security_density"]["value"] is not None
    assert payload["rows"][0]["project"] == "p1"
    assert payload["rows"][0]["spec_supplied"] is False

    assert str(project.resolve()) not in text
    assert "acme-secret-client" not in text
    assert rows[0]["project"] not in text, "even the salted local id stays home"
    assert "app.py" not in text and "def add" not in text
    assert share.leaks(payload, rows) == []


def test_a_new_field_in_the_history_is_not_shared_until_someone_says_so(home, project):
    scan(project)
    rows = history.rows()
    rows[0]["client_name"] = "Acme Holdings"           # a future field, added carelessly
    payload = share.build(rows, install="test-install")
    assert "Acme Holdings" not in json.dumps(payload), "the allowlist decides, not a denylist"


def test_a_share_sends_only_with_a_destination_and_an_explicit_yes(home, project, monkeypatch):
    scan(project)
    sent = []
    monkeypatch.setattr(share, "send", lambda url, payload, **kw: sent.append(url) or "200 OK")
    runner = CliRunner()

    assert runner.invoke(main, ["share"]).exit_code == 0
    assert runner.invoke(main, ["share", "--to", "https://example.test/x"]).exit_code == 0
    assert sent == [], "showing the payload is not sending it"

    assert runner.invoke(main, ["share", "--to", "https://example.test/x", "--yes"]).exit_code == 0
    assert sent == ["https://example.test/x"]


def test_a_destination_must_be_https(home):
    with pytest.raises(ValueError, match="https"):
        share.send("http://example.test/x", {"rows": []})


def test_share_is_refused_if_the_payload_would_name_anything(home, project, monkeypatch):
    scan(project)
    monkeypatch.setattr(share, "build",
                        lambda rows, install, since=None: {"scans": 1, "projects": 1,
                                                           "rows": [{"path": rows[0]["path"]}]})
    out = CliRunner().invoke(main, ["share"])
    assert out.exit_code == 1 and "Refused" in out.output


def test_only_scans_since_a_date_are_included(home, project):
    scan(project)
    rows = history.rows()
    rows[0]["at"] = "2020-01-01T00:00:00+00:00"
    assert share.build(rows, "i", since="2026-01-01")["scans"] == 0
    assert share.build(rows, "i", since="2019-01-01")["scans"] == 1
