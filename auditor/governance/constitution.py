"""Whether an agent is governed, which is not whether its code is clean.

``compliance_checker`` asks the security question: are there hardcoded
secrets, is input validated, is ``eval`` kept away from user data. A codebase
can pass every one of those and still be an agent nobody has put a limit on.

This module asks the other question, against the five elements in
``specs/kya_constitution_v1.yaml``: is what the agent may do alone bounded, do
the decisions above that bound reach a human, is there a record of what it did
and what it refused, can the rules be changed visibly, and is somebody named.

The honesty constraint is the whole design. A static read of a repository can
establish two of these and only gather evidence about three:

    artefact    a versioned policy file, a CODEOWNERS entry. The artefact is
                the compliance, so absence is a measured failure.
    behaviour   a spend ceiling, an approval gate, an audit log. A scan sees a
                marker in source, never the behaviour at runtime. A marker
                found is PROVISIONAL. No marker found is WITHHELD, never
                FAILED, because the ceiling may sit in infrastructure, a
                gateway or a policy engine this scan cannot read.

A known weakness, recorded rather than hidden: these are markers matched in
source text, so a file that *discusses* governance satisfies them as readily as
one that *implements* it. Scanning this repository, the module matched its own
marker vocabulary and credited this project with an approval gate it does not
have. A text match is the reason every behavioural element is capped at
PROVISIONAL, and it is why the grade is not decoration.

So this module cannot issue a passing KYA verdict on a repository alone, and
that is correct rather than a limitation: a standard you have only partly
measured is not a standard you have passed. The verdict says INCOMPLETE and
names what it could not see, which is the sentence an assurance engagement
exists to replace.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

import yaml
from pydantic import BaseModel

from auditor.core.evidence import MEASURED, PROVISIONAL, WITHHELD
from auditor.core.logger import get_logger

log = get_logger("constitution")

ARTEFACT = "artefact"
BEHAVIOUR = "behaviour"


class ElementResult(BaseModel):
    """One element of the standard, and what the reading rests on."""

    id: str
    basis: str
    description: str
    grade: str
    passed: bool | None   # None when the grade is WITHHELD: not known either way
    evidence: str

    @property
    def reportable(self) -> bool:
        return self.grade != WITHHELD


class ConstitutionVerdict(BaseModel):
    standard: str
    version: int
    verdict: str                 # PASS | FAIL | INCOMPLETE
    score: float | None          # over the elements that could be read; None if none could
    measured: int
    provisional: int
    withheld: int
    results: list[ElementResult]

    @property
    def note(self) -> str | None:
        """The sentence a surface is obliged to print alongside the verdict."""
        if self.withheld:
            unseen = ", ".join(r.id for r in self.results if not r.reportable)
            return (
                f"Incomplete: {self.withheld} of {len(self.results)} elements "
                f"could not be established by reading the code ({unseen}). A "
                f"limit enforced in infrastructure is invisible here, so this "
                f"is not a finding that they are absent."
            )
        if self.provisional:
            return (
                f"{self.provisional} of {len(self.results)} elements rest on a "
                f"marker in source rather than on observed behaviour."
            )
        return None

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)


CheckerFn = Callable[[dict], tuple[bool | None, str, str]]
"""Signature: (codebase) -> (passed, evidence, grade)."""


# ---------------------------------------------------------------------------
# Marker vocabularies
# ---------------------------------------------------------------------------

_CEILING_MARKERS = (
    "max_spend", "spend_cap", "spend_limit", "budget", "quota", "ceiling",
    "rate_limit", "ratelimit", "max_calls", "max_tokens", "max_retries",
    "MAX_", "_LIMIT", "allowlist", "allowed_tools", "permitted_actions",
)

_APPROVAL_MARKERS = (
    "require_approval", "requires_approval", "needs_approval",
    "human_in_the_loop", "human_approval", "await_approval",
    "pending_review", "requires_human", "escalate", "four_eyes",
    "confirm_before", "dry_run",
)

_RECORD_MARKERS = (
    "audit_log", "audit_trail", "action_log", "log_action", "journal",
    "ledger", "append_only", "immutable_log", "receipt", "log_refusal",
    "refusal", "denied", "provenance",
)

_REFUSAL_MARKERS = ("refus", "denied", "rejected", "blocked", "not_permitted")

# Matched as stems, not whole filenames: the first version of this looked for
# "guardrails.yaml" exactly and walked straight past
# specs/governance_guardrails.yaml, which is the very file it was written for.
_POLICY_STEMS = (
    "policy", "policies", "constitution", "guardrail", "guardrails",
    "rules", "governance", "agent",
)

_OWNER_FILENAMES = ("codeowners", "owners", "maintainers")

_OWNER_FIELDS = ("owner:", "owners:", "accountable:", "maintainer:", "steward:")


def _files(codebase: dict) -> dict[str, str]:
    return codebase.get("files", {}) or {}


def _hits(codebase: dict, markers: tuple[str, ...]) -> list[str]:
    found = []
    for path, content in _files(codebase).items():
        lowered = content.lower()
        for marker in markers:
            needle = marker if marker.isupper() else marker.lower()
            probe = content if marker.isupper() else lowered
            if needle in probe:
                found.append(f"{path}: {marker}")
                break
    return found


def _behavioural(hits: list[str], absent: str) -> tuple[bool | None, str, str]:
    """A marker found is provisional; none found is unestablished, not failed."""
    if hits:
        return True, "; ".join(hits[:4]), PROVISIONAL
    return None, absent, WITHHELD


# ---------------------------------------------------------------------------
# The five
# ---------------------------------------------------------------------------

def check_powers_bounded(codebase: dict) -> tuple[bool | None, str, str]:
    return _behavioural(
        _hits(codebase, _CEILING_MARKERS),
        "no ceiling on spend, rate or scope found in source",
    )


def check_separation_of_duty(codebase: dict) -> tuple[bool | None, str, str]:
    return _behavioural(
        _hits(codebase, _APPROVAL_MARKERS),
        "no human-approval gate found in source",
    )


def check_action_record(codebase: dict) -> tuple[bool | None, str, str]:
    hits = _hits(codebase, _RECORD_MARKERS)
    if not hits:
        return None, "no action record found in source", WITHHELD
    # A record of what the agent did is half the element. The refusals are the
    # half that matters to a regulator, and they are what gets left out.
    if not _hits(codebase, _REFUSAL_MARKERS):
        return (False,
                f"a record was found ({hits[0]}) but nothing writes refusals "
                f"to it; a log of permitted actions only cannot show the "
                f"agent was ever told no",
                PROVISIONAL)
    return True, "; ".join(hits[:4]), PROVISIONAL


def check_amendment_path(codebase: dict) -> tuple[bool | None, str, str]:
    files = _files(codebase)
    policies = [p for p in files
                if Path(p).suffix.lower() in (".yaml", ".yml")
                and any(stem in Path(p).stem.lower() for stem in _POLICY_STEMS)]
    if not policies:
        return False, "no policy or guardrail file in the repository", MEASURED
    versioned = [p for p in policies
                 if "version" in files[p].lower()]
    if not versioned:
        return (False,
                f"policy file {policies[0]} carries no version, so a change to "
                f"the rules is not visible as one",
                MEASURED)
    return True, f"versioned policy at {versioned[0]}", MEASURED


def check_named_accountability(codebase: dict) -> tuple[bool | None, str, str]:
    files = _files(codebase)
    for path in files:
        if Path(path).name.lower().split(".")[0] in _OWNER_FILENAMES:
            return True, f"owner file at {path}", MEASURED
    for path, content in files.items():
        lowered = content.lower()
        for field in _OWNER_FIELDS:
            if field in lowered:
                return True, f"{path}: {field.rstrip(':')} declared", MEASURED
    return False, "nobody is named as accountable anywhere in the repository", MEASURED


CHECKERS: dict[str, CheckerFn] = {
    "powers_bounded": check_powers_bounded,
    "separation_of_duty": check_separation_of_duty,
    "action_record": check_action_record,
    "amendment_path": check_amendment_path,
    "named_accountability": check_named_accountability,
}


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def load_standard(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def evaluate(codebase: dict, standard: dict) -> ConstitutionVerdict:
    """Read a codebase against the five elements.

    There is no threshold argument. A standard is passed when every element it
    declares is satisfied and established; anything else is FAIL or INCOMPLETE,
    and a caller cannot tune that away.
    """
    results: list[ElementResult] = []
    for element in standard.get("elements", []):
        eid = element["id"]
        checker = CHECKERS.get(eid)
        if checker is None:
            log.warning("constitution: no checker for element %r -- skipped", eid)
            continue
        passed, evidence, grade = checker(codebase)
        results.append(ElementResult(
            id=eid,
            basis=element.get("basis", BEHAVIOUR),
            description=" ".join(element.get("description", "").split()),
            grade=grade,
            passed=passed,
            evidence=evidence,
        ))

    readable = [r for r in results if r.reportable]
    withheld = len(results) - len(readable)
    score = (sum(1 for r in readable if r.passed) / len(readable)
             if readable else None)

    if withheld:
        verdict = "INCOMPLETE"
    elif readable and all(r.passed for r in readable):
        verdict = "PASS"
    else:
        verdict = "FAIL"

    return ConstitutionVerdict(
        standard=standard.get("standard", "kya"),
        version=int(standard.get("version", 1)),
        verdict=verdict,
        score=score,
        measured=sum(1 for r in results if r.grade == MEASURED),
        provisional=sum(1 for r in results if r.grade == PROVISIONAL),
        withheld=withheld,
        results=results,
    )


def evaluate_from_spec(codebase: dict, standard_path: str | Path) -> ConstitutionVerdict:
    return evaluate(codebase, load_standard(standard_path))
