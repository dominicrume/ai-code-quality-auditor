"""What this machine audited, kept on this machine.

Every `auditor scan` appends one line to `~/.auditor/history.jsonl`. Nothing is sent anywhere:
this module imports no network library, and the only way a row ever leaves is if the person
running the tool types `auditor share` (see `share.py`, which is a separate module for exactly
that reason).

Three rules shape what a row contains.

*It belongs to the person, not to us.* The file is theirs, in their home directory, readable in
any text editor, and `auditor forget` deletes it.

*A folder is identified by a salted hash, not by its name.* `project` is sha256 of the absolute
path salted with a random value created once on this machine and never transmitted. It is stable
here, so trends work, and meaningless anywhere else, so a shared row cannot be traced back to a
client folder.

*The absolute path is kept locally and never shared.* It is in the row because a person reading
their own history needs to know which project a line refers to. `share.py` builds its payload
from an allowlist that excludes it.

Set `AUDITOR_NO_HISTORY=1` to record nothing at all. Set `AUDITOR_HOME` to move the store.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path

ENV_HOME = "AUDITOR_HOME"
ENV_OFF = "AUDITOR_NO_HISTORY"


def home() -> Path:
    return Path(os.environ.get(ENV_HOME) or (Path.home() / ".auditor"))


def history_path() -> Path:
    return home() / "history.jsonl"


def identity_path() -> Path:
    return home() / "install.json"


def enabled() -> bool:
    return str(os.environ.get(ENV_OFF, "")).strip().lower() not in ("1", "true", "yes", "on")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def identity() -> dict:
    """A random id for this installation and a random salt for folder ids.

    Both are generated here, on first use, and neither is derived from anything about the
    machine or the person. `auditor forget --all` deletes them, after which the same folder
    gets a different id, by design.
    """
    path = identity_path()
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if {"install", "salt"} <= set(data):
                return data
        except (ValueError, OSError):
            pass
    data = {"install": secrets.token_hex(8), "salt": secrets.token_hex(16), "created": now()}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    _private(path)
    return data


def _private(path: Path) -> None:
    try:
        path.chmod(0o600)
    except OSError:
        pass                    # a filesystem without permissions is not a reason to fail a scan


def project_id(path: str | Path) -> str:
    return hashlib.sha256(f"{identity()['salt']}|{Path(path).resolve()}".encode()).hexdigest()[:12]


def row_for(result, version: str, when: str | None = None) -> dict:
    """One scan, as a line. Values and counts only: never a file name, never a line of code."""
    languages = sorted({lang for o in result.outcomes for lang in (o.languages or [])})
    return {
        "at": when or now(),
        "project": project_id(result.path),
        "path": str(result.path),                      # local only; excluded from every share
        "files": result.file_count,
        "loc": result.total_loc,
        "python_files": result.python_files,
        "readable_files": result.readable_files,
        "spec_supplied": bool(result.spec_name),       # whether a brief was given, never its name
        "languages": languages,
        "worst_band": result.worst_band,
        "metrics": {
            o.name: ({"value": o.value, "unit": o.unit, "band": o.band, "coverage": o.coverage}
                     if o.applicable else {"skipped": o.skipped_reason})
            for o in result.outcomes
        },
        "auditor_version": version,
    }


def append(result, version: str) -> Path | None:
    """Record one scan. Returns the file written, or None when history is switched off."""
    if not enabled():
        return None
    path = history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row_for(result, version), sort_keys=True) + "\n")
    _private(path)
    return path


def rows(project: str | None = None) -> list:
    """Every recorded scan, oldest first. A damaged line is skipped, never fatal."""
    path = history_path()
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and (project is None or _matches(row, project)):
            out.append(row)
    return out


def _matches(row: dict, project: str) -> bool:
    """Match on the folder id, or on the folder name a person would actually type."""
    return row.get("project") == project or Path(str(row.get("path", ""))).name == project


def trend(project: str) -> list:
    """One project's scans with the change since the scan before it.

    This is movement between audits, which is what a local history can honestly give. It is not
    the study's rework metric: that needs a captured session, not a folder (§3.4.5).
    """
    out, prev = [], None
    for row in rows(project):
        delta = {}
        if prev:
            delta["loc"] = row.get("loc", 0) - prev.get("loc", 0)
            delta["files"] = row.get("files", 0) - prev.get("files", 0)
            for name, cur in (row.get("metrics") or {}).items():
                before = (prev.get("metrics") or {}).get(name, {})
                if isinstance(cur.get("value"), (int, float)) and isinstance(before.get("value"), (int, float)):
                    delta[name] = round(cur["value"] - before["value"], 4)
        out.append({**row, "delta": delta})
        prev = row
    return out


def forget(project: str | None = None) -> int:
    """Delete one project's rows, or everything including the ids. Returns rows removed."""
    path = history_path()
    if project is None:
        removed = len(rows())
        path.unlink(missing_ok=True)
        identity_path().unlink(missing_ok=True)
        return removed
    keep = [r for r in rows() if not _matches(r, project)]
    removed = len(rows()) - len(keep)
    if removed:
        path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in keep), encoding="utf-8")
        _private(path)
    return removed
