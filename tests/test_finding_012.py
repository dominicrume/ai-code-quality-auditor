"""FINDING_012 - the README's headline example was never run.

Up to and including 0.6.11 the first code block in README.md, which is also the
first thing on the PyPI project page, was written by hand. A fixture built to
match it produced different output in four places. Two of those are defects in
the instrument; the published example was fiction either way.

The example is now captured from a real run. These tests exist so that it
cannot drift away from the tool again without a test going red: one half runs
the fixture, the other half asserts the README still shows what the run
produces.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from auditor.core.scan import scan_directory

REPO = Path(__file__).resolve().parents[1]

# The fixture the README's two examples are captured from. A click CLI, because
# the verdicts the README demonstrates need a real command surface to be
# visible: two exposed subcommands, one internal function nothing exposes, one
# requirement with nothing behind it, and one subcommand nobody asked for.
CLI_SOURCE = '''
import click

@click.group()
def cli():
    pass

@cli.command()
@click.argument("text")
def add(text):
    """Add an item to the list."""
    click.echo(text)

@cli.command("list")
def list_items():
    """List every item."""
    click.echo("items")

@cli.command()
def scheduler():
    """Run the nightly scheduler."""
    click.echo("scheduling")

def export_csv(rows):
    """Export the list to CSV."""
    return ",".join(rows)
'''

BRIEF = ["add an item", "list items", "export to csv", "validate input"]


def _fixture(tmp_path: Path) -> Path:
    project = tmp_path / "item-tracker"
    project.mkdir()
    (project / "cli.py").write_text(CLI_SOURCE.lstrip(), encoding="utf-8")
    (project / "spec.yaml").write_text(
        yaml.safe_dump({"name": "item tracker", "requirements": BRIEF}),
        encoding="utf-8",
    )
    return project


def _report(tmp_path: Path):
    project = _fixture(tmp_path)
    spec = yaml.safe_load((project / "spec.yaml").read_text(encoding="utf-8"))
    return scan_directory(project, spec=spec).fidelity


def test_the_readme_example_is_reproducible(tmp_path):
    """The whole point: the published block comes from a run, not from a pen."""
    report = _report(tmp_path)
    assert {v.description: v.status for v in report.verdicts} == {
        "add an item": "delivered",
        "list items": "delivered",
        "export to csv": "unreachable",
        "validate input": "not_found",
    }


def test_two_of_four_delivered(tmp_path):
    """The headline count in the README block."""
    report = _report(tmp_path)
    assert len(report.delivered) == 2
    assert report.total == 4
    assert report.headline == "2 of 4 delivered"
    assert len(report.unreachable) == 1
    assert len(report.missing) == 1


def test_an_unrequested_subcommand_is_reported_as_drift(tmp_path):
    """`~ scheduler  not asked for`. Attribution, never exclusion."""
    report = _report(tmp_path)
    assert "scheduler" in [e.name for e in report.extras]


def test_every_verdict_cites_a_file_and_a_line(tmp_path):
    """A claim without a location is the defect ERRATUM_003 was written for."""
    report = _report(tmp_path)
    for verdict in report.verdicts:
        if verdict.status == "not_found":
            continue
        assert verdict.where, verdict
        assert ":" in verdict.where, verdict


def test_the_readme_still_shows_what_the_tool_produces():
    """The guard that makes this finding stay closed.

    If the renderer's output format changes, or somebody hand-edits the example
    again, this fails. It is deliberately a string check against the published
    file: the defect was not a wrong number, it was a published block nobody
    had run.
    """
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    for line in (
        '✓  add an item     cli.py:9   subcommand "add"',
        '✓  list items      cli.py:13  subcommand "list"',
        "!  export to csv   cli.py:23  function export_csv exists, but nothing exposes it",
        "✗  validate input             not found",
        "~  scheduler       cli.py:19  not asked for",
    ):
        assert line in readme, f"README no longer shows: {line}"


def test_the_readme_does_not_promise_a_flask_route_as_evidence():
    """Defect 2 of FINDING_012, pinned until the detector learns Flask.

    `_PY_PATTERNS` matches the `@app.get(...)` decorator family. Flask's
    `@app.route(..., methods=[...])` falls through to the plain function
    pattern, so `route POST /claims` is not reachable from Flask source and
    must not be advertised as though it were.
    """
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    for fiction in (
        "api.py:4   route POST /claims",
        "api.py:8   route GET /claims/<ref>",
    ):
        assert fiction not in readme, f"the withdrawn example is back: {fiction}"
