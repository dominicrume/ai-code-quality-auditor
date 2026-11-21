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
from pathlib import Path
from typing import Any

RECEIPT_VERSION = 1

UNSEALED = "unsealed"
SEALED = "sealed"


def canonical(payload: Any) -> bytes:
    """One byte string per value, so a digest is reproducible anywhere."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def digest(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(payload)).hexdigest()


def _file_digests(codebase: dict) -> list[list[str]]:
    out = []
    for path, content in sorted((codebase.get("files") or {}).items()):
        h = hashlib.sha256(content.encode("utf-8", "surrogateescape")).hexdigest()
        out.append([path, h])
    return out


def subject_record(codebase: dict) -> dict:
    """What was read, provably, without carrying any of it."""
    files = _file_digests(codebase)
    return {
        "file_count": len(files),
        "tree_digest": digest(files),
        "files": files,
    }


def _instrument_version() -> str:
    try:
        from importlib.metadata import version
        return version("ai-code-quality-auditor")
    except Exception:
        return "0"


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
    return data.get("open", []) or []


def build(codebase: dict, standard: dict, verdict, *,
          previous: str | None = None) -> dict:
    """A finding, named by its content.

    `verdict` is a ConstitutionVerdict. `previous` is the finding digest of the
    last receipt for this subject, which chains them into an append-only record
    without anybody hosting a database.
    """
    from auditor.governance import subject as subj
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
        "unparsed": sorted(classification.unparsed),
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
                 encoding="utf-8")
    return p


def recompute(finding: dict) -> str:
    """The digest the finding should carry, for checking that it still does."""
    body = {k: v for k, v in finding.items()
            if k not in ("finding_digest", "seal")}
    return digest(body)


def intact(finding: dict) -> bool:
    return finding.get("finding_digest") == recompute(finding)


def state(finding: dict) -> str:
    return SEALED if finding.get("seal") else UNSEALED
