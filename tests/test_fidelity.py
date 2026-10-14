"""Specification fidelity: the per-feature verdict, and the evidence under it.

The case that governs this file is the one measured in
docs/ERRATUM_003_token_evidence.md: a six-feature CLI specification against an
ETL script implementing none of it, where the old token rule credited five.
"""
from __future__ import annotations

import textwrap

import pytest

from auditor.analyzers import definitions as defs
from auditor.analyzers import fidelity
from auditor.analyzers.manifest_deriver import derive
from auditor.live.brief import parse_brief

CLI_SPEC = {
    "name": "internal_tool_cli", "version": "1.0.0",
    "features": [
        {"id": "cli.add", "description": "add an item"},
        {"id": "cli.list", "description": "list items"},
        {"id": "cli.export", "description": "export to csv"},
        {"id": "cli.validate", "description": "validate input"},
        {"id": "cli.help", "description": "show help"},
        {"id": "cli.remove", "description": "remove an item"},
    ],
}

ETL_MENTIONING_EVERYTHING = {
    "files": {"etl.py": textwrap.dedent("""
        import pandas as pd
        def extract(src):
            # read the list of rows, add them to a frame, then export
            return pd.read_csv(src)
        def transform(df):
            return df.dropna()      # validate and remove the empties, help
        def load(df, dest):
            df.to_parquet(dest)
    """)},
    "manifest": [],
}

REAL_CLI = {
    "files": {
        "cli.py": textwrap.dedent("""
            import click

            @click.group()
            def cli():
                pass

            @cli.command("add")
            def add_item(name):
                pass

            @cli.command()
            def list():
                pass

            def export_csv(path):
                pass

            @cli.command("scheduler")
            def scheduler():
                pass
        """),
        "store.py": "def remove_item(item_id):\n    pass\n",
    },
    "manifest": [],
}


def _by_id(report):
    return {v.feature_id: v for v in report.verdicts}


# ------------------------------------------------- the defect this replaces

def test_words_in_comments_are_not_evidence_of_delivery():
    report = fidelity.assess(CLI_SPEC, ETL_MENTIONING_EVERYTHING)
    assert report.delivered == []
    assert len(report.missing) == 6
    assert report.completeness == 0.0


def test_version_1_keeps_the_published_rule():
    """The old figures have to stay reproducible, defect and all."""
    old = derive(CLI_SPEC, ETL_MENTIONING_EVERYTHING, version=1)
    # All six, from words in comments. The erratum measures five on a variant
    # of this script that omits the word "help"; here every feature's token
    # appears, which is the rule's behaviour taken to its conclusion.
    assert len(old["implemented"]) == 6
    new = derive(CLI_SPEC, ETL_MENTIONING_EVERYTHING, version=2)
    assert new["implemented"] == []


# --------------------------------------------------------- the three verdicts

def test_a_registered_subcommand_is_delivery_and_cites_its_line():
    v = _by_id(fidelity.assess(CLI_SPEC, REAL_CLI))["cli.add"]
    assert v.status == fidelity.DELIVERED
    assert v.where.startswith("cli.py:")
    assert 'subcommand "add"' == v.evidence


def test_a_feature_nothing_declares_is_missing():
    v = _by_id(fidelity.assess(CLI_SPEC, REAL_CLI))["cli.help"]
    assert v.status == fidelity.NOT_FOUND
    assert v.where is None
    assert v.reason() == "not found"


def test_code_that_exists_but_cannot_be_invoked_is_its_own_verdict():
    """`export_csv` is defined and no user can reach it.

    Reporting that as delivered is wrong and reporting it as missing throws
    away the most useful thing the audit knows: where the work already is.
    """
    report = fidelity.assess(CLI_SPEC, REAL_CLI)
    v = _by_id(report)["cli.export"]
    assert v.status == fidelity.UNREACHABLE
    assert v.where == "cli.py:16"
    assert "nothing exposes it" in v.reason()
    assert [x.feature_id for x in report.unreachable] == ["cli.export", "cli.remove"]


def test_the_headline_counts_only_what_a_user_can_reach():
    report = fidelity.assess(CLI_SPEC, REAL_CLI)
    assert report.headline == "2 of 6 delivered"
    assert report.completeness == pytest.approx(33.33)


def test_surface_nobody_asked_for_is_reported_separately():
    report = fidelity.assess(CLI_SPEC, REAL_CLI)
    assert [e.name for e in report.extras] == ["scheduler"]
    # An internal helper is how code is organised, not a shipped feature.
    assert "export_csv" not in [e.name for e in report.extras]


# ----------------------------------------------------------------- matching

def test_a_feature_is_not_credited_to_a_different_verb_on_the_same_noun():
    """`remove.item` must not be satisfied by `def add_item`."""
    d = defs.Definition(name="add_item", kind="function", file="a.py", line=1)
    assert defs.matches(d, "add.item")
    assert not defs.matches(d, "remove.item")


def test_a_scaffolding_name_is_never_evidence_on_its_own():
    """`def cli()` once credited four features of a CLI specification."""
    d = defs.Definition(name="cli", kind="function", file="a.py", line=1)
    for feature in ("cli.add", "cli.export", "cli.validate", "cli.remove"):
        assert not defs.matches(d, feature)


@pytest.mark.parametrize("feature,name,kind,expected", [
    # Both id styles have to work: hand-authored ids namespace by surface and
    # put the action last, ids derived from a sentence put it first.
    ("cli.export", "export_csv", "function", True),
    ("export.csv", "export_csv", "function", True),
    ("cli.add", "add", "command", True),
    ("add.item", "add", "command", True),
    # A generated wrapper around the feature still counts.
    ("cli.add", "handle_add", "function", True),
    ("cli.add", "addCommand", "function", True),
    # A different operation does not.
    ("cli.export", "extract", "function", False),
    ("cli.list", "load", "function", False),
    # REST expresses the action in the method, so the noun carries the path.
    ("course.list", "/courses/:id", "route", True),
    ("order.list", "/courses", "route", False),
])
def test_matching_rules(feature, name, kind, expected):
    d = defs.Definition(name=name, kind=kind, file="a.py", line=1)
    assert defs.matches(d, feature) is expected


def test_definitions_are_indexed_with_their_line():
    found = {(d.kind, d.name): d for d in defs.index(REAL_CLI)}
    assert found[("command", "add")].where == "cli.py:8"
    assert found[("function", "remove_item")].where == "store.py:1"
    assert found[("command", "scheduler")].is_surface
    assert not found[("function", "export_csv")].is_surface


def test_a_word_in_a_comment_is_not_a_definition():
    index = defs.index(ETL_MENTIONING_EVERYTHING)
    assert {d.name for d in index} == {"extract", "transform", "load"}


# --------------------------------------------- the brief has to keep the verb

def test_a_brief_keeps_the_action_not_just_the_object():
    """"add an item" became the id `item`, so no subcommand could match it."""
    ids = [f["id"] for f in parse_brief("add an item\nexport to csv\nremove an item")]
    assert ids == ["add.item", "export.csv", "remove.item"]


def test_an_instruction_verb_is_still_filler():
    """"build a course listing page" is about the page, not about building."""
    assert [f["id"] for f in parse_brief("Build a course listing page")] == \
        ["course.listing.page"]


def test_a_phrasal_verb_keeps_its_particle():
    assert [f["id"] for f in parse_brief("Users can log in with email")] == \
        ["log.in.email"]


# --------------------------------------------------- it reaches the scan report

def test_the_scan_result_carries_the_verdicts(tmp_path):
    from auditor.core.scan import scan_directory

    (tmp_path / "cli.py").write_text(REAL_CLI["files"]["cli.py"])
    (tmp_path / "store.py").write_text(REAL_CLI["files"]["store.py"])
    result = scan_directory(tmp_path, CLI_SPEC)
    report = result.fidelity
    assert report is not None
    assert report.headline == "2 of 6 delivered"
    assert [v.feature_id for v in report.missing] == ["cli.validate", "cli.help"]


def test_no_specification_means_no_table(tmp_path):
    from auditor.core.scan import scan_directory

    (tmp_path / "a.py").write_text("def f():\n    return 1\n")
    assert scan_directory(tmp_path).fidelity is None


# ------------------------------------------- a route is a method and a path

API_SPEC = {
    "name": "claims", "version": "1.0.0",
    "features": [
        {"id": "submit.new.claim", "description": "submit a new claim"},
        {"id": "look.up.claim", "description": "look up a claim by reference"},
        {"id": "delete.claim", "description": "delete a claim"},
    ],
}

API_CODE = {"files": {"api.py": textwrap.dedent("""
    from flask import Flask
    app = Flask(__name__)

    @app.post("/claims")
    def submit_claim():
        return {}

    @app.get("/claims/<ref>")
    def lookup_claim(ref):
        return {}
""")}, "manifest": []}


def test_two_features_on_one_noun_cite_different_routes():
    """"submit a claim" and "look up a claim" both matched POST /claims.

    The path is the noun and the method is the verb, so ignoring the method
    credited the second feature to code that does something else, and cited
    the same line twice as evidence for both.
    """
    verdicts = {v.feature_id: v for v in fidelity.assess(API_SPEC, API_CODE).verdicts}
    assert verdicts["submit.new.claim"].evidence == "route POST /claims"
    assert verdicts["look.up.claim"].evidence == "route GET /claims/<ref>"
    assert verdicts["submit.new.claim"].where != verdicts["look.up.claim"].where


def test_a_verb_with_no_matching_method_is_not_delivered():
    """Nothing deletes a claim, so the feature is missing rather than credited."""
    verdicts = {v.feature_id: v for v in fidelity.assess(API_SPEC, API_CODE).verdicts}
    assert verdicts["delete.claim"].status == fidelity.NOT_FOUND


def test_a_verb_the_map_does_not_know_still_matches_any_method():
    """The method narrows a match; it must never be required to make one."""
    spec = {"name": "t", "version": "1.0.0",
            "features": [{"id": "reconcile.claim", "description": "reconcile a claim"}]}
    report = fidelity.assess(spec, API_CODE)
    assert report.verdicts[0].status == fidelity.DELIVERED


# ------------------------------------------------ what a person is shown

def test_a_person_is_shown_the_sentence_not_the_slug():
    """The id is a key written for the matcher, and it reads badly.

    "Notify the assessor when a claim is submitted" slugs to
    notify.assessor.when, which is accurate, unreadable, and the wrong thing
    to put on a wall in front of a client.
    """
    v = fidelity.FeatureVerdict(
        feature_id="notify.assessor.when",
        description="Notify the assessor when a claim is submitted",
        status=fidelity.NOT_FOUND)
    assert v.label == "Notify the assessor when a claim is submitted"
    assert v.name == "notify.assessor.when"       # the key is still the key


def test_a_feature_with_no_sentence_falls_back_to_its_id():
    v = fidelity.FeatureVerdict(feature_id="cli.add", description="",
                                status=fidelity.DELIVERED)
    assert v.label == "cli.add"


def test_a_long_label_is_cut_on_a_word():
    v = fidelity.FeatureVerdict(
        feature_id="x.y", description="Attach supporting documents to a claim record",
        status=fidelity.NOT_FOUND)
    short = v.short(20)
    assert len(short) <= 21 and short.endswith("…")
    assert not short[:-1].endswith(" ")


# ------------------------------------- unreachable needs evidence of absence

WIRED = {"files": {"api.py": textwrap.dedent("""
    from flask import Flask
    app = Flask(__name__)

    @app.post("/claims")
    def submit_claim():
        claim = {}
        notify_assessor(claim)
        return claim

    def notify_assessor(claim):
        pass
""")}, "manifest": []}

ORPHANED = {"files": {"api.py": textwrap.dedent("""
    from flask import Flask
    app = Flask(__name__)

    @app.post("/claims")
    def submit_claim():
        return {}

    def notify_assessor(claim):
        pass
""")}, "manifest": []}

NOTIFY_SPEC = {
    "name": "claims", "version": "1.0.0",
    "features": [
        {"id": "submit.new.claim", "description": "Submit a new claim"},
        {"id": "notify.assessor.when", "description": "Notify the assessor"},
    ],
}


def _notify(codebase):
    report = fidelity.assess(NOTIFY_SPEC, codebase)
    return next(v for v in report.verdicts if v.feature_id == "notify.assessor.when")


def test_a_helper_a_route_calls_is_delivered_not_unreachable():
    """It was called unreachable while being called on the line above.

    The verdict rested on the definition not itself being a route, which
    describes most working code. Telling a team their working feature is
    broken costs more trust than missing a finding does.
    """
    assert _notify(WIRED).status == fidelity.DELIVERED


def test_a_helper_nothing_calls_is_still_unreachable():
    """The verdict has to survive, or it was not worth having."""
    v = _notify(ORPHANED)
    assert v.status == fidelity.UNREACHABLE
    assert "nothing exposes it" in v.reason()


def test_a_declaration_is_not_a_use():
    assert not defs.is_invoked("notify_assessor", {
        "files": {"a.py": "def notify_assessor(claim):\n    pass\n"}})
    assert defs.is_invoked("notify_assessor", {
        "files": {"a.py": "def notify_assessor(c):\n    pass\n",
                  "b.py": "notify_assessor({})\n"}})


def test_an_exported_name_counts_as_reachable():
    """A library exposes a function by exporting it, not by routing it."""
    assert defs.is_invoked("formatDate", {
        "files": {"i.ts": "export { formatDate };\n"}})
    assert defs.is_invoked("format_date", {
        "files": {"__init__.py": '__all__ = ["format_date"]\n'}})
