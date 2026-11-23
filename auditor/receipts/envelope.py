"""One receipt envelope, two payload types.

Two hash-chained receipt formats existed for the two halves of one question:
whether an agent was built with rules, and what the rules actually stopped. One
was signed and one was not. Two formats for one chain of evidence is what reads
as indecision to anybody assessing the work, and each format had written down,
in public, the hole the other closed.

This module is the merge. `docs/RECEIPT_ENVELOPE.md` is the normative text and
this is its only implementation. Three properties do the work, and two of them
are taken from the format being merged in rather than from this one.

**Assurance is derived, and there is no field for it.** A verifier computes
`self_attested`, `sealed` or `anchored` from what the reader brought. A producer
cannot assert a level it does not have when there is nowhere to write one.

**Canonical form is ASCII by escaping, not by prohibition.** Python's JSON
writer escapes non-ASCII and JavaScript's does not, so the same receipt seals
differently in two languages. The other format fixed that by forbidding
non-ASCII in a sealed body, at the stated cost that a refusal reason in a
non-Latin script cannot be sealed as written. Escaping gives identical bytes in
every language *and* keeps the text, which closes a limitation that format
declares about itself.

**The digest covers the content and not the moment.** The same work has the
same name forever, which is what makes the billable unit idempotent. A
refusal's own time is material, so it sits inside the payload and is covered.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from auditor.receipts.bundle import (
    DIGEST_PATTERN, open_defects, safe_text, subject_record, _instrument_version,
)

ENVELOPE_VERSION = 2

MEDIA_TYPE = "application/agent-constitution-receipt+json"

STANDARD_NAME = "agent-constitution"

# A receipt produced against `kya/1` was a true statement when it was made.
# Renaming a standard must not invalidate a record somebody is holding.
STANDARD_ALIASES = frozenset({"kya", STANDARD_NAME})

CONFORMANCE = "conformance"
REFUSAL = "refusal"
RECEIPT_TYPES = frozenset({CONFORMANCE, REFUSAL})

STATIC = "static_conformance"
BEHAVIOURAL = "behavioural_evidence"
METHODS = {CONFORMANCE: STATIC, REFUSAL: BEHAVIOURAL}

# Derived by a verifier, never read from a document. There is deliberately no
# envelope field these can be written into.
SELF_ATTESTED = "self_attested"
SEALED = "sealed"
ANCHORED = "anchored"

# An amount is a string because a float does not round-trip identically across
# languages, and an amount that changes in transit is not evidence.
AMOUNT_PATTERN = re.compile(r"^-?\d+(\.\d+)?$")


def _is_amount(value) -> bool:
    """A decimal string, and nothing that merely looks like one once printed.

    The type test is load-bearing and was missing. `str(1.10)` is `"1.1"`,
    which matches the pattern perfectly, so a float passed validation and was
    written into a sealed payload as a float. That is the exact defect the rule
    exists to prevent, and the pattern alone could not see it.
    """
    return isinstance(value, str) and bool(AMOUNT_PATTERN.match(value))


def canonical(payload: Any) -> bytes:
    """One byte string per value, identical in every language.

    `ensure_ascii=True` is the whole point and is not a default taken by
    accident: it is what makes a Python producer and a JavaScript verifier
    agree. `sort_keys` and no whitespace are the rest of the canonical form.

    `surrogatepass` survives a lone surrogate in a path read back through
    `surrogateescape`, which a receipt must be buildable for.
    """
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("ascii", "surrogatepass")


def digest(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(payload)).hexdigest()


# Excluded from the digest: the digest itself, and the seal that is taken over
# it. Everything else is covered, including every field a producer wrote.
_UNCOVERED = ("content_digest", "seal")


def content_digest(envelope: dict) -> str:
    """The name of this envelope's content, independent of when it was issued."""
    return digest({k: v for k, v in envelope.items() if k not in _UNCOVERED})


def intact(envelope: dict) -> bool:
    """True when the envelope still matches the name it carries."""
    claimed = envelope.get("content_digest")
    return bool(claimed) and claimed == content_digest(envelope)


def _envelope(*, receipt_type: str, standard: dict, subject: dict,
              payload: dict, previous: str | None, n: int) -> dict:
    if receipt_type not in RECEIPT_TYPES:
        raise ValueError(f"unknown receipt_type: {receipt_type!r}; "
                         f"expected one of {sorted(RECEIPT_TYPES)}")
    # A chain pointer that is not a digest is not a pointer: it would stand in
    # the record looking like provenance while naming nothing checkable.
    if previous is not None and not DIGEST_PATTERN.match(previous):
        raise ValueError(
            f"chain.previous is not a content digest: {previous!r}; expected "
            "'sha256:' followed by 64 lowercase hex characters")
    if n < 0:
        raise ValueError(f"chain.n cannot be negative: {n}")
    if n == 0 and previous is not None:
        raise ValueError("chain.n is 0, which is the first link, but a "
                         "predecessor was named")
    if n > 0 and previous is None:
        raise ValueError(f"chain.n is {n}, so a predecessor is required")

    env = {
        "envelope_version": ENVELOPE_VERSION,
        "standard": {
            "name": str(standard.get("standard") or STANDARD_NAME),
            "version": int(standard.get("version") or 1),
            "digest": digest(standard),
        },
        "receipt_type": receipt_type,
        "method": METHODS[receipt_type],
        "instrument": {"name": "ai-code-quality-auditor",
                       "version": _instrument_version()},
        "subject": subject,
        "payload": payload,
        "chain": {"n": n, "previous": previous},
        "disclosed_defects": open_defects(),
        # No `seal` key is written here. Absent means unsealed, which is the
        # honest default, and `seal: null` and a missing key must read the same.
    }
    env["content_digest"] = content_digest(env)
    return env


def build_conformance(codebase: dict, standard: dict, verdict, *,
                      previous: str | None = None, n: int = 0) -> dict:
    """A static reading, in the merged envelope.

    The payload is the same body the version-one receipt carried: the grade on
    every element, the coverage, what could not be parsed, and the subject
    classification. What moved is the framing around it.
    """
    from auditor.governance import subject as subj
    classification = subj.classify(codebase)

    payload = {
        "verdict": verdict.verdict,
        "classification": verdict.subject_kind,
        "coverage": round(verdict.coverage, 6),
        "score_over_readable": verdict.score,
        "grades": {"measured": verdict.measured,
                   "provisional": verdict.provisional,
                   "withheld": verdict.withheld},
        "elements": [{
            "id": r.id,
            "basis": r.basis,
            "requirement": r.description,
            "satisfied": r.passed,
            "grade": r.grade,
            "evidence": r.evidence,
        } for r in verdict.results],
        "not_established": [r.id for r in verdict.results if not r.reportable],
        "disclosure": verdict.note,
        "unparsed": sorted(safe_text(u) for u in classification.unparsed),
    }
    return _envelope(receipt_type=CONFORMANCE, standard=standard,
                     subject=subject_record(codebase), payload=payload,
                     previous=previous, n=n)


def build_refusal(*, subject: dict, attempt: dict, rule: str, decided_by: str,
                  at: str, standard: dict | None = None,
                  ledger_ref: str | None = None,
                  previous: str | None = None, n: int = 0) -> dict:
    """One refusal, in the merged envelope.

    This repository does not contain the enforcement point that produces these.
    The builder exists so that the schema is code with tests rather than prose
    in a document, and so the producer has something concrete to write against.

    `decided_by` must name the thing that enforced the rule and not the agent
    that was refused. A refusal an agent recorded about itself is not evidence
    of enforcement, and this is the only place that distinction can be held.
    """
    amount = attempt.get("amount")
    if amount is not None and not _is_amount(amount):
        raise ValueError(
            f"amount must be a decimal string, not {amount!r}: a float does "
            "not round-trip identically across languages")
    if not rule or not str(rule).strip():
        raise ValueError("a refusal with no named rule records nothing: the "
                         "rule that decided is the evidence")
    if not decided_by or not str(decided_by).strip():
        raise ValueError("decided_by must name the enforcement point")

    payload = {
        "attempt": {k: (str(v) if k == "amount" else v)
                    for k, v in sorted(attempt.items())},
        "rule": str(rule),
        "outcome": "refused",
        "decided_by": str(decided_by),
        "at": str(at),
    }
    if ledger_ref is not None:
        # An address, not evidence. Either the record is there with that rule
        # at that time, or it is not, and only a reader who went and looked may
        # raise the assurance level on the strength of it.
        payload["ledger_ref"] = str(ledger_ref)

    return _envelope(receipt_type=REFUSAL,
                     standard=standard or {"standard": STANDARD_NAME,
                                           "version": 1},
                     subject=subject, payload=payload,
                     previous=previous, n=n)


def assurance(envelope: dict, *, public_key: str | None = None,
              anchor_checked: bool = False) -> str:
    """The assurance level, derived from what the reader brought.

    Never read from the document, because there is no field in the document to
    read it from. `seal`, `instrument`, `standard` and `disclosed_defects` are
    all written by the producer and none of them raises this.

    A reader who did not supply a key gets `self_attested` even for a receipt
    carrying a perfectly good signature, which is correct: an unverified
    signature is a string.
    """
    if not intact(envelope):
        raise ValueError("envelope does not match its own content digest; "
                         "no assurance level applies to altered content")
    if public_key is None or not envelope.get("seal"):
        return SELF_ATTESTED

    from auditor.receipts import seal as S
    report = S.verify(envelope, public_key)
    if not report.get("signature_valid"):
        # False is a bad signature and None is "could not check". Neither is a
        # verified one, and neither may be rounded up.
        return SELF_ATTESTED
    # The reader went and looked, and says the chain head is in a record the
    # producer does not control. Only a reader can assert that.
    return ANCHORED if anchor_checked else SEALED


def validate(envelope: dict) -> list[str]:
    """Everything wrong with this envelope, in plain sentences.

    Returns an empty list for a well-formed envelope. Never raises: a verifier
    that crashes on a malformed receipt tells the reader nothing, and a
    malformed receipt is exactly what a verifier is for.
    """
    p: list[str] = []
    if not isinstance(envelope, dict):
        return ["not a JSON object"]

    if envelope.get("envelope_version") != ENVELOPE_VERSION:
        p.append(f"envelope_version is {envelope.get('envelope_version')!r}, "
                 f"expected {ENVELOPE_VERSION}")

    rt = envelope.get("receipt_type")
    if rt not in RECEIPT_TYPES:
        p.append(f"receipt_type is {rt!r}, expected one of {sorted(RECEIPT_TYPES)}")
    elif envelope.get("method") != METHODS[rt]:
        p.append(f"a {rt} receipt declares method {envelope.get('method')!r}, "
                 f"but only {METHODS[rt]!r} can produce one")

    std = envelope.get("standard") or {}
    if std.get("name") not in STANDARD_ALIASES:
        p.append(f"standard.name is {std.get('name')!r}, which this verifier "
                 f"does not know; expected one of {sorted(STANDARD_ALIASES)}")
    if not DIGEST_PATTERN.match(str(std.get("digest") or "")):
        p.append("standard.digest is not a digest, so which standard was "
                 "applied cannot be checked")

    chain = envelope.get("chain") or {}
    n, prev = chain.get("n"), chain.get("previous")
    if not isinstance(n, int) or isinstance(n, bool) or n < 0:
        p.append(f"chain.n is {n!r}, expected a non-negative integer")
    elif n == 0 and prev is not None:
        p.append("chain.n is 0, the first link, yet a predecessor is named")
    elif n > 0 and prev is None:
        p.append(f"chain.n is {n} but no predecessor is named")
    if prev is not None and not DIGEST_PATTERN.match(str(prev)):
        p.append(f"chain.previous is not a digest: {prev!r}")

    # An assurance field is the one thing that must never appear. If a producer
    # has written one, something downstream will eventually read it.
    for forbidden in ("assurance", "assurance_level", "verified", "trusted"):
        if forbidden in envelope or forbidden in (envelope.get("payload") or {}):
            p.append(f"{forbidden!r} is present; assurance is derived by the "
                     "verifier and must not appear in the document")

    if not intact(envelope):
        p.append("content_digest does not match the content")

    try:
        canonical(envelope)
    except UnicodeEncodeError:
        p.append("envelope does not encode to canonical ASCII form")

    if rt == REFUSAL:
        pay = envelope.get("payload") or {}
        for field in ("rule", "outcome", "decided_by", "at", "attempt"):
            if not pay.get(field):
                p.append(f"a refusal receipt is missing payload.{field}")
        amount = (pay.get("attempt") or {}).get("amount")
        if amount is not None and not _is_amount(amount):
            p.append(f"payload.attempt.amount is {amount!r}, expected a "
                     "decimal string")
    return p


def chain_breaks(envelopes: list[dict]) -> list[str]:
    """Where an ordered run of envelopes stops being a chain.

    Checks the pointers *and* the counter. The counter is what makes a removed
    tail visible to a reader who knows how many there should be; the pointers
    are what make an edited middle visible to anybody.
    """
    problems: list[str] = []
    for i, e in enumerate(envelopes):
        chain = e.get("chain") or {}
        if not intact(e):
            problems.append(f"receipt {i} does not match its own digest")
        if chain.get("n") != i:
            problems.append(
                f"receipt {i} is numbered {chain.get('n')!r}; a gap in the "
                "numbering is a removed link")
        if i == 0:
            continue
        got, want = chain.get("previous"), envelopes[i - 1].get("content_digest")
        if got != want:
            problems.append(
                f"receipt {i} names {got!r} as its predecessor, but receipt "
                f"{i - 1} is {want!r}")
    return problems


def chain_intact(envelopes: list[dict]) -> bool:
    return not chain_breaks(envelopes)
