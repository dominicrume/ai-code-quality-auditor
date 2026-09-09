"""Cyclomatic complexity, McCabe per function.

See docs/METRICS.md. Python is scored by radon. JavaScript and TypeScript are
scored by a lexical decision-point counter (js_complexity), because radon reads
Python only and every TypeScript function in this study was therefore unscored.
Version 1 preserves the Python-only behaviour that produced the published
figures; version 2 is the default for new audits.

Every reading declares the share of source it could evaluate: a mean over 6% of
a codebase is a different claim from a mean over all of it.
"""
from __future__ import annotations

from radon.complexity import cc_visit

from auditor.analyzers import js_complexity, languages
from auditor.core.logger import get_logger
from auditor.models.audit_result import MetricScore

log = get_logger("complexity_analyzer")

# 1 = Python only, the analyser the published study ran with.
# 2 = adds JavaScript and TypeScript.
DEFAULT_VERSION = 2


def _python_complexities(files: dict[str, str]) -> tuple[list[int], int]:
    scores, loc = [], 0
    for path, content in files.items():
        if not languages.in_languages(path, languages.PYTHON):
            continue
        loc += len(content.splitlines())
        try:
            scores.extend(b.complexity for b in cc_visit(content))
        except (SyntaxError, ValueError) as e:
            log.warning("complexity: skipped %s (%s)", path, e)
    return scores, loc


def _js_complexities(files: dict[str, str]) -> tuple[list[int], int]:
    scores, loc = [], 0
    for path, content in files.items():
        if not languages.in_languages(path, languages.TYPESCRIPT):
            continue
        loc += len(content.splitlines())
        try:
            scores.extend(js_complexity.complexities(content))
        except Exception as e:                      # never fail a whole audit
            log.warning("complexity: skipped %s (%s)", path, e)
    return scores, loc


def analyze(codebase: dict, interaction_log: list[dict], spec: dict,
            version: int = DEFAULT_VERSION) -> MetricScore:
    files = codebase.get("files", {})
    scores, scanned = _python_complexities(files)
    if version >= 2:
        js_scores, js_loc = _js_complexities(files)
        scores += js_scores
        scanned += js_loc

    suffixes = languages.PYTHON if version < 2 else (
        languages.PYTHON + languages.TYPESCRIPT)
    _, total = languages.line_counts(files, suffixes)

    mean = sum(scores) / len(scores) if scores else 0.0
    return MetricScore(
        name="complexity_mean",
        value=mean,
        unit="cc",
        scanned_lines=scanned,
        total_lines=total,
        languages=languages.present(files),
    )
