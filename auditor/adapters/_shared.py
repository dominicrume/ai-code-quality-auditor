"""Shared helpers for vendor adapters.

Every adapter loader was originally a verbatim copy of the same walk-and-filter.
That duplication (~80 LOC × 4 files) is the bulk of the auditor's SonarCloud
duplication score. Consolidating here drops it sharply without changing
behaviour.

Exports:
  CODE_SUFFIXES   — file extensions the codebase loader ingests
  EXCLUDE_DIRS    — directory names ignored by the codebase loader
  VENDOR_DIRS     — directories holding code the project did not write
  Ignores         — the project's own .gitignore rules
  load_codebase() — walk-and-filter helper used by every vendor adapter
"""
from __future__ import annotations

import json
import re
from pathlib import Path

CODE_SUFFIXES: frozenset[str] = frozenset({
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs",
    ".java", ".rb", ".sql", ".yaml", ".yml", ".toml", ".md",
})

EXCLUDE_DIRS: frozenset[str] = frozenset({
    ".venv", "venv", "env", "__pycache__", "node_modules",
    ".pytest_cache", ".git", "site-packages", "dist", "build",
    ".mypy_cache", ".ruff_cache", "egg-info",
})


# Directories holding code the project did not write, or data it does not ship.
# Counting them is how a tool reports 83% duplication on a repository whose own
# source is barely duplicated: that figure was real, and it described vendored
# trees and frozen research captures rather than anything the user wrote.
VENDOR_DIRS: frozenset[str] = frozenset({
    "vendor", "vendored", "third_party", "thirdparty", "external",
    "bower_components", "jspm_packages", "Pods", "Carthage",
    ".tox", ".nox", ".eggs", "htmlcov", ".cache", ".gradle", ".terraform",
    ".next", ".nuxt", ".svelte-kit", ".parcel-cache", ".turbo",
    "target", "_build", "coverage",
    "fixtures", "__fixtures__", "testdata", "__snapshots__",
    ".ipynb_checkpoints", ".idea", ".vscode",
})


class Ignores:
    """The project's own ignore rules, applied to the walk.

    A repository's ``.gitignore`` is its authoritative statement of what is not
    part of it. Honouring it is not a convenience: reading a frozen data capture
    or a build output and reporting the result as a property of the user's code
    is a false reading, and this instrument exists to catch that class of error
    in other tools.

    Supported, the subset that decides nearly every real case: comments and
    blank lines, a trailing ``/`` for directory-only, a leading or embedded
    ``/`` for a root-anchored pattern, a bare name matching at any depth,
    ``*``, ``?``, ``[...]`` and ``**``, and a leading ``!`` to re-include.
    Not supported: ``.gitignore`` files in subdirectories, and
    ``.git/info/exclude``. Both are stated as limits in ``docs/METRICS.md``
    rather than silently assumed away.
    """

    SOURCES = (".gitignore", ".auditorignore")

    def __init__(self, patterns: list[str] | None = None):
        # (matches the path itself, matches anything below it, dir only, negated)
        self.rules: list[tuple[re.Pattern[str], re.Pattern[str], bool, bool]] = []
        for raw in patterns or []:
            rule = self._compile(raw)
            if rule:
                self.rules.append(rule)

    @classmethod
    def read(cls, root: Path) -> "Ignores":
        """Collect the rules declared at the root of ``root``."""
        patterns: list[str] = []
        for name in cls.SOURCES:
            path = Path(root) / name
            if not path.is_file():
                continue
            try:
                patterns += path.read_text(encoding="utf-8").splitlines()
            except (UnicodeDecodeError, OSError):
                continue        # an unreadable ignore file must not fail a scan
        return cls(patterns)

    @staticmethod
    def _compile(raw: str):
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            return None
        negated = line.startswith("!")
        if negated:
            line = line[1:]
        dir_only = line.endswith("/")
        # A leading slash anchors, and so does an interior one, so both have to
        # be noticed before the slashes are stripped off: reading "/build/" as
        # a bare name would have it match src/build too, which git does not.
        anchored = line.startswith("/") or "/" in line.strip("/")
        line = line.strip("/")
        if not line:
            return None
        prefix = "" if anchored else r"(?:.*/)?"
        body = f"{prefix}{Ignores._translate(line)}"
        return re.compile(f"^{body}$"), re.compile(f"^{body}/.*$"), dir_only, negated

    @staticmethod
    def _translate(pattern: str) -> str:
        """Glob to regex, where ``*`` stops at a slash and ``**`` does not."""
        out, i = [], 0
        while i < len(pattern):
            c = pattern[i]
            if c == "*":
                if pattern[i:i + 2] == "**":
                    i += 2
                    if pattern[i:i + 1] == "/":
                        i += 1
                        out.append("(?:.*/)?")   # "**/" also matches no directory
                    else:
                        out.append(".*")
                    continue
                out.append("[^/]*")
            elif c == "?":
                out.append("[^/]")
            elif c == "[":
                end = pattern.find("]", i)
                if end == -1:
                    out.append(re.escape(c))
                else:
                    out.append(pattern[i:end + 1])
                    i = end + 1
                    continue
            else:
                out.append(re.escape(c))
            i += 1
        return "".join(out)

    def ignored(self, rel: str, is_dir: bool = False) -> bool:
        """True when the project's own rules exclude ``rel``.

        Later rules win, which is what lets a ``!`` line re-include a path an
        earlier pattern excluded. A directory rule excludes everything beneath
        the directory, which is why every rule carries a second pattern.
        """
        verdict = False
        for exact, under, dir_only, negated in self.rules:
            hit = under.match(rel) or ((not dir_only or is_dir) and exact.match(rel))
            if hit:
                verdict = not negated
        return verdict

    def __bool__(self) -> bool:
        return bool(self.rules)


def _excluded(rel_parts: tuple[str, ...], vendor: bool = False) -> bool:
    names = EXCLUDE_DIRS | VENDOR_DIRS if vendor else EXCLUDE_DIRS
    return any(part in names or part.endswith(".egg-info") for part in rel_parts)


def iter_source_files(work_dir: Path, respect_ignores: bool = False):
    """Yield ``(relative_posix_path, absolute_path)`` for every scorable file.

    The single definition of "a file this instrument looks at". The codebase
    loader and the watcher both consume it, so a file can never be measured
    but not watched, or the reverse.

    ``respect_ignores`` additionally applies the project's own ``.gitignore``
    and the vendored-directory list. It defaults to **off** so that the
    experiment path -- ``auditor run`` and ``auditor experiment``, which
    produced the figures in Table 4.1 -- walks exactly the files it always
    walked. The user-facing commands (``scan``, ``watch``, ``live``) turn it
    on, because a reading about a user's repository should describe their code
    and not the dependencies and captures sitting beside it.
    """
    work_dir = Path(work_dir)
    ignores = Ignores.read(work_dir) if respect_ignores else Ignores()
    for path in sorted(work_dir.rglob("*")):
        if not path.is_file() or path.name == "manifest.json":
            continue
        if path.suffix not in CODE_SUFFIXES:
            continue
        rel = path.relative_to(work_dir)
        if _excluded(rel.parts, vendor=respect_ignores):
            continue
        if ignores and ignores.ignored(rel.as_posix()):
            continue
        yield rel.as_posix(), path


def load_codebase(work_dir: Path, respect_ignores: bool = False) -> dict:
    """Walk ``work_dir``, return the capture-contract codebase dict.

    Skips the EXCLUDE_DIRS set so transitive deps (.venv, node_modules,
    site-packages, etc.) don't inflate any downstream metric. With
    ``respect_ignores`` it also skips whatever the project itself ignores;
    see ``iter_source_files`` for why that is not the default.
    """
    work_dir = Path(work_dir)
    if not work_dir.is_dir():
        raise FileNotFoundError(f"work_dir not found: {work_dir}")

    files: dict[str, str] = {}
    for rel, path in iter_source_files(work_dir, respect_ignores=respect_ignores):
        try:
            files[rel] = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # binary or vanished mid-walk — skip, never crash a scan

    manifest_path = work_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else []
    return {"files": files, "manifest": manifest}
