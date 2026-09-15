"""Zero-ceremony audit of any directory.

The experiment path (``auditor run`` / ``auditor experiment``) exists to
serve a controlled study: fixed spec, isolated workspace, one condition per
capture. That rigour is right for the dissertation and wrong as a front
door — it forces a user to decide, before writing a line, that this folder
is The Session.

``scan`` inverts that. Point it at a directory that already exists, however
the code got there, and it reports what it can actually measure.

The design rule that matters: **a metric is reported only where it applies.**
Bandit and radon read Python; on a TypeScript project they will happily
return 0.00, and printing that as a score would be a lie of exactly the kind
this instrument exists to catch. Inapplicable metrics are reported as
``n/a`` with the reason, never as a zero.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from auditor.adapters._shared import load_codebase
from auditor.analyzers import (
    complexity_analyzer,
    duplication_analyzer,
    hallucination_analyzer,
    security_analyzer,
)
from auditor.analyzers import languages
from auditor.core.calibration import Band, band_for


@dataclass
class MetricOutcome:
    """One metric's result, or the reason it could not be computed."""
    name: str
    label: str
    value: float | None = None
    unit: str = ""
    band: Band | None = None
    skipped_reason: str | None = None
    details: list[str] | None = None
    coverage: float | None = None
    languages: list[str] | None = None

    @property
    def applicable(self) -> bool:
        return self.skipped_reason is None

    @property
    def caveat(self) -> str | None:
        """A short warning when the reading rests on part of the codebase.

        A density computed over a fraction of a project reads as a clean bill of
        health unless the tool says otherwise. This is the sentence that says
        otherwise.
        """
        if self.coverage is None or self.coverage >= 0.995:
            return None
        return f"read {self.coverage:.0%} of the source"


@dataclass
class ScanResult:
    path: Path
    file_count: int = 0
    total_loc: int = 0
    python_files: int = 0
    readable_files: int = 0
    python_loc: int = 0
    spec_name: str | None = None
    outcomes: list[MetricOutcome] = field(default_factory=list)

    @property
    def worst_band(self) -> Band:
        order = {"good": 0, "warn": 1, "critical": 2}
        bands = [o.band for o in self.outcomes if o.band]
        return max(bands, key=lambda b: order[b]) if bands else "good"

    @property
    def coverage_note(self) -> str | None:
        """A plain-language warning when a metric read only part of the source.

        Security and complexity now read Python, JavaScript and TypeScript. Any
        other language is still unread, and a density computed over the readable
        fraction is not a clean bill of health for the rest. This says so in the
        terms a reader needs: which metric, and how much it saw.
        """
        partial = [
            (o.label, o.coverage) for o in self.outcomes
            if o.applicable and o.coverage is not None and o.coverage < 0.995
        ]
        if not partial:
            return None
        worst = min(c for _, c in partial)
        names = ", ".join(sorted({label for label, _ in partial}))
        return (
            f"{names} read {worst:.0%} of your source. The rest is in a language "
            f"this tool does not scan yet, so treat the score as covering the "
            f"part it could read, not the whole project."
        )


# label, analyser, and the predicate that decides whether it can run at all
_METRICS = [
    ("security_density", "Security", security_analyzer),
    ("complexity_mean", "Complexity", complexity_analyzer),
    ("duplication_pct", "Duplication", duplication_analyzer),
    ("hallucinations", "Scope drift", hallucination_analyzer),
]


def scan_directory(path: Path, spec: dict | None = None) -> ScanResult:
    """Audit ``path`` in place. No session, no capture, no cleanup."""
    path = Path(path).resolve()
    codebase = load_codebase(path)
    files = codebase.get("files", {})

    result = ScanResult(
        path=path,
        file_count=len(files),
        total_loc=sum(len(c.splitlines()) for c in files.values()),
        python_files=sum(1 for f in files if f.endswith(".py")),
        readable_files=sum(
            1 for f in files
            if languages.in_languages(f, languages.PYTHON + languages.TYPESCRIPT)),
        python_loc=sum(len(c.splitlines()) for f, c in files.items() if f.endswith(".py")),
        spec_name=(spec or {}).get("name"),
    )

    for name, label, module in _METRICS:
        reason = _skip_reason(name, result, spec)
        if reason:
            result.outcomes.append(MetricOutcome(name=name, label=label, skipped_reason=reason))
            continue
        score = module.analyze(codebase, [], spec or {})
        result.outcomes.append(MetricOutcome(
            name=name, label=label, value=score.value, unit=score.unit,
            band=band_for(name, score.value),
            coverage=score.coverage, languages=score.languages,
            # Security names its medium and high findings. Scope-drift details
            # stay out of the scan: the live page would offer to strip them.
            details=score.details if name == "security_density" else None,
        ))

    # correction_freq counts backspaces per thousand keystrokes, so it needs an
    # interaction log captured while the code was being written. A directory has
    # no such thing and never will: scan reads what was produced, not how.
    #
    # The hint used to name `auditor session`, which is not a command -- a user
    # following it got "Error: No such command". Only the adapters produce an
    # interaction log, from a captures directory, so point at the command that
    # reads them.
    result.outcomes.append(MetricOutcome(
        name="correction_freq", label="Rework",
        skipped_reason="not measurable from a directory; needs a captured "
                       "session (auditor run --workflow ...)",
    ))

    return result


def _skip_reason(metric: str, r: ScanResult, spec: dict | None) -> str | None:
    if r.file_count == 0:
        return "no analysable files found"
    if metric in ("security_density", "complexity_mean") and r.readable_files == 0:
        return "no Python, JavaScript or TypeScript files to analyse"
    if metric == "hallucinations" and not spec:
        return "needs --spec to know what was asked for"
    return None
