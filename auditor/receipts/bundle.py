"""The finding, canonicalised, so that the same work has the same name.

A reading is free, local and unlimited. What a team pays for is a receipt: a
finding they can hand to somebody who was not there and who does not trust
them. This module builds the part of that receipt which anybody can compute,
and it deliberately contains no cryptography and no secret, because the
honest half of an attestation has nothing to hide.

Two properties do all the work.

**Content addressing gives idempotency for free.** The digest covers the
finding and not the moment, so the same code assessed against the same standard
by the same version of the instrument yields the same digest forever. A customer
who runs the check a hundred times has produced one finding, and is charged for
one. Nothing has to remember that, and no cache can get it wrong.

**No source leaves the machine.** The subject is recorded as a digest over
(path, content hash) pairs. That is enough for anyone to prove later which exact
bytes were read, and not enough to reconstruct a line of them. A security review
that asks whether proprietary code is transmitted to a third party gets a
structural no.

What the bundle keeps that systems like this usually drop:

- the evidence grade on every element, so a withheld reading stays withheld
  rather than quietly becoming a pass;
- the coverage and the files that could not be parsed;
- the subject classification, because `NOT_APPLICABLE` is a finding worth
  retaining: on this date, this thing was not an agent;
- the defects known to be open in the instrument at the moment of sealing. A
  verdict whose known weakness is invisible to whoever relies on it is not an
  attestation, whatever it is signed with.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

RECEIPT_VERSION = 1

UNSEALED = "unsealed"
SEALED = "sealed"

# A chain pointer is a digest this module produced, or nothing at all.
DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


def canonical(payload: Any) -> bytes:
    """One byte string per value, so a digest is reproducible anywhere.

    `surrogatepass` because a path or an evidence string can carry a lone
    surrogate (a file name that is not valid UTF-8, read back through
    `surrogateescape`), and a receipt that cannot be computed for a file on
    disk is worse than one whose digest covers an odd byte. Every payload that
    is valid UTF-8 encodes to exactly the same bytes as before.
    """
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8", "surrogatepass")


def safe_text(value: str) -> str:
    """A path or label made printable without losing which bytes it was.

    Lone surrogates survive a digest but not a JSON file anyone can read, so
    they are escaped here instead: `\\xff` rather than an unencodable char.
    Reversible, so two different paths cannot be flattened into one.
    """
    return value.encode("utf-8", "surrogateescape").decode("utf-8",
                                                           "backslashreplace")


def digest(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(payload)).hexdigest()


def _file_digests(codebase: dict) -> list[list[str]]:
    out = []
    for path, content in sorted((codebase.get("files") or {}).items()):
        h = hashlib.sha256(content.encode("utf-8", "surrogateescape")).hexdigest()
        out.append([safe_text(path), h])
    return out


def subject_record(codebase: dict) -> dict:
    """What was read, provably, without carrying any of it."""
    files = _file_digests(codebase)
    record = {
        "file_count": len(files),
        "tree_digest": digest(files),
        "files": files,
    }
    # Present on disk and not read: binary, badly encoded, or gone mid-walk.
    # Named rather than omitted, so the receipt cannot imply it saw everything.
    unreadable = codebase.get("unreadable") or []
    if unreadable:
        record["unreadable"] = [safe_text(p) for p in sorted(unreadable)]
    return record


def _instrument_version() -> str:
    """The version of the code that produced the finding.

    Read from the package, not from installed distribution metadata: metadata
    goes stale in an editable install, and a receipt stamped with a version that
    did not produce it is a receipt that lies about its own provenance.
    """
    from auditor._version import __version__
    return __version__


def open_defects() -> list[dict]:
    """Defects known open in the instrument, declared as shipped data.

    `docs/FINDING_*.md` is the record of account and is excluded from the wheel,
    so the machine-readable list travels with the package. A test cross-checks
    the two in a checkout, which is what stops this going stale.
    """
    import yaml
    from auditor.standards import path as standards_path
    f = standards_path("open_defects.yaml")
    if not f.exists():
        return []
    data = yaml.safe_load(f.read_text()) or {}
    # Coerced to text. YAML reads a bare 2026-11-21 as a date object, which is
    # not JSON serialisable, and one unquoted value in this file made every
    # receipt unproducible. A receipt must be buildable whatever the shipped
    # disclosure happens to contain.
    return [{str(k): _as_text(v) for k, v in entry.items()}
            for entry in (data.get("open") or [])
            if isinstance(entry, dict)]


def _as_text(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_as_text(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _as_text(v) for k, v in value.items()}
    return str(value)


def build(codebase: dict, standard: dict, verdict, *,
          previous: str | None = None) -> dict:
    """A finding, named by its content.

    `verdict` is a ConstitutionVerdict. `previous` is the finding digest of the
    last receipt for this subject, which chains them into an append-only record
    without anybody hosting a database.
    """
    from auditor.governance import subject as subj
    # A chain pointer that is not a digest is not a pointer: it would stand in
    # the record looking like provenance while naming nothing checkable.
    if previous is not None and not DIGEST_PATTERN.match(previous):
        raise ValueError(
            f"chain.previous is not a finding digest: {previous!r}; expected "
            "'sha256:' followed by 64 lowercase hex characters")
    classification = subj.classify(codebase)

    elements = [{
        "id": r.id,
        "basis": r.basis,
        "requirement": r.description,
        "satisfied": r.passed,
        "grade": r.grade,
        "evidence": r.evidence,
    } for r in verdict.results]

    finding = {
        "receipt_version": RECEIPT_VERSION,
        "instrument": {"name": "ai-code-quality-auditor",
                       "version": _instrument_version()},
        "standard": {
            "name": verdict.standard,
            "version": verdict.version,
            "digest": digest(standard),
        },
        "subject": subject_record(codebase),
        "classification": verdict.subject_kind,
        "coverage": round(verdict.coverage, 6),
        "unparsed": sorted(safe_text(u) for u in classification.unparsed),
        "verdict": verdict.verdict,
        "score_over_readable": verdict.score,
        "grades": {"measured": verdict.measured,
                   "provisional": verdict.provisional,
                   "withheld": verdict.withheld},
        "elements": elements,
        "not_established": [r.id for r in verdict.results if not r.reportable],
        "disclosure": verdict.note,
        "instrument_open_defects": open_defects(),
        "chain": {"previous": previous},
    }
    finding["finding_digest"] = digest(
        {k: v for k, v in finding.items() if k != "finding_digest"})
    return finding


def write(finding: dict, out: str | Path) -> Path:
    """A receipt is a file. That is the point: it outlives whatever made it."""
    p = Path(out).expanduser()
    p.write_text(json.dumps(finding, indent=2, ensure_ascii=False) + "\n",
                 encoding="utf-8", errors="surrogatepass")
    return p


def chain_breaks(findings: list[dict]) -> list[str]:
    """Where an ordered run of receipts stops being a chain.

    Nothing else checks this: each receipt names its predecessor and no code
    ever walked the pointers, so a missing or re-pointed link in a record a
    customer hands over would have passed unexamined. Returns one plain
    sentence per problem, empty when the chain is unbroken.
    """
    problems: list[str] = []
    for i, f in enumerate(findings):
        got = (f.get("chain") or {}).get("previous")
        if not intact(f):
            problems.append(f"receipt {i} does not match its own digest")
        if i == 0:
            if got is not None and not DIGEST_PATTERN.match(got):
                problems.append(f"receipt 0 names a malformed predecessor: {got!r}")
            continue
        want = findings[i - 1].get("finding_digest")
        if got != want:
            problems.append(
                f"receipt {i} names {got!r} as its predecessor, but receipt "
                f"{i - 1} is {want!r}")
    return problems


def chain_intact(findings: list[dict]) -> bool:
    return not chain_breaks(findings)


def digest_field(receipt: dict) -> str:
    """Which field names this receipt's own content.

    Version one wrote `finding_digest`. The merged envelope writes
    `content_digest`, because it carries a refusal as readily as a finding and
    calling that a finding would be a lie about what it is. One seal module has
    to serve both, so the field name is asked for rather than assumed.
    """
    return "content_digest" if "content_digest" in receipt else "finding_digest"


def recompute(finding: dict) -> str:
    """The digest the receipt should carry, for checking that it still does.

    Dispatches on the envelope version because canonical form changed: version
    two is ASCII by escaping, so that a Python producer and a JavaScript
    verifier agree. A version one receipt must keep verifying exactly as it did
    the day it was issued, so its path is untouched.
    """
    if finding.get("envelope_version") == 2:
        from auditor.receipts import envelope as E
        return E.content_digest(finding)
    body = {k: v for k, v in finding.items()
            if k not in ("finding_digest", "seal")}
    return digest(body)


def intact(finding: dict) -> bool:
    return finding.get(digest_field(finding)) == recompute(finding)


def state(finding: dict) -> str:
    return SEALED if finding.get("seal") else UNSEALED
