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
import sys
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


# Distinguishable from "no file failed to parse", which is an empty list, and
# from a list of files that did. Identity is the test, so a real file named
# like this cannot be mistaken for it.
_UNAVAILABLE: list[str] = ["<bandit unavailable>"]


def _run_bandit(scan_dir: Path) -> tuple[list[dict], list[str]]:
    """Run Bandit; return its findings and the files it could not parse.

    Bandit reports an unparseable file in ``errors`` and still counts its lines
    in ``metrics``. Taking only ``results`` therefore produced a density of 0.00
    over source that was never read, which bands as OK. The error list is the
    authoritative statement of what Bandit failed on, so it is carried out of
    here rather than inferred.
    """
    if not any(scan_dir.rglob("*.py")):
        return [], []
    # `sys.executable -m bandit`, never a bare `bandit`.
    #
    # A bare name is resolved through PATH, and a console script installed into
    # a virtual environment is not on PATH unless that environment has been
    # activated. `env/bin/pip install ai-code-quality-auditor` followed by
    # `env/bin/auditor scan .` is a correct installation and the documented
    # one, and it crashed the whole scan with FileNotFoundError. Naming the
    # running interpreter uses the environment the auditor is already in.
    # Reported from the field; see FINDING_009.
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "bandit", "-r", str(scan_dir), "-f", "json", "-q"],
            capture_output=True, text=True, check=False,
        )
    except (OSError, ValueError):
        # Bandit is a declared dependency, so this is an environment that has
        # been taken apart. A security reading is still owed for the languages
        # that do not need it, and a tool that dies on the whole scan because
        # one analyser is missing has turned a partial answer into no answer.
        return [], _UNAVAILABLE
    if proc.returncode != 0 and not proc.stdout.strip():
        # Bandit exits non-zero and silent when the module is absent. Same
        # situation as above, reached by a different route.
        return [], _UNAVAILABLE
    if not proc.stdout.strip():
        return [], []
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return [], []
    failed = []
    for err in data.get("errors") or []:
        name = str(err.get("filename") or "")
        try:
            name = str(Path(name).resolve().relative_to(scan_dir.resolve()))
        except (ValueError, OSError):
            pass
        failed.append(name.replace("\\", "/"))
    return data.get("results", []), failed


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
        rel = rel.replace("\\", "/")
        if issue.get("test_id") == "B101" and _is_test_file(rel):
            continue
        # the scan ran in a temporary directory; report the project's own path
        kept.append({**issue, "filename": rel})
    return kept


_SEVERITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


def _severity(finding: dict) -> str:
    return str(finding.get("issue_severity") or "UNKNOWN").upper()


def _review_details(findings: list[dict]) -> list[str] | None:
    """Name every medium- or high-severity finding, whatever the density.

    Density is the study's metric and its bands are calibrated for it: the
    warning starts at 50 findings per thousand lines. A field audit of a
    4,000-line health prototype (docs/FIELD_REPORT_001.md) had one real medium
    finding, a URL opener that would accept file: paths, under a verdict of
    OK. One serious finding is not a density problem, so it is named beside
    the score rather than folded into it. The value and the band are unchanged.
    """
    serious = [f for f in findings if _severity(f) in ("HIGH", "MEDIUM")]
    if not serious:
        return None
    tally: dict[str, int] = {}
    for f in findings:
        tally[_severity(f)] = tally.get(_severity(f), 0) + 1
    order = sorted(tally, key=lambda s: _SEVERITY_ORDER.get(s, 3))
    noun = "finding" if len(findings) == 1 else "findings"
    lines = [f"{len(findings)} {noun}: " + ", ".join(f"{tally[s]} {s.lower()}" for s in order)]
    for f in sorted(serious, key=lambda f: (_SEVERITY_ORDER.get(_severity(f), 3),
                                           str(f.get("filename", "")), f.get("line_number") or 0)):
        cwe = (f.get("issue_cwe") or {}).get("id")
        lines.append(f"{_severity(f)} {f.get('test_id', '')}"
                     + (f" CWE-{cwe}" if cwe else "")
                     + f" {f.get('filename', '?')}:{f.get('line_number', '?')}"
                     + f" · {str(f.get('issue_text', '')).strip()[:90]}")
    return lines


def _diagnostics(tally: dict[str, int], bandit_missing: bool) -> dict | None:
    """What the reader needs beside the number, if anything."""
    out: dict = {}
    if tally:
        out["severity"] = tally
    if bandit_missing:
        out["unavailable"] = (
            "Python was not analysed: bandit could not be run in this "
            "environment. Reinstall with `pip install ai-code-quality-auditor` "
            "to restore it. Any JavaScript or TypeScript reading above is "
            "unaffected.")
    return out or None


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
        raw_issues, unparsed = _run_bandit(scan_dir)
        issues = _counts(raw_issues, scan_dir)

        # Bandit could not be run at all. Every Python line is then a line
        # nothing read, and saying so is the whole point: a density computed
        # over code that was never scanned is the "0.00 OK" this instrument
        # exists to catch. The JavaScript reading is still owed and still good.
        bandit_missing = unparsed is _UNAVAILABLE
        if bandit_missing:
            unparsed = sorted(f for f in (codebase.get("files") or {})
                              if f.endswith(".py"))
            py_loc = 0
        else:
            # Lines Bandit could not parse are not lines Bandit read.
            py_loc -= sum(len((codebase.get("files", {}).get(f) or "").splitlines())
                          for f in unparsed)

    js_issues, js_loc = ([], 0) if version < 2 else _scan_javascript(files)
    suffixes = languages.PYTHON if version < 2 else (
        languages.PYTHON + languages.TYPESCRIPT)
    _, total = languages.line_counts(files, suffixes)

    scanned = max(py_loc + js_loc, 0)
    density = (len(issues) + len(js_issues)) / max(scanned, 1) * 1000

    # The tally as data, not only inside the first details string. The band
    # needs it: a density divides by size, so a large codebase is rewarded for
    # being large, and severity is the thing that division throws away.
    # See FINDING_005.
    tally: dict[str, int] = {}
    for f in issues + js_issues:
        tally[_severity(f)] = tally.get(_severity(f), 0) + 1

    return MetricScore(
        name="security_density",
        value=density,
        unit="per_kloc",
        details=_review_details(issues + js_issues),
        scanned_lines=scanned,
        total_lines=total,
        languages=languages.present(files),
        unparsed=sorted(unparsed) or None,
        count=len(issues) + len(js_issues),
        diagnostics=_diagnostics(tally, bandit_missing),
    )
