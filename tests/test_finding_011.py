"""FINDING_011 - a supplied specification nothing read.

A user ran 0.6.10 on a small Python project with a hand-written `spec.yaml`
whose sentences sat under `requirements:`. The scan printed a scope-drift
value of 0.00 banded OK, omitted the fidelity table entirely, and still
footed the report with "measured against spec.yaml". They concluded in
writing that the tool had confirmed the implementation matched the stated
requirements. It had not read one of them.

Every test here fails on 0.6.10.
"""
from __future__ import annotations

import yaml

from auditor.core.scan import scan_directory
from auditor.live.brief import normalise_spec, slugify


# The reporter's own file shape, which is the obvious way to write one.
REPORTED_SPEC = """
project: my-project
description: A small calculator that adds and subtracts two numbers.
requirements:
  - The program must add two numbers.
  - The program must subtract two numbers.
  - The program must print the results.
"""

SOURCE = (
    "def add(a, b):\n    return a + b\n\n\n"
    "def subtract(a, b):\n    return a - b\n\n\n"
    "def main():\n    print(add(2, 3))\n    print(subtract(5, 2))\n\n\n"
    'if __name__ == "__main__":\n    main()\n'
)


def _project(tmp_path, spec_text=REPORTED_SPEC):
    (tmp_path / "main.py").write_text(SOURCE)
    (tmp_path / "spec.yaml").write_text(spec_text)
    return tmp_path


def _outcome(result, name):
    return next(o for o in result.outcomes if o.name == name)


# --- the sentences are read out of the key the author used ----------------

def test_requirements_are_read_as_features():
    spec = normalise_spec(yaml.safe_load(REPORTED_SPEC))
    assert len(spec["features"]) == 3
    assert spec["_features_from_key"] == "requirements"


def test_the_users_own_wording_is_preserved_exactly():
    """The id is ours; the sentence is theirs. Rewording somebody's
    requirement is how a report stops being about their project."""
    spec = normalise_spec(yaml.safe_load(REPORTED_SPEC))
    assert [f["description"] for f in spec["features"]] == [
        "The program must add two numbers",
        "The program must subtract two numbers",
        "The program must print the results",
    ]


def test_an_existing_schema_spec_is_left_alone():
    given = {"features": [{"id": "add.numbers", "description": "Add two numbers."}]}
    assert normalise_spec(given) is given


def test_the_input_is_not_mutated():
    given = yaml.safe_load(REPORTED_SPEC)
    before = yaml.safe_dump(given, sort_keys=True)
    normalise_spec(given)
    assert yaml.safe_dump(given, sort_keys=True) == before


def test_a_list_of_dicts_under_requirements_is_not_read_as_sentences():
    """Only a list of plain sentences is a list of requirements. Anything
    else is a structure we do not understand, and stringifying it would put
    `{'id': ...}` into a report as though a person had written it."""
    spec = normalise_spec({"requirements": [{"id": "x", "must": "y"}]})
    assert not spec.get("features")
    assert spec.get("_no_features")


# --- the verdict the reporter should have been given ----------------------

def test_the_fidelity_table_is_produced_at_all(tmp_path):
    root = _project(tmp_path)
    spec = normalise_spec(yaml.safe_load((root / "spec.yaml").read_text()))
    result = scan_directory(root, spec)
    assert result.fidelity is not None
    assert result.fidelity.total == 3, "0.6.10 produced no table from this spec"


def test_a_three_function_script_is_not_reported_as_nothing_delivered(tmp_path):
    """The near-miss this test exists for.

    Reading the sentences was not enough. `slugify` took the first three
    meaningful words, so "The program must add two numbers" became
    `program.add.two`, and the matcher tests the *head* word first. Nothing
    declares `program`, so a correct script read **0 of 3 delivered**: a red
    verdict against working code, which is worse than the silence it
    replaced. A word naming the deliverable is filler, exactly as "build"
    already was."""
    root = _project(tmp_path)
    spec = normalise_spec(yaml.safe_load((root / "spec.yaml").read_text()))
    result = scan_directory(root, spec)
    delivered = {v.feature_id for v in result.fidelity.delivered}
    assert len(delivered) == 2, result.fidelity.headline
    assert all(not f["id"].startswith("program") for f in spec["features"])


def test_the_delivered_features_cite_a_file_and_a_line(tmp_path):
    root = _project(tmp_path)
    spec = normalise_spec(yaml.safe_load((root / "spec.yaml").read_text()))
    for verdict in scan_directory(root, spec).fidelity.delivered:
        assert verdict.where and ":" in verdict.where


def test_the_deliverable_naming_itself_is_filler_but_a_real_noun_is_not():
    """The line between the two, pinned. "page", "report" and "dashboard"
    name something somebody has to build, which is the thing a fidelity
    verdict looks for, so they stay."""
    assert not slugify("The program must add two numbers", "x").startswith("program")
    assert not slugify("The application should export a file", "x").startswith("application")
    assert slugify("Build a course listing page", "x").startswith("course")
    assert "report" in slugify("Generate a monthly report", "x")
    assert "dashboard" in slugify("Show a dashboard of sales", "x")


# --- a spec that declares nothing checkable must not band green ----------

def test_a_spec_with_no_requirements_withholds_scope_drift(tmp_path):
    """0.00 extra features found, because there was nothing to compare
    against, and 0.00 bands OK. That is FINDING_005's error in a third
    place: a reading that cannot fail is not a reading."""
    root = _project(tmp_path, "project: my-project\ndescription: A calculator.\n")
    drift = _outcome(scan_directory(root, yaml.safe_load((root / "spec.yaml").read_text())),
                     "hallucinations")
    assert drift.value is None
    assert drift.skipped_reason
    assert "no requirements this tool can check" in drift.skipped_reason


def test_the_withheld_reason_names_the_keys_to_use(tmp_path):
    """A refusal that does not say how to satisfy it is a dead end."""
    root = _project(tmp_path, "project: my-project\n")
    drift = _outcome(scan_directory(root, {"project": "my-project"}), "hallucinations")
    assert "requirements" in drift.skipped_reason
    assert "features" in drift.skipped_reason


def test_scope_drift_still_reports_when_the_spec_has_features(tmp_path):
    """The withholding must not swallow the ordinary case."""
    root = _project(tmp_path)
    spec = normalise_spec(yaml.safe_load((root / "spec.yaml").read_text()))
    drift = _outcome(scan_directory(root, spec), "hallucinations")
    assert drift.skipped_reason is None
    assert drift.value is not None
