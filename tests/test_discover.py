"""The specification is derived, not demanded.

Installing this tool already means handing over the repository. Asking the
developer to then retype what the repository is for is asking twice for
something on disk, and it was the step at which most people stopped.
"""
from __future__ import annotations

import subprocess
import textwrap

import pytest

from auditor.live import discover as D
from auditor.live.brief import load_spec
from auditor.core.scan import scan_directory


@pytest.fixture
def project(tmp_path):
    (tmp_path / "README.md").write_text(textwrap.dedent("""
        # Taskly

        A small task manager.

        ## Features
        - Add a task with a title and due date
        - List all open tasks
        - Mark a task as done
        - Export tasks to CSV
    """))
    (tmp_path / "cli.py").write_text(textwrap.dedent("""
        import click

        @click.group()
        def cli():
            pass

        @cli.command("add")
        def add_task(title):
            pass

        @cli.command("list")
        def list_tasks():
            pass

        def export_csv(path):
            pass
    """))
    return tmp_path


# ------------------------------------------------- the rule that cannot break

def test_intent_is_never_read_from_the_source_tree(tmp_path):
    """A specification inferred from the code it measures is a tautology.

    Every feature would be delivered by construction, nothing would ever be
    missing, and the result would be a clean bill of health that means
    nothing. Reporting nothing is the better failure.
    """
    (tmp_path / "app.py").write_text(
        "def register_user(): pass\ndef login(): pass\ndef export_report(): pass\n")
    (tmp_path / "server.js").write_text("app.get('/healthz', h);\n")
    assert D.discover(tmp_path) is None


def test_a_project_that_states_nothing_gets_no_specification(tmp_path):
    """Inventing one to fill the gap would manufacture the finding."""
    (tmp_path / "main.py").write_text("print('hi')\n")
    assert D.discover(tmp_path) is None
    assert scan_directory(tmp_path).fidelity is None


# ----------------------------------------------------------- the sources used

def test_a_requirements_document_wins(tmp_path):
    (tmp_path / "README.md").write_text("## Features\n- something from the readme\n")
    (tmp_path / "REQUIREMENTS.md").write_text("- the requirement that was written down\n")
    spec = D.discover(tmp_path)
    assert spec["_discovered_from"] == "REQUIREMENTS.md"
    assert "written down" in spec["features"][0]["description"]


def test_the_readme_feature_list_is_read(project):
    spec = D.discover(project)
    assert spec["_discovered_from"] == "README.md"
    assert [f["id"] for f in spec["features"]] == [
        "add.task.title", "list.all.open", "mark.task.done", "export.tasks.csv"]


def test_prose_outside_a_feature_heading_is_not_a_feature(tmp_path):
    (tmp_path / "README.md").write_text(textwrap.dedent("""
        # Thing

        ## Installation
        - pip install thing
        - then run it

        ## Features
        - Send a reminder by email
    """))
    spec = D.discover(tmp_path)
    assert [f["description"] for f in spec["features"]] == ["Send a reminder by email"]


def test_a_term_and_its_gloss_keeps_the_statement(tmp_path):
    """"human_control — a hand-coded baseline" is about the baseline."""
    (tmp_path / "README.md").write_text(
        "## Features\n- `thing` — a hand-coded\n- `other` — Sends a weekly digest to admins\n")
    spec = D.discover(tmp_path)
    descriptions = [f["description"] for f in spec["features"]]
    assert "Sends a weekly digest to admins" in descriptions
    assert "a hand-coded" not in descriptions


def test_commits_are_the_last_resort(tmp_path):
    def git(*args):
        subprocess.run(["git", "-C", str(tmp_path), *args],
                       check=True, capture_output=True)
    try:
        git("init", "-q")
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip("git not available")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "T")
    (tmp_path / "a.py").write_text("x = 1\n")
    git("add", "-A")
    git("commit", "-qm", "feat: send a reminder to every subscriber")
    spec = D.discover(tmp_path)
    assert spec["_discovered_from"] == "recent feat: commits"
    assert "reminder" in spec["features"][0]["description"]


# ---------------------------------------------------- what the developer sees

def test_a_scan_needs_nothing_typed(project):
    result = scan_directory(project)
    assert result.fidelity is not None
    assert result.fidelity.headline == "2 of 4 delivered"
    assert [v.feature_id for v in result.fidelity.missing] == ["mark.task.done"]


def test_the_derived_file_says_it_was_derived(project):
    scan_directory(project)
    written = project / ".auditor" / "spec.yaml"
    # scan_directory does not write; the CLI does. Write it the same way.
    from auditor.live.brief import save_spec
    save_spec(project, D.discover(project))
    text = written.read_text()
    assert "Derived automatically from README.md" in text
    assert "Nothing here was read from your source code" in text
    assert "provisional" in text.lower()


def test_a_spec_the_developer_wrote_is_never_overwritten(project):
    from auditor.live.brief import save_spec

    mine = {"name": "mine", "version": "1.0.0",
            "features": [{"id": "only.mine", "description": "only mine"}]}
    save_spec(project, mine)
    assert load_spec(project)["name"] == "mine"
    result = scan_directory(project, load_spec(project))
    assert [v.feature_id for v in result.fidelity.verdicts] == ["only.mine"]


def test_the_live_session_derives_on_first_run(project):
    from auditor.live.server import LiveSession

    session = LiveSession(project)
    assert session.spec is not None
    assert session.spec_origin == "README.md"
    assert (project / ".auditor" / "spec.yaml").exists()
