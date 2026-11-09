"""KYA constitution — the five elements, and what a scan may say about each."""
import json
from pathlib import Path

from auditor.core.evidence import MEASURED, PROVISIONAL, WITHHELD
from auditor.governance import constitution as con


STANDARD = Path(__file__).parent.parent / "specs" / "kya_constitution_v1.yaml"


GOVERNED = {
    "agent/policy.yaml": "version: 3\nmax_spend: 500\nowner: platform-team\n",
    "agent/run.py": (
        "MAX_SPEND = 500\n"
        "def act(action):\n"
        "    if action.cost > MAX_SPEND:\n"
        "        return require_approval(action)\n"
        "    audit_log.write(action)\n"
        "    if not permitted(action):\n"
        "        audit_log.write_refusal(action)\n"
        "        return denied(action)\n"
    ),
}

UNGOVERNED = {
    "agent/run.py": (
        "def act(action):\n"
        "    return do_it(action)\n"
    ),
}


# --- the honesty constraint -------------------------------------------------

def test_a_bare_repo_withholds_the_behavioural_elements_rather_than_failing_them():
    """The point of the module. A ceiling enforced in infrastructure is
    invisible to a file scan, so silence is not evidence of absence."""
    verdict = con.evaluate_from_spec({"files": UNGOVERNED}, STANDARD)
    behavioural = {r.id: r for r in verdict.results if r.basis == con.BEHAVIOUR}
    assert set(behavioural) == {"powers_bounded", "separation_of_duty", "action_record"}
    for r in behavioural.values():
        assert r.grade == WITHHELD
        assert r.passed is None, f"{r.id} was reported as failed, not unestablished"


def test_a_bare_repo_does_fail_the_artefact_elements():
    """Absence of a CODEOWNERS file is not ambiguous: nobody is named."""
    verdict = con.evaluate_from_spec({"files": UNGOVERNED}, STANDARD)
    artefact = {r.id: r for r in verdict.results if r.basis == con.ARTEFACT}
    for r in artefact.values():
        assert r.grade == MEASURED
        assert r.passed is False


def test_withholding_anything_makes_the_whole_verdict_incomplete():
    verdict = con.evaluate_from_spec({"files": UNGOVERNED}, STANDARD)
    assert verdict.verdict == "INCOMPLETE"
    assert verdict.withheld == 3
    assert "could not be established" in verdict.note


def test_a_behavioural_element_never_grades_better_than_provisional():
    verdict = con.evaluate_from_spec({"files": GOVERNED}, STANDARD)
    for r in verdict.results:
        if r.basis == con.BEHAVIOUR:
            assert r.grade == PROVISIONAL, (
                f"{r.id} claimed {r.grade}; a scan sees a marker, not behaviour"
            )


def test_a_pass_still_discloses_what_it_rests_on():
    verdict = con.evaluate_from_spec({"files": GOVERNED}, STANDARD)
    assert verdict.verdict == "PASS"
    assert verdict.provisional == 3
    assert "rest on a marker" in verdict.note


# --- individual elements ----------------------------------------------------

def test_powers_bounded_finds_a_ceiling():
    passed, ev, grade = con.check_powers_bounded({"files": GOVERNED})
    assert passed is True and grade == PROVISIONAL
    assert "MAX_" in ev or "max_spend" in ev


def test_separation_of_duty_finds_an_approval_gate():
    assert con.check_separation_of_duty({"files": GOVERNED})[0] is True


def test_a_log_without_refusals_fails_rather_than_passes():
    """The half that matters to a regulator is the half that gets left out."""
    actions_only = {"a.py": "audit_log.write(action)\nallowed = True\n"}
    passed, ev, grade = con.check_action_record({"files": actions_only})
    assert passed is False
    assert grade == PROVISIONAL
    assert "refusal" in ev


def test_action_record_passes_when_refusals_are_written_too():
    assert con.check_action_record({"files": GOVERNED})[0] is True


def test_an_unversioned_policy_file_is_a_measured_failure():
    passed, ev, grade = con.check_amendment_path(
        {"files": {"policy.yaml": "max_spend: 500\n"}})
    assert passed is False and grade == MEASURED
    assert "no version" in ev


def test_amendment_path_accepts_a_versioned_policy():
    assert con.check_amendment_path({"files": GOVERNED})[0] is True


def test_named_accountability_accepts_a_codeowners_file():
    passed, ev, _ = con.check_named_accountability(
        {"files": {"CODEOWNERS": "* @platform-team\n"}})
    assert passed is True
    assert "CODEOWNERS" in ev


def test_named_accountability_accepts_an_owner_field():
    assert con.check_named_accountability({"files": GOVERNED})[0] is True


def test_named_accountability_fails_when_nobody_is_named():
    assert con.check_named_accountability({"files": UNGOVERNED})[0] is False


# --- aggregate --------------------------------------------------------------

def test_score_is_over_what_could_be_read_not_over_five():
    verdict = con.evaluate_from_spec({"files": UNGOVERNED}, STANDARD)
    # 2 readable, both failed
    assert verdict.score == 0.0
    assert verdict.measured == 2


def test_score_is_none_when_nothing_could_be_read():
    verdict = con.evaluate({"files": {}}, {
        "standard": "kya", "version": 1,
        "elements": [{"id": "powers_bounded", "basis": "behaviour",
                      "description": "x"}],
    })
    assert verdict.score is None
    assert verdict.verdict == "INCOMPLETE"


def test_unknown_element_is_skipped_not_crash():
    verdict = con.evaluate({"files": GOVERNED}, {
        "standard": "kya", "version": 1,
        "elements": [{"id": "named_accountability", "basis": "artefact",
                      "description": "x"},
                     {"id": "invented_element", "basis": "artefact",
                      "description": "y"}],
    })
    assert {r.id for r in verdict.results} == {"named_accountability"}


def test_verdict_is_json_serialisable():
    payload = json.loads(con.evaluate_from_spec({"files": GOVERNED}, STANDARD).to_json())
    assert payload["standard"] == "kya"
    assert payload["version"] == 1
    assert len(payload["results"]) == 5


def test_the_spec_declares_exactly_the_five_and_all_are_implemented():
    standard = con.load_standard(STANDARD)
    ids = [e["id"] for e in standard["elements"]]
    assert len(ids) == 5
    assert set(ids) == set(con.CHECKERS)


def test_a_versioned_policy_is_found_by_stem_not_exact_filename():
    """The first cut matched "guardrails.yaml" exactly and walked past
    specs/governance_guardrails.yaml, the file it was written for."""
    passed, ev, grade = con.check_amendment_path(
        {"files": {"specs/governance_guardrails.yaml": "version: 2\nrules: []\n"}})
    assert passed is True and grade == MEASURED
    assert "governance_guardrails" in ev
