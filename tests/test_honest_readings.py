"""A reading must never claim more than the analysers actually read.

Every test here pins a defect found by running the published 0.5.1 against
real directories. They are grouped in one file because they are one idea:
the instrument exists to catch tools that report a number about code they
did not read, and it was doing that itself.
"""
from __future__ import annotations

import textwrap

import pytest

from auditor.adapters._shared import Ignores, load_codebase
from auditor.analyzers import duplication_analyzer
from auditor.core.scan import scan_directory


def _outcome(result, name):
    return next(o for o in result.outcomes if o.name == name)


@pytest.fixture
def broken(tmp_path):
    """A project whose only Python file cannot be parsed."""
    (tmp_path / "bad.py").write_text("def f(:\n  this is not python @@@\n")
    return tmp_path


# --------------------------------------------------------- code that will not parse

def test_unparseable_code_is_never_reported_as_ok(broken):
    """0.5.1 printed `Security 0.00 OK` for a directory of unparseable Python.

    The lines were added to the scanned total before the parse was attempted,
    so coverage read 100%, the value was 0.00 for want of any finding, and
    0.00 bands as OK. A tool that says OK about code it could not read has
    reported the opposite of what it found.
    """
    result = scan_directory(broken)
    for metric in ("security_density", "complexity_mean"):
        outcome = _outcome(result, metric)
        assert not outcome.applicable, f"{metric} produced a reading from nothing"
        assert outcome.band is None, f"{metric} was banded despite reading nothing"
        assert outcome.unparsed == ["bad.py"]
        assert "could not read" in outcome.skipped_reason


def test_unparseable_code_fails_a_ci_gate(broken):
    """An unreadable file is an unknown, not a pass, so it must not exit 0."""
    assert scan_directory(broken).worst_band == "warn"
    assert scan_directory(broken).read_failure_note is not None
    assert "bad.py" in scan_directory(broken).read_failure_note


def test_a_readable_project_is_unaffected(tmp_path):
    """The floor only rises for code that would not parse."""
    (tmp_path / "ok.py").write_text("def f(x):\n    return x + 1\n")
    result = scan_directory(tmp_path)
    assert result.unparsed_files == []
    assert result.read_failure_note is None
    assert _outcome(result, "complexity_mean").applicable


# ------------------------------------------------------------------ ignore rules

def test_gitignored_directories_are_not_measured(tmp_path):
    """0.5.1 reported 83.58% duplication on this repository.

    The figure was arithmetically right and described `data/raw`, a frozen
    set of research captures the repository does not ship and git ignores.
    """
    (tmp_path / ".gitignore").write_text("data/raw/\n")
    (tmp_path / "app.py").write_text("def f(x):\n    return x\n")
    captures = tmp_path / "data" / "raw"
    captures.mkdir(parents=True)
    block = "def dup(a, b):\n    c = a + b\n    d = c * 2\n    e = d - 1\n    return e\n"
    for i in range(4):
        (captures / f"capture_{i}.py").write_text(block)

    files = load_codebase(tmp_path, respect_ignores=True)["files"]
    assert set(files) == {"app.py"}

    with_captures = load_codebase(tmp_path, respect_ignores=False)["files"]
    assert len(with_captures) == 5, "the experiment path must still see everything"


def test_include_all_measures_what_the_project_ignores(tmp_path):
    (tmp_path / ".gitignore").write_text("generated/\n")
    (tmp_path / "app.py").write_text("x = 1\n")
    (tmp_path / "generated").mkdir()
    (tmp_path / "generated" / "g.py").write_text("y = 2\n")

    assert scan_directory(tmp_path).file_count == 1
    assert scan_directory(tmp_path, include_all=True).file_count == 2
    assert scan_directory(tmp_path, include_all=True).honoured_ignores is False


def test_vendored_directories_are_not_the_users_code(tmp_path):
    (tmp_path / "app.py").write_text("x = 1\n")
    for name in ("vendor", "third_party", "__snapshots__"):
        d = tmp_path / name
        d.mkdir()
        (d / "lib.py").write_text("y = 2\n")
    assert set(load_codebase(tmp_path, respect_ignores=True)["files"]) == {"app.py"}


@pytest.mark.parametrize("pattern,path,ignored", [
    ("*.log", "a.log", True),
    ("*.log", "deep/a.log", True),
    ("/build/", "build/x.py", True),
    ("/build/", "src/build/x.py", False),      # a leading slash anchors
    ("node_modules", "a/node_modules/x.js", True),   # a bare name does not
    ("**/tmp/", "a/b/tmp/x.py", True),
    ("data/*.csv", "data/x.csv", True),
    ("data/*.csv", "data/sub/x.csv", False),    # * stops at a slash
])
def test_ignore_patterns_follow_git_semantics(pattern, path, ignored):
    assert Ignores([pattern]).ignored(path) is ignored


def test_a_negation_re_includes(tmp_path):
    assert Ignores(["*.log", "!keep.log"]).ignored("keep.log") is False
    assert Ignores(["*.log", "!keep.log"]).ignored("other.log") is True


# -------------------------------------------------------- duplication is about code

def test_duplication_counts_code_and_not_prose():
    """75% of what this metric read on its own repository was Markdown.

    Repeated prose in a changelog is not duplicated code, and a reading
    labelled Duplication on a code audit is taken to mean code.
    """
    block = "\n".join(f"line {i} of repeated text here" for i in range(8))
    codebase = {"files": {"a.md": block, "b.md": block, "app.py": "x = 1\n"}, "manifest": []}

    v2 = duplication_analyzer.analyze(codebase, [], {})
    assert v2.value == 0.0, "Markdown was counted as duplicated code"

    v1 = duplication_analyzer.analyze(codebase, [], {}, version=1)
    assert v1.value > 0, "version 1 must stay reproducible for the published figures"


def test_duplication_still_sees_duplicated_code():
    block = "def f(a):\n    b = a + 1\n    c = b * 2\n    d = c - 3\n    e = d / 4\n    return e\n"
    codebase = {"files": {"one.py": block, "two.py": block}, "manifest": []}
    assert duplication_analyzer.analyze(codebase, [], {}).value > 90


# ------------------------------------------------- the density needs its numerator

def test_a_density_is_reported_with_what_it_counted(tmp_path):
    """Two findings in twelve lines is 166.67 per kLOC, which tells nobody much."""
    (tmp_path / "a.py").write_text("import os\nPW = 'hunter2'\n")
    security = _outcome(scan_directory(tmp_path), "security_density")
    assert security.count is not None
    assert security.total_note == f"{security.count} finding" + ("s" if security.count != 1 else "")


# ------------------------------------------- the reading no other tool offers

def test_building_the_wrong_kind_of_thing_is_reported(tmp_path):
    """The case the scope-drift count cannot see, because nothing was added.

    An agent asked for a CLI that ships an ETL package adds no features and
    so scores 0.00, the same as an agent that built the CLI correctly. The
    shape detector separates them, and its verdict was being computed and
    then discarded before it reached the report.
    """
    (tmp_path / "pipeline.py").write_text(textwrap.dedent("""
        import pandas as pd
        def extract(src):
            return pd.read_csv(src)
        def transform(df):
            return df.dropna()
        def load(df, dest):
            df.to_parquet(dest)
    """))
    spec = {"name": "t", "version": "1.0.0",
            "features": [{"id": "cli.add", "description": "a command line tool with add and list"}]}
    result = scan_directory(tmp_path, spec)

    assert _outcome(result, "hallucinations").value == 0.0, \
        "the published metric's value must not change"
    note = result.shape_note
    assert note and "command-line tool" in note and "data pipeline" in note


def test_the_right_shape_raises_nothing(tmp_path):
    """A confident detector that cries wolf is worse than no detector."""
    (tmp_path / "cli.py").write_text(textwrap.dedent("""
        import argparse
        def main():
            p = argparse.ArgumentParser()
            sub = p.add_subparsers()
            sub.add_parser("add")
            sub.add_parser("list")
            return p.parse_args()
    """))
    spec = {"name": "t", "version": "1.0.0",
            "features": [{"id": "cli.add", "description": "a command line tool with add and list"}]}
    assert scan_directory(tmp_path, spec).shape_note is None
