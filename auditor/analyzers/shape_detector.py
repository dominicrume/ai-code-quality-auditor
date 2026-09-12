"""Architectural-shape detection for the scope-drift metric.

Why this exists
---------------
`manifest_deriver._evidence` credits a spec feature when its terminal token
appears anywhere in the codebase. That is blind to *where* the token appears,
and the run_001 captures show why this matters. Given the `internal_tool_cli`
specification, `replit_agent` shipped an ETL package (`pipeline/ingest.py`,
`pipeline/load.py`, `pipeline/report.py`) and no subcommands. Token matching
nevertheless credited four of the six CLI features as implemented, because the
words ``add``, ``list``, ``validate`` and ``help`` occur inside pipeline code
and argparse help strings.

The agent did not implement the CLI. It implemented something else that
contains those words. The dissertation names this gap directly (§6.4): a
spec-token appearing inside the wrong architectural shape is a hallucination,
not an implementation.

What this module adds
---------------------
1. ``specified_shape(spec)`` — the shape the brief asks for.
2. ``detect_shape(codebase)`` — the shape actually built, with the evidence
   that decided it and the margin over the runner-up.
3. ``classify_surface(codebase)`` — separates *capabilities* a user can invoke
   (routes, subcommands) from *scaffolding* that is internal organisation
   (generated clients, connection pools, build config).

(3) exists because the two-rater validation found a genuine construct boundary
at item_16, not rater error: a monorepo implemented its pipeline spec exactly
in seven Python modules and also shipped four TypeScript packages nobody asked
for. One rater read those as unrequested capabilities, the other as vendor
scaffolding, and both readings follow the written protocol because the protocol
does not settle the question. This module does not settle it either — it makes
the distinction explicit and lets the caller declare which side is counted,
so the choice is recorded rather than made by accident.

On validation
-------------
The behaviour here is derived from the protocol, not fitted to the rater
labels. It reproduces the known item_19 finding, but that is a smoke test and
**not** validation: these are the captures that motivated the work. Establishing
that shape detection agrees with human judgement requires a fresh sample and
raters who have not seen these items, exactly as `docs/KAPPA_RESULTS_001.md`
argues for the repaired hallucination detector.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

CLI = "cli"
WEB_SERVICE = "web_service"
DATA_PIPELINE = "data_pipeline"
LIBRARY = "library"
UNKNOWN = "unknown"

# --- structural signals -----------------------------------------------------
# Each entry is (compiled pattern, weight, human-readable label). Weights are
# ordinal, not calibrated: a declaration that can only exist in one shape
# (registering a subcommand, binding a port) outweighs an import, which can
# appear incidentally in any shape.

_SIGNALS: dict[str, list[tuple[re.Pattern[str], int, str]]] = {
    CLI: [
        (re.compile(r"\badd_parser\s*\(", re.I), 3, "argparse subcommand registered"),
        (re.compile(r"@\w+\.command\s*\(", re.I), 3, "click/typer command registered"),
        (re.compile(r"\bargparse\.ArgumentParser\s*\(", re.I), 2, "argparse parser constructed"),
        (re.compile(r"^\s*import\s+(?:argparse|click|typer)\b", re.I | re.M), 1, "cli library imported"),
        (re.compile(r"\bconsole_scripts\b|\[project\.scripts\]", re.I), 3, "console entry point declared"),
        (re.compile(r"\bsys\.argv\b"), 1, "argv read directly"),
    ],
    WEB_SERVICE: [
        (re.compile(r"@\w+\.(?:get|post|put|delete|patch)\s*\(", re.I), 3, "route decorator declared"),
        (re.compile(r"\b(?:app|router|api)\.(?:get|post|put|delete|patch)\s*\(", re.I), 3, "route handler registered"),
        (re.compile(r"\b(?:FastAPI|Flask)\s*\(", re.I), 3, "web framework instantiated"),
        (re.compile(r"\bexpress\s*\(\s*\)"), 3, "express app created"),
        (re.compile(r"\bapp\.listen\s*\(|\buvicorn\.run\s*\(|\bapp\.run\s*\("), 3, "server bound to a port"),
        (re.compile(r"^\s*(?:from|import)\s+(?:fastapi|flask|django)\b", re.I | re.M), 1, "web framework imported"),
    ],
    DATA_PIPELINE: [
        (re.compile(r"\bdef\s+run_pipeline\b|\bclass\s+\w*Pipeline\b", re.I), 3, "pipeline entry point defined"),
        (re.compile(r"(?:^|/)pipeline/", re.I | re.M), 2, "pipeline package present"),
        (re.compile(r"\bdef\s+(?:ingest|extract|transform|load)\b", re.I), 2, "ETL stage function defined"),
        (re.compile(r"\b(?:apscheduler|airflow|prefect|dagster|schedule)\b", re.I), 2, "scheduler library present"),
        (re.compile(r"\bcron\b|\bschedule\.every\b", re.I), 1, "scheduled execution referenced"),
        (re.compile(r"\bpd\.read_csv\b|\bto_sql\b|\bbulk_insert\b", re.I), 1, "bulk data movement"),
    ],
    LIBRARY: [
        (re.compile(r"^\s*__all__\s*=", re.M), 2, "public API declared via __all__"),
        (re.compile(r'"(?:main|module|exports)"\s*:', re.I), 1, "package entry field declared"),
        (re.compile(r"\bexport\s+(?:function|const|class|default)\b"), 1, "module exports"),
    ],
}

# Files that are packaging, config or documentation rather than deliverable
# behaviour. Their presence never decides a shape.
_NON_SOURCE = re.compile(
    r"(?:^|/)(?:package(?:-lock)?\.json|tsconfig\.json|requirements\.txt|"
    r"pyproject\.toml|\.env\S*|README[^/]*|LICENSE|Dockerfile|[^/]*\.ya?ml|[^/]*\.md)$",
    re.I,
)

# Paths that read as internal organisation rather than a user-facing capability.
_SCAFFOLDING_PATH = re.compile(
    r"(?:^|/)(?:lib|libs|packages|shared|common|internal|generated|codegen|"
    r"node_modules|dist|build|migrations|config)(?:/|$)",
    re.I,
)


@dataclass
class ShapeReport:
    """What was built, how confidently, and on what evidence."""

    shape: str
    scores: dict[str, int]
    evidence: dict[str, list[str]] = field(default_factory=dict)

    @property
    def margin(self) -> int:
        """Points between the winner and the runner-up.

        A margin of 0 means two shapes are equally supported and the verdict
        should be treated as unresolved rather than as a finding.
        """
        ranked = sorted(self.scores.values(), reverse=True)
        if len(ranked) < 2:
            return ranked[0] if ranked else 0
        return ranked[0] - ranked[1]

    @property
    def confident(self) -> bool:
        return self.shape != UNKNOWN and self.margin >= 2


def _source_blob(codebase: dict) -> str:
    files = codebase.get("files", {}) or {}
    parts = []
    for path, content in files.items():
        if _NON_SOURCE.search(path):
            continue
        parts.append(f"# path: {path}\n{content}")
    return "\n".join(parts)


def detect_shape(codebase: dict) -> ShapeReport:
    """Infer the architectural shape actually built."""
    blob = _source_blob(codebase)
    paths = "\n".join(codebase.get("files", {}) or {})
    haystack = f"{paths}\n{blob}"

    scores: dict[str, int] = {}
    evidence: dict[str, list[str]] = {}
    for shape, signals in _SIGNALS.items():
        total = 0
        seen: list[str] = []
        for pattern, weight, label in signals:
            if pattern.search(haystack):
                total += weight
                seen.append(label)
        scores[shape] = total
        if seen:
            evidence[shape] = seen

    best = max(scores, key=lambda s: scores[s])
    if scores[best] == 0:
        return ShapeReport(UNKNOWN, scores, evidence)
    return ShapeReport(best, scores, evidence)


def specified_shape(spec: dict) -> str:
    """Infer the shape the specification asks for.

    Reads the feature ids first (they are namespaced by the spec author, e.g.
    ``cli.export``) and falls back to the descriptions, which is where a brief
    states the invocation form (``tool init <name>``, ``GET /courses``).
    """
    ids = " ".join(f.get("id", "") for f in spec.get("features", []) or []).lower()
    text = " ".join(f.get("description", "") for f in spec.get("features", []) or []).lower()
    name = str(spec.get("name", "")).lower()

    if re.search(r"\bcli\.|\bcommand\.", ids) or "cli" in name:
        return CLI
    if re.search(r"\b(?:route|endpoint|api)\.", ids) or re.search(r"\bget /|\bpost /|\bendpoint\b", text):
        return WEB_SERVICE
    if re.search(r"\b(?:pipeline|etl|ingest|scheduler)\b", f"{ids} {name}"):
        return DATA_PIPELINE
    if re.search(r"`\w+ \w+", text) and "tool " in text:
        return CLI
    # A brief that gives named actors session-scoped actions is describing a
    # service, whatever transport it names. `agent_education_system` is the
    # case in point: `auth.register` / `auth.login` / "authenticated user can
    # list…" is a web service even though the word never appears.
    if re.search(r"\bauth\.|\bsession\b|\blog in\b|\blogin\b|\bsign in\b", f"{ids} {text}"):
        return WEB_SERVICE
    if re.search(r"\bcrud\b|\bauthenticat\w*\b|\bweb app\b", text):
        return WEB_SERVICE
    return UNKNOWN


def classify_surface(codebase: dict) -> dict[str, list[str]]:
    """Split produced files into deliverable capability vs internal scaffolding.

    The protocol does not settle whether scaffolding that ships in the
    deliverable counts as scope drift (see item_16 in the κ study). This
    function only makes the two visible; the caller decides which it counts.
    """
    capability: list[str] = []
    scaffolding: list[str] = []
    for path in (codebase.get("files", {}) or {}):
        if _NON_SOURCE.search(path):
            continue
        (scaffolding if _SCAFFOLDING_PATH.search(path) else capability).append(path)
    return {"capability": sorted(capability), "scaffolding": sorted(scaffolding)}


def shape_mismatch(spec: dict, codebase: dict) -> dict:
    """Compare the shape asked for with the shape built.

    Returns ``mismatch: True`` only when both shapes are known and the built
    shape is confidently something else. An unresolved verdict is reported as
    unresolved rather than forced into a finding, because a metric that
    guesses under uncertainty is worse than one that abstains.
    """
    want = specified_shape(spec)
    report = detect_shape(codebase)

    mismatch = (
        want != UNKNOWN
        and report.shape != UNKNOWN
        and report.shape != want
        and report.confident
    )
    return {
        "specified_shape": want,
        "built_shape": report.shape,
        "mismatch": mismatch,
        "confident": report.confident,
        "margin": report.margin,
        "scores": report.scores,
        "evidence": report.evidence.get(report.shape, []),
    }
