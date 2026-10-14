"""Work out what the project was asked to be, without asking anybody.

Why this exists
---------------
Installing this tool already means handing it the repository. Making the
developer then retype, into a textarea, what that repository is for is asking
twice for something already on disk, and it is the step at which most people
stop: scope drift was reported as unavailable on nearly every scan because the
specification had to be authored by hand first.

So the specification is derived on first run, the audit starts immediately,
and the derived file is written where the developer can correct it.

The one rule that cannot be broken
----------------------------------
**Intent is never read from the source tree.** A specification inferred from
the code it is about would be satisfied by that code by construction: every
feature would be delivered, nothing would ever be missing, and the number
would be a tautology dressed as a measurement. That is a worse failure than
reporting nothing at all, because it reports a clean bill of health.

Only documents that state intent are read, in this order of authority:

1. an explicit requirements document, which is somebody writing down what is
   wanted;
2. the README's feature or usage list, which is the project describing itself
   to a stranger;
3. the project's one-line description in its package metadata;
4. recent ``feat:`` commit subjects, which are the nearest thing to a record
   of what was last asked for.

Every derived specification records which of these it came from, is marked
provisional, and says so on every surface that reports it. A derived
specification is a starting point the developer owns, not a finding.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from auditor.live.brief import build_spec

# Documents whose whole purpose is to say what is wanted.
REQUIREMENT_FILES = (
    "REQUIREMENTS.md", "SPEC.md", "SPECIFICATION.md", "PRD.md", "SCOPE.md",
    "docs/REQUIREMENTS.md", "docs/SPEC.md", "docs/PRD.md", "docs/SCOPE.md",
)

# README headings beneath which a list of features is usually found.
_FEATURE_HEADINGS = re.compile(
    r"^#{1,4}\s*(features?|what it does|capabilities|usage|commands|"
    r"getting started|quick ?start|endpoints|api)\b",
    re.I,
)
_HEADING = re.compile(r"^#{1,6}\s")
_BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.+?)\s*$")
_FENCE = re.compile(r"^\s*```")
_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_BADGE = re.compile(r"^\s*!\[")
_CODE = re.compile(r"`([^`]+)`")

MAX_FEATURES = 12
MIN_WORDS = 3

# A bullet that continues a previous thought rather than stating a new one.
# These are never the start of a requirement at any length.
_CONTINUATION = re.compile(r"^(and|or|but|also|plus|see|note|e\.g\.|i\.e\.)\b", re.I)
# An article only signals a fragment in something too short to be a sentence:
# "a hand-coded" is a gloss, "The system must send a reminder" is a
# requirement, and rejecting both loses more than it saves.
_ARTICLE = re.compile(r"^(a|an|the)\b", re.I)


def _is_fragment(line: str) -> bool:
    if _CONTINUATION.match(line):
        return True
    return bool(_ARTICLE.match(line)) and len(line.split()) <= 4


def _clean(line: str) -> str:
    line = _LINK.sub(r"\1", line)
    line = _CODE.sub(r"\1", line)
    line = re.sub(r"[*_]{1,2}([^*_]+)[*_]{1,2}", r"\1", line)
    # "auditor scan . — audit a folder" is a term and its gloss; the gloss is
    # the part a person wrote as prose. Taking it blindly turns
    # "human_control — a hand-coded baseline" into "a hand-coded baseline",
    # so the gloss is only preferred when it is a statement on its own.
    parts = re.split(r"\s+[—–]\s+|\s+--\s+", line, maxsplit=1)
    if len(parts) == 2 and len(parts[1].split()) >= MIN_WORDS and not _is_fragment(parts[1]):
        line = parts[1]
    return " ".join(line.split()).strip(" .;:")


def _usable(line: str) -> bool:
    if len(line) < 10 or len(line) > 140:
        return False
    if len(line.split()) < MIN_WORDS:
        return False
    if line.startswith(("http", "![", "<")):
        return False
    if _is_fragment(line):
        return False
    # A line that is only a code token, a path or a flag is reference
    # material, not a thing somebody asked for.
    if re.fullmatch(r"[\w./\-]+", line):
        return False
    return True


def from_requirements(root: Path) -> tuple[list[str], str] | None:
    """Bullets from an explicit requirements document, if the project has one."""
    for name in REQUIREMENT_FILES:
        path = root / name
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines, fenced = [], False
        for raw in text.splitlines():
            if _FENCE.match(raw):
                fenced = not fenced
                continue
            if fenced or _BADGE.match(raw):
                continue
            m = _BULLET.match(raw)
            if m:
                cleaned = _clean(m.group(1))
                if _usable(cleaned):
                    lines.append(cleaned)
        if lines:
            return lines[:MAX_FEATURES], name
    return None


def from_readme(root: Path) -> tuple[list[str], str] | None:
    """Bullets under a features or usage heading in the README."""
    for name in ("README.md", "README.rst", "readme.md"):
        path = root / name
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        collecting, fenced, lines = False, False, []
        for raw in text.splitlines():
            if _FENCE.match(raw):
                fenced = not fenced
                continue
            if fenced:
                continue
            if _HEADING.match(raw):
                # A new heading either opens a feature list or closes one.
                collecting = bool(_FEATURE_HEADINGS.match(raw))
                continue
            if not collecting or _BADGE.match(raw):
                continue
            m = _BULLET.match(raw)
            if m:
                cleaned = _clean(m.group(1))
                if _usable(cleaned):
                    lines.append(cleaned)
        if lines:
            return lines[:MAX_FEATURES], name
    return None


def from_commits(root: Path, limit: int = 40) -> tuple[list[str], str] | None:
    """Subjects of recent ``feat:`` commits.

    The weakest source here, and last for that reason: a commit says what was
    done, which is only evidence of what was asked for. It is used when a
    project documents nothing, because some statement of intent the developer
    can correct beats none at all.
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "log", f"-{limit}", "--no-merges", "--format=%s"],
            capture_output=True, text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    lines = []
    for subject in out.stdout.splitlines():
        m = re.match(r"^feat(?:\([^)]*\))?!?:\s*(.+)$", subject.strip(), re.I)
        if not m:
            continue
        cleaned = _clean(m.group(1))
        if _usable(cleaned) and cleaned.lower() not in {l.lower() for l in lines}:
            lines.append(cleaned)
    if lines:
        return lines[:MAX_FEATURES], "recent feat: commits"
    return None


def from_metadata(root: Path) -> tuple[list[str], str] | None:
    """The project's own one-line description of itself."""
    import json as _json

    pkg = root / "package.json"
    if pkg.is_file():
        try:
            desc = (_json.loads(pkg.read_text(encoding="utf-8")) or {}).get("description")
            if desc and _usable(_clean(desc)):
                return [_clean(desc)], "package.json"
        except (OSError, ValueError):
            pass
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        try:
            import tomllib
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            desc = (data.get("project") or {}).get("description")
            if desc and _usable(_clean(desc)):
                return [_clean(desc)], "pyproject.toml"
        except (OSError, ValueError, ImportError):
            pass
    return None


SOURCES = (from_requirements, from_readme, from_metadata, from_commits)


def discover(root: Path) -> dict | None:
    """A provisional specification for ``root``, or None if nothing states intent.

    Returning None is a real answer. A project that says nowhere what it is
    for cannot have its scope measured, and inventing a specification to fill
    the gap would manufacture the finding.
    """
    root = Path(root)
    for source in SOURCES:
        found = source(root)
        if not found:
            continue
        lines, origin = found
        spec = build_spec("\n".join(lines), name=root.name.replace("-", "_") or "project")
        if not spec["features"]:
            continue
        spec["_derived_from_brief"] = False
        spec["_discovered"] = True
        spec["_discovered_from"] = origin
        return spec
    return None
