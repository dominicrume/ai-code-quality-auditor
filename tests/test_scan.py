"""Tests for the zero-ceremony directory scan.

The behaviour under test that matters most: a metric that cannot be computed
must be reported as inapplicable, never as 0.00. Silently scoring an unscanned
codebase as perfect is the exact failure mode the instrument exists to expose.

Security and complexity used to be Python-only, so a TypeScript project was
reported as inapplicable across the board. They now read JavaScript and
TypeScript as well, so the same project gets real scores, and the inapplicable
path is reserved for source the tool genuinely cannot read.
"""
from pathlib import Path

import pytest

from auditor.core.calibration import band_for
from auditor.core.scan import scan_directory


@pytest.fixture
def ts_project(tmp_path: Path) -> Path:
    (tmp_path / "app.ts").write_text("export const x = 1;\n" * 5)
    (tmp_path / "ui.tsx").write_text("export const C = () => null;\n")
    return tmp_path


@pytest.fixture
def py_project(tmp_path: Path) -> Path:
    (tmp_path / "main.py").write_text(
        "def handler(flag):\n"
        "    if flag:\n"
        "        return 1\n"
        "    return 0\n"
    )
    return tmp_path


def _outcome(result, name):
    return next(o for o in result.outcomes if o.name == name)


def test_typescript_projects_are_scored_not_skipped(ts_project):
    """A TypeScript project gets real readings, not a row of n/a."""
    result = scan_directory(ts_project)

    for metric in ("security_density", "complexity_mean"):
        outcome = _outcome(result, metric)
        assert outcome.applicable, f"{metric} should now run on TypeScript"
        assert outcome.value is not None
        assert outcome.coverage == 1.0, "all source here is readable"

    assert result.coverage_note is None, "nothing was left unread"


def test_unreadable_source_is_skipped_not_zeroed(tmp_path):
    """The inapplicable path still exists, for languages the tool cannot read."""
    (tmp_path / "main.go").write_text("package main\nfunc main() {}\n")
    result = scan_directory(tmp_path)

    for metric in ("security_density", "complexity_mean"):
        outcome = _outcome(result, metric)
        assert not outcome.applicable, f"{metric} should be inapplicable"
        assert outcome.value is None, f"{metric} must not report a number"


def test_a_partly_readable_project_says_how_much_it_read(tmp_path):
    """Mixed source must not present a partial reading as a whole one."""
    (tmp_path / "app.py").write_text("x = 1\n")
    (tmp_path / "main.go").write_text("package main\n" * 40)
    result = scan_directory(tmp_path)

    security = _outcome(result, "security_density")
    assert security.applicable
    assert security.coverage is not None and security.coverage < 0.5
    assert security.caveat and "read" in security.caveat
    assert result.coverage_note and "%" in result.coverage_note


def test_language_agnostic_metric_still_runs_on_typescript(ts_project):
    duplication = _outcome(scan_directory(ts_project), "duplication_pct")
    assert duplication.applicable
    assert duplication.value is not None


def test_python_project_reports_all_static_metrics(py_project):
    result = scan_directory(py_project)
    assert result.python_files == 1
    for metric in ("security_density", "complexity_mean", "duplication_pct"):
        assert _outcome(result, metric).applicable
    assert result.coverage_note is None


def test_scope_drift_requires_a_spec(py_project):
    without = _outcome(scan_directory(py_project), "hallucinations")
    assert not without.applicable
    # The reason must name the missing thing, not the flag: there are now
    # three ways to supply it (--spec, --brief, and a spec `auditor init`
    # wrote), so naming one of them in the reason would misdirect.
    assert "what was asked for" in without.skipped_reason

    spec = {"name": "demo", "features": [{"id": "a.b"}]}
    with_spec = _outcome(scan_directory(py_project, spec), "hallucinations")
    assert with_spec.applicable


def test_rework_always_needs_a_recorded_session(py_project):
    rework = _outcome(scan_directory(py_project), "correction_freq")
    assert not rework.applicable
    assert "session" in rework.skipped_reason


def test_rework_hint_names_a_command_that_exists(py_project):
    """The hint must point somewhere a user can actually go.

    It used to read "needs a recorded session (auditor session)". There is no
    `session` command, so anyone following the tool's own instruction got
    "Error: No such command 'session'" -- on the one metric that never
    produces a number. The old test asserted the word "session" appeared,
    which the broken hint satisfied perfectly.

    So assert the thing that matters instead: every `auditor <word>` named in
    the hint is a command the CLI actually has.
    """
    import re

    from auditor.core.cli import main

    hint = _outcome(scan_directory(py_project), "correction_freq").skipped_reason
    named = set(re.findall(r"auditor ([a-z][a-z_-]*)", hint))
    assert named, "the hint should tell the user which command to run"
    assert named <= set(main.commands), (
        "hint names %s, but the CLI has %s"
        % (sorted(named), sorted(main.commands))
    )


def test_empty_directory_skips_everything(tmp_path):
    result = scan_directory(tmp_path)
    assert result.file_count == 0
    assert all(not o.applicable for o in result.outcomes)


def test_dependencies_are_excluded_from_the_scan(tmp_path):
    (tmp_path / "main.py").write_text("x = 1\n")
    vendored = tmp_path / "node_modules" / "pkg"
    vendored.mkdir(parents=True)
    (vendored / "index.js").write_text("module.exports = 1;\n" * 50)

    assert scan_directory(tmp_path).file_count == 1


def test_worst_band_drives_the_ci_verdict(py_project):
    result = scan_directory(py_project)
    assert result.worst_band in {"good", "warn", "critical"}


@pytest.mark.parametrize("value,expected", [
    (0.0, "good"), (4.9, "good"), (5.0, "warn"), (9.9, "warn"), (10.0, "critical"),
])
def test_duplication_bands(value, expected):
    assert band_for("duplication_pct", value) == expected


# ------------------------------------------------- test-assert noise

def test_asserts_in_test_files_are_not_security_findings(tmp_path):
    """B101 fires on every assert. In a test file the assert IS the test —
    counting it would score a well-tested codebase worse than an untested one."""
    (tmp_path / "app.py").write_text("def add(a, b):\n    return a + b\n")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_app.py").write_text(
        "from app import add\n\n"
        "def test_add():\n"
        + "".join(f"    assert add({i}, 1) == {i + 1}\n" for i in range(40))
    )
    security = next(o for o in scan_directory(tmp_path).outcomes
                    if o.name == "security_density")
    assert security.applicable
    assert security.value == 0.0, "test assertions were counted as vulnerabilities"


def test_asserts_in_production_code_are_still_findings(tmp_path):
    """The rule exists for a reason: -O strips asserts from shipped code."""
    (tmp_path / "auth.py").write_text(
        "def check(user):\n"
        "    assert user.is_admin, 'not an admin'\n"
        "    return True\n"
    )
    security = next(o for o in scan_directory(tmp_path).outcomes
                    if o.name == "security_density")
    assert security.value > 0, "an assert used as a production check must still count"


def test_scan_names_serious_security_findings_without_changing_the_band(tmp_path):
    """The band still follows the density; the finding is reported beside it."""
    (tmp_path / "svc.py").write_text(
        "import urllib.request\n" + "\n".join(f"x{i} = {i}" for i in range(400))
        + "\nurllib.request.urlopen(url)\n")
    outcome = _outcome(scan_directory(tmp_path), "security_density")
    assert outcome.band == band_for("security_density", outcome.value) == "good"
    assert outcome.details and any("MEDIUM B310" in d for d in outcome.details)


def test_scan_keeps_scope_drift_details_out(tmp_path):
    """The live page offers to strip drift items; the scan must not feed it."""
    (tmp_path / "main.py").write_text("def f():\n    return 1\n")
    for outcome in scan_directory(tmp_path).outcomes:
        if outcome.name != "security_density":
            assert outcome.details is None


# --- a guessed brief that matched nothing (field report, 23 Oct 2026) -------
#
# A user pointed the live view at a documents repository. Its commit subjects
# were prefixed `feat:` and described errands -- contracts, CVs, interview
# answers -- so discovery harvested twelve of them and called them features.
# Nothing in the folder implemented any of them, because none of them were
# software, and the tool answered "0 of 12 delivered" over twelve red crosses.
#
# That states as measurement something the instrument does not know. A brief
# the caller supplies is evidence; a brief the tool guesses is not, and zero
# delivered against a guess impugns the guess.


def _docs_repo(tmp_path):
    """A repository whose commits describe errands rather than software."""
    import subprocess
    root = tmp_path / "docs"
    root.mkdir()
    (root / "notes.md").write_text("# Notes\nContract status lives here.\n")
    (root / "helper.py").write_text("def tidy(text):\n    return text.strip()\n")
    run = lambda *a: subprocess.run(a, cwd=root, capture_output=True, check=True)
    run("git", "init", "-q", ".")
    run("git", "config", "user.email", "t@t")
    run("git", "config", "user.name", "t")
    run("git", "add", "-A")
    for subject in (
        "feat: finalise the contract and Ouaknine notes to paste-ready",
        "feat: the 'why this role' screening answer for the NHS service desk",
        "feat: add real, attributed testimonials to the NHS service-desk CV",
    ):
        run("git", "commit", "-q", "--allow-empty", "-m", subject)
    return root


def test_guessed_brief_that_matches_nothing_is_withdrawn(tmp_path):
    result = scan_directory(_docs_repo(tmp_path))
    assert result.discovery_failed
    assert result.fidelity is None, "a guess that matched nothing is not a verdict"
    assert "intent is unknown" in (result.discovery_note or "").lower() \
        or "could not establish" in (result.discovery_note or "").lower()


def test_scope_drift_is_withdrawn_with_the_brief_it_rested_on(tmp_path):
    result = scan_directory(_docs_repo(tmp_path))
    drift = next(o for o in result.outcomes if o.name == "hallucinations")
    assert drift.value is None, "scope drift cannot outlive the brief behind it"
    assert "matched nothing" in (drift.skipped_reason or "")


def test_a_supplied_brief_still_reports_zero_delivered(tmp_path):
    """The headline finding must survive the fix that silences guesses.

    run_001 contains an agent that, given a CLI specification, shipped a data
    pipeline and delivered none of the six declared subcommands. That zero is
    the dissertation's central result. It is reported because the caller
    supplied the specification.
    """
    root = tmp_path / "wrong"
    root.mkdir()
    (root / "pipeline.py").write_text(
        "def _init_db():\n    return 1\n\n\ndef run_pipeline():\n    return _init_db()\n")
    spec = {
        "name": "cli",
        "features": [
            {"id": "cli.init", "description": "tool init creates a project"},
            {"id": "cli.add", "description": "tool add appends a key"},
        ],
    }
    result = scan_directory(root, spec=spec)
    assert not result.discovery_failed, "a supplied brief is evidence, not a guess"
    assert result.fidelity is not None
    assert not result.fidelity.delivered, "zero delivered is a finding here"


# --- evidence grading: the generalisation of the fix above ------------------
#
# The first fix for FINDING_002 was a boolean set when a guessed brief matched
# nothing. That is one failure mode, not a concept: a guessed brief matching
# one feature in twelve is no more trustworthy and went straight through it.
#
# auditor/core/evidence.py grades every fidelity reading by what it rests on,
# and the surfaces consult the grade before rendering. These pin the three
# grades at their boundaries.


class _Report:
    def __init__(self, total, delivered):
        self.total = total
        self.delivered = delivered


def test_a_supplied_brief_is_a_measurement():
    from auditor.core.evidence import grade, MEASURED
    e = grade({"name": "cli"}, _Report(6, []))
    assert e.grade == MEASURED
    assert e.reportable and not e.needs_disclosure
    assert e.note is None, "a brief a human wrote needs no disclaimer"


def test_a_guessed_brief_is_never_a_measurement():
    """Even when every feature matches. The brief is what is in doubt."""
    from auditor.core.evidence import grade, PROVISIONAL
    e = grade({"_discovered": True, "_discovered_from": "the README"},
              _Report(6, [1, 2, 3, 4, 5, 6]))
    assert e.grade == PROVISIONAL
    assert e.reportable, "it corroborated; it may be shown"
    assert e.needs_disclosure, "but never without saying what it rests on"
    assert "Provisional" in e.note


def test_a_guessed_brief_matching_one_in_twelve_is_still_disclosed():
    """The case the boolean missed.

    discovery_failed was False here, so the old gate reported this exactly as
    it would a supplied brief: an unqualified verdict resting on a guess.
    """
    from auditor.core.evidence import grade, PROVISIONAL
    e = grade({"_discovered": True, "_discovered_from": "recent feat: commits"},
              _Report(12, [1]))
    assert e.grade == PROVISIONAL
    assert e.needs_disclosure
    assert "recent feat: commits" in e.note


def test_a_guessed_brief_corroborating_nothing_is_withheld():
    from auditor.core.evidence import grade, WITHHELD
    e = grade({"_discovered": True, "_discovered_from": "recent feat: commits"},
              _Report(12, []))
    assert e.grade == WITHHELD
    assert not e.reportable
    assert "matched nothing" in e.note
