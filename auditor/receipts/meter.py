"""What is billable, recorded so that the same work is never charged twice.

The billable unit is a sealed finding, not an API call. That choice settles
several things at once, and each of them is a decision somebody would otherwise
have to get right by hand:

- **Re-running is free.** The finding digest covers the content and not the
  moment, so a hundred assessments of unchanged code are one outcome. A customer
  cannot be surprised by a bill for a loop in their CI.
- **Idempotency needs no window.** Two sealing requests for the same digest are
  the same outcome whether they arrive a second or a year apart. There is no
  retry key to agree on and no deduplication window to tune.
- **A refusal is not an outcome.** `NOT_APPLICABLE` is a real and useful finding,
  and charging for the sentence "the standard does not apply to this" would be
  charging for the one answer the instrument exists to give honestly. It is
  recorded and not billed.
- **The record is the invoice.** Every entry carries the digest, so a customer
  can reconcile a charge against a receipt they hold. An invoice line nobody can
  trace to an artefact is the thing this product exists to replace.

This module is the ledger shape and a local file implementation. The hosted
sealing service writes the same records to a real store and forwards them to a
billing provider. Keeping the shape here, in the open, means a customer can see
exactly what is recorded about them: a digest, an outcome type, a time. No
source, no paths, no file names.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

# Outcome types. Only the first is billable.
SEALED_ASSESSMENT = "sealed_assessment"
NOT_APPLICABLE = "not_applicable"
UNSEALED_READING = "unsealed_reading"

BILLABLE = {SEALED_ASSESSMENT}

FREE_QUOTA = int(os.environ.get("AUDITOR_FREE_QUOTA", "25"))


def outcome_type(finding: dict) -> str:
    """What kind of outcome this finding is, before any seal is applied."""
    if finding.get("verdict") == "NOT_APPLICABLE":
        return NOT_APPLICABLE
    return SEALED_ASSESSMENT if finding.get("seal") else UNSEALED_READING


def billable(finding: dict) -> bool:
    return outcome_type(finding) in BILLABLE


def entry(finding: dict, org_id: str) -> dict:
    """One ledger row. Deliberately the minimum that supports an invoice."""
    return {
        "org_id": org_id,
        "outcome_type": outcome_type(finding),
        "finding_digest": finding.get("finding_digest"),
        "standard": f"{finding.get('standard', {}).get('name')}"
                    f" v{finding.get('standard', {}).get('version')}",
        "verdict": finding.get("verdict"),
        "key_id": (finding.get("seal") or {}).get("key_id"),
        "recorded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "billable": billable(finding),
    }


class Ledger:
    """Append-only, idempotent on (org_id, finding_digest).

    A file here; a table in the hosted service. The interface is the contract.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser()

    def _rows(self) -> list[dict]:
        if not self.path.exists():
            return []
        rows = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
        return rows

    def seen(self, org_id: str, finding_digest: str,
             billable_only: bool = False) -> bool:
        """Whether this outcome is already recorded for this organisation.

        `billable_only` matters: keying idempotency on the digest alone let a
        free outcome shadow a paid one. A customer could record an unsealed
        reading, then seal the identical finding, and the seal would be waved
        through as already recorded. A billable outcome is therefore only
        blocked by an earlier billable outcome.
        """
        for r in self._rows():
            if r["org_id"] != org_id or r["finding_digest"] != finding_digest:
                continue
            if billable_only and not r.get("billable"):
                continue
            if not billable_only and r.get("billable") != False:
                return True
            if billable_only:
                return True
        return False

    def record(self, finding: dict, org_id: str) -> dict:
        """Record an outcome. Returns the row, with `charged` saying what happened.

        Charging is decided here and only here, so there is one place to read
        when a customer asks why a line appeared.
        """
        row = entry(finding, org_id)
        digest = row["finding_digest"]
        if digest and self.seen(org_id, digest, billable_only=row["billable"]):
            row["charged"] = False
            row["reason"] = "already recorded for this organisation"
            return row
        if not row["billable"]:
            row["charged"] = False
            row["reason"] = (
                "not a billable outcome: a refusal to score and an unsealed "
                "reading are both free")
        else:
            used = self.billable_count(org_id)
            if used < FREE_QUOTA:
                row["charged"] = False
                row["reason"] = f"within the free quota ({used + 1} of {FREE_QUOTA})"
            else:
                row["charged"] = True
                row["reason"] = "billable outcome beyond the free quota"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
        return row

    def billable_count(self, org_id: str) -> int:
        return sum(1 for r in self._rows()
                   if r["org_id"] == org_id and r.get("billable"))

    def charged_count(self, org_id: str) -> int:
        return sum(1 for r in self._rows()
                   if r["org_id"] == org_id and r.get("charged"))

    def statement(self, org_id: str) -> dict:
        rows = [r for r in self._rows() if r["org_id"] == org_id]
        return {
            "org_id": org_id,
            "outcomes": len(rows),
            "billable_outcomes": self.billable_count(org_id),
            "charged": self.charged_count(org_id),
            "free_quota": FREE_QUOTA,
            "digests": [r["finding_digest"] for r in rows],
        }
