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


def _https_only_opener():
    """An opener that keeps the https promise across redirects.

    Checking the URL the caller passed is not enough. `urlopen` follows
    redirects, and Python's own handler permits the new location to be `http`
    or `ftp` -- it blocks `file:` and little else. A server could therefore
    answer a 302 and move this POST onto a cleartext connection, which is
    precisely what the scheme check exists to prevent and exactly what the
    docstring promised it did.

    Reported from the field as a path-traversal risk at this line. That part
    was a false positive, because the scheme check does block `file:`. The line
    was the right line: the hole was one redirect further on. See FINDING_010.
    """
    import urllib.request

    class _HttpsOnlyRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            if not str(newurl).lower().startswith("https://"):
                raise urllib.error.HTTPError(
                    newurl, code,
                    "refusing a redirect away from https: the payload would "
                    "travel in the clear", headers, fp)
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    return urllib.request.build_opener(_HttpsOnlyRedirect)


def send(url: str, payload: dict, opener=None, timeout: float = 15.0) -> str:
    """Post the payload. Refuses anything but https, so a root cannot travel in the clear.

    The promise holds across redirects too; see `_https_only_opener`.
    """
    if not str(url).lower().startswith("https://"):
        raise ValueError("the destination must be https://")
    body = json.dumps(payload).encode("utf-8")
    if opener is not None:
        return str(opener(url, body))
    import urllib.error                                     # noqa: F401  (used by the handler)
    import urllib.request                                   # imported here, never at module load
    request = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "ai-code-quality-auditor"})
    # The only network call. Through an opener that will not be redirected off
    # https, rather than the module-level `urlopen`, which would be.
    with _https_only_opener().open(request, timeout=timeout) as response:
        return f"{response.status} {response.reason}"
