"""Opt-in sharing of aggregate readings. Nothing here runs unless a person types `auditor share`.

This is the only module in the package that can open a network connection, and it is separate
from every other module for that reason: `scan`, `watch` and `live` do not import it, so no
ordinary use of the tool can reach this code.

What a share contains is decided by an allowlist, not by a denylist, so a field added to the
local history in future is *not* shared until someone adds it here deliberately:

  * the metric values, their units, bands and coverage
  * file and line counts, and which languages were read
  * whether a specification was supplied, never which one
  * the tool version, the operating system family and the Python version
  * a random installation id, created on this machine and deletable with `auditor forget --all`

What a share never contains: a path, a folder name, a specification name, a file name, a finding,
or a line of code. Projects appear as `p1`, `p2` within one payload, numbered afresh each time,
so the receiver can tell two projects apart inside a submission without being able to name either.

The payload is printed before anything is sent, and sending needs both an explicit destination
and an explicit `--yes`.
"""
from __future__ import annotations

import json
import platform
from datetime import datetime, timezone

# Everything a shared row may carry. Anything not named here stays on the machine.
ROW_FIELDS = ("files", "loc", "python_files", "readable_files", "spec_supplied",
              "languages", "worst_band", "metrics", "auditor_version")
METRIC_FIELDS = ("value", "unit", "band", "coverage", "skipped")


def _metric(value: dict) -> dict:
    return {k: v for k, v in value.items() if k in METRIC_FIELDS}


def build(rows: list, install: str, since: str | None = None) -> dict:
    """The exact object `send` would post. Pure: no file is read and no socket is opened."""
    chosen = [r for r in rows if not since or str(r.get("at", ""))[:10] >= since]
    index, shared = {}, []
    for row in chosen:
        key = row.get("project")
        if key not in index:
            index[key] = f"p{len(index) + 1}"
        item = {k: row[k] for k in ROW_FIELDS if k in row}
        item["project"] = index[key]
        item["date"] = str(row.get("at", ""))[:10]          # the day, not the minute
        if isinstance(item.get("metrics"), dict):
            item["metrics"] = {name: _metric(val) for name, val in item["metrics"].items()}
        shared.append(item)
    return {
        "install": install,
        "sent": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "os": platform.system().lower(),
        "python": platform.python_version(),
        "scans": len(shared),
        "projects": len(index),
        "rows": shared,
    }


def leaks(payload: dict, rows: list) -> list:
    """Names anything identifying that survived into the payload. Used by `share` and by a test.

    A share is refused if this returns anything, so a future edit that widens the allowlist
    cannot quietly start sending folder names.
    """
    text = json.dumps(payload)
    found = []
    for row in rows:
        path = str(row.get("path", ""))
        if path and path in text:
            found.append("a folder path")
        if path:
            from pathlib import Path
            name = Path(path).name
            if name and len(name) > 2 and f'"{name}"' in text:
                found.append(f"a folder name ({name})")
        if row.get("project") and row["project"] in text:
            found.append("the local folder id")
    return sorted(set(found))


def send(url: str, payload: dict, opener=None, timeout: float = 15.0) -> str:
    """Post the payload. Refuses anything but https, so a root cannot travel in the clear."""
    if not str(url).lower().startswith("https://"):
        raise ValueError("the destination must be https://")
    body = json.dumps(payload).encode("utf-8")
    if opener is not None:
        return str(opener(url, body))
    import urllib.request                                   # imported here, never at module load
    request = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "ai-code-quality-auditor"})
    with urllib.request.urlopen(request, timeout=timeout) as response:   # the only network call
        return f"{response.status} {response.reason}"
