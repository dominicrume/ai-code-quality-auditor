"""Security vulnerability density — local Bandit scan of the captured codebase.

Why local Bandit instead of SonarCloud:
  The original SonarCloud integration queries one shared project key per
  spec, which means every condition gets the same numerator (the issues
  found in the host repo) divided by a different LOC — a structurally
  broken metric. Switching to a local scanner means each condition's
  captured codebase is scanned in isolation, producing an honest
  per-condition score with zero external infrastructure dependency.

What is counted:
  Every Bandit issue is mapped to a CWE id via Bandit's built-in metadata.
  We count issues whose CWE id is non-null, which is the same OWASP/CWE
  framing used in the original SonarQube contract (see docs/METRICS.md).

Languages:
  Bandit reads Python and nothing else. On this study's own captures that
  left the majority of the produced code unscanned and returned 0.00 for a
  TypeScript-dominated condition, which reads as "secure" and means "not
  read" (Erratum 001, section 5.2). Version 2 of the metric adds a curated,
  CWE-tagged JavaScript and TypeScript ruleset, and every reading now
  declares the share of source it could evaluate.

  Version 1 is retained so the study's published figures remain
  reproducible: `analyze(..., version=1)` is Python-only and returns exactly
  what data/reports/main_001.csv records.

Output: per 1,000 LOC density (preserves the unit used in METRICS.md).
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from auditor.analyzers import js_security, languages
from auditor.models.audit_result import MetricScore

# 1 = Python only, the analyser the published study ran with.
# 2 = adds JavaScript and TypeScript. Default for new audits.
DEFAULT_VERSION = 2


def _write_codebase(codebase: dict, dest: Path) -> int:
    """Materialise the in-memory codebase to disk; return python LOC."""
    loc = 0
    for rel, content in codebase.get("files", {}).items():
        if not rel.endswith(".py"):
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        loc += len(content.splitlines())
    return loc


def _run_bandit(scan_dir: Path) -> list[dict]:
    """Run Bandit and parse its JSON output. Empty list if no python files."""
    if not any(scan_dir.rglob("*.py")):
        return []
    proc = subprocess.run(
        ["bandit", "-r", str(scan_dir), "-f", "json", "-q"],
        capture_output=True, text=True, check=False,
    )
    if not proc.stdout.strip():
        return []
    data = json.loads(proc.stdout)
    return data.get("results", [])


def _is_test_file(rel: str) -> bool:
    """True for files whose purpose is testing."""
    name = rel.rsplit("/", 1)[-1]
    return (
        name.startswith("test_")
        or name.endswith("_test.py")
        or name == "conftest.py"
        or "/tests/" in f"/{rel}"
        or rel.startswith("tests/")
    )


def _counts(issues: list[dict], scan_dir: Path) -> list[dict]:
    """CWE-tagged issues, excluding assertions inside test files.

    B101 fires on every `assert`, because assertions are removed when Python
    runs with -O and a production check would silently vanish. In a test file
    the assertion *is* the test: flagging it measures how thoroughly a
    codebase is tested and reports it as a security score. On this repository
    that single rule accounted for 291 findings and inflated the density
    tenfold, so a well-tested submission would score worse than an untested
    one — the opposite of what the metric is for.
    """
    kept = []
    for issue in issues:
        if not (issue.get("issue_cwe") or {}).get("id"):
            continue
        rel = str(Path(issue["filename"]).relative_to(scan_dir)) \
            if str(issue["filename"]).startswith(str(scan_dir)) else issue["filename"]
        if issue.get("test_id") == "B101" and _is_test_file(rel.replace("\\", "/")):
            continue
        kept.append(issue)
    return kept


def _scan_javascript(files: dict[str, str]) -> tuple[list[dict], int]:
    """Findings and lines read across the JS/TS files, test files excluded."""
    findings, loc = [], 0
    for path, content in files.items():
        if not languages.in_languages(path, languages.TYPESCRIPT):
            continue
        if _is_test_file(path):
            continue
        loc += len(content.splitlines())
        findings += js_security.scan(path, content)
    return findings, loc


def analyze(codebase: dict, interaction_log: list[dict], spec: dict,
            version: int = DEFAULT_VERSION) -> MetricScore:
    files = codebase.get("files", {})
    with tempfile.TemporaryDirectory() as tmp:
        scan_dir = Path(tmp) / "code"
        scan_dir.mkdir()
        py_loc = _write_codebase(codebase, scan_dir)
        issues = _counts(_run_bandit(scan_dir), scan_dir)

    js_issues, js_loc = ([], 0) if version < 2 else _scan_javascript(files)
    suffixes = languages.PYTHON if version < 2 else (
        languages.PYTHON + languages.TYPESCRIPT)
    _, total = languages.line_counts(files, suffixes)

    scanned = py_loc + js_loc
    density = (len(issues) + len(js_issues)) / max(scanned, 1) * 1000
    return MetricScore(
        name="security_density",
        value=density,
        unit="per_kloc",
        scanned_lines=scanned,
        total_lines=total,
        languages=languages.present(files),
    )
