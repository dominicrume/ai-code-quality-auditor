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
    unparsed: list[str] | None = None
    count: int | None = None
    diagnostics: dict | None = None

    @property
    def applicable(self) -> bool:
        return self.skipped_reason is None

    @property
    def total_note(self) -> str | None:
        """What the value is a density or a mean of.

        A density is unreadable at small sizes: two findings in twelve lines is
        166.67 per thousand, which bands as RISK and tells the reader nothing
        they can act on. The count beside it does.
        """
        if self.count is None or not self.applicable:
            return None
        if self.name == "security_density":
            return f"{self.count} finding{'s' if self.count != 1 else ''}"
        if self.name == "complexity_mean":
            return f"over {self.count} function{'s' if self.count != 1 else ''}"
        if self.name == "duplication_pct":
            return f"{self.count} line{'s' if self.count != 1 else ''}"
        return None

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
    honoured_ignores: bool = True
    outcomes: list[MetricOutcome] = field(default_factory=list)

    @property
    def unparsed_files(self) -> list[str]:
        """Every file an analyser could not parse, named once."""
        seen: list[str] = []
        for o in self.outcomes:
            for f in o.unparsed or []:
                if f not in seen:
                    seen.append(f)
        return seen

    @property
    def worst_band(self) -> Band:
        """The worst reading, where code that would not parse counts as one.

        A file the analysers could not read is an unknown, not a pass, and a
        scan whose only outcome is an unknown must not exit 0 under
        ``--fail-on warn``. Unreadable source therefore raises the floor to a
        warning instead of leaving the default of "good" to speak for it.
        """
        order = {"good": 0, "warn": 1, "critical": 2}
        bands = [o.band for o in self.outcomes if o.band]
        if self.unparsed_files:
            bands.append("warn")
        return max(bands, key=lambda b: order[b]) if bands else "good"

    @property
    def fidelity(self):
        """The per-feature verdict, when a specification was supplied.

        ``FidelityReport`` or None. This is the reading no tool without a
        specification can produce, so it is the one the report leads with.
        """
        for o in self.outcomes:
            report = (o.diagnostics or {}).get("fidelity")
            if report is not None:
                return report
        return None

    @property
    def shape_note(self) -> str | None:
        """The sentence for an agent that built the wrong kind of thing.

        The hallucination count asks what extra was shipped, so it reads 0.00
        when an agent replaces the brief rather than adding to it: in run_001
        an agent given a CLI specification shipped an ETL package with no
        subcommands and scored the same as the conditions that built the CLI
        correctly. The shape detector separates those cases and its verdict was
        being computed and then discarded. Reported only when the detector is
        confident, because a low-margin guess about architecture is worse than
        silence.
        """
        for o in self.outcomes:
            shape = (o.diagnostics or {}).get("shape") or {}
            if shape.get("mismatch") and shape.get("confident"):
                why = ", ".join(shape.get("evidence") or []) or "no matching structure found"
                return (
                    f"you asked for {_SHAPE_WORDS.get(shape['specified_shape'], shape['specified_shape'])}, "
                    f"and what is here looks like {_SHAPE_WORDS.get(shape['built_shape'], shape['built_shape'])} "
                    f"({why}). The scope-drift count is about extra features and cannot see a "
                    f"substitution, so it is not raised by this."
                )
        return None

    @property
    def read_failure_note(self) -> str | None:
        """The sentence that has to appear when source would not parse."""
        files = self.unparsed_files
        if not files:
            return None
        shown = ", ".join(files[:3]) + (f" and {len(files) - 3} more" if len(files) > 3 else "")
        return (
            f"{len(files)} file{'s' if len(files) != 1 else ''} could not be parsed "
            f"({shown}). Nothing is known about {'them' if len(files) != 1 else 'it'}: "
            f"an unreadable file is an unknown, not a pass."
        )

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


# Plain words for the architectural shapes, for a sentence a user reads once.
_SHAPE_WORDS = {
    "cli": "a command-line tool",
    "web_service": "a web service",
    "data_pipeline": "a data pipeline",
    "library": "a library",
    "unknown": "something this tool cannot classify",
}


# label, analyser, and the predicate that decides whether it can run at all
_METRICS = [
    ("security_density", "Security", security_analyzer),
    ("complexity_mean", "Complexity", complexity_analyzer),
    ("duplication_pct", "Duplication", duplication_analyzer),
    ("hallucinations", "Scope drift", hallucination_analyzer),
]


def scan_directory(path: Path, spec: dict | None = None,
                   include_all: bool = False) -> ScanResult:
    """Audit ``path`` in place. No session, no capture, no cleanup.

    By default the walk honours the project's own ``.gitignore`` and skips
    vendored directories, because a reading about someone's repository should
    describe the code they wrote. ``include_all`` measures everything present,
    which is occasionally what an auditor wants and never a sensible default.
    """
    path = Path(path).resolve()
    codebase = load_codebase(path, respect_ignores=not include_all)
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
        honoured_ignores=not include_all,
    )

    for name, label, module in _METRICS:
        reason = _skip_reason(name, result, spec)
        if reason:
            result.outcomes.append(MetricOutcome(name=name, label=label, skipped_reason=reason))
            continue
        score = module.analyze(codebase, [], spec or {})

        # There was source in this metric's languages and none of it parsed.
        # The value is 0.00 because nothing was measured, and 0.00 bands as
        # OK, so the tool would report a clean bill of health for code it
        # could not read. That is the precise failure this instrument was
        # built to detect in other tools, so it is reported as unread rather
        # than banded. It is a skip with a reason, not a score.
        if getattr(score, "read_nothing", False):
            n = len(score.unparsed or [])
            result.outcomes.append(MetricOutcome(
                name=name, label=label, coverage=0.0, languages=score.languages,
                unparsed=score.unparsed,
                skipped_reason=(
                    f"could not read any of it: {n} file{'s' if n != 1 else ''} "
                    f"would not parse" if n else "none of the source could be parsed"),
            ))
            continue

        result.outcomes.append(MetricOutcome(
            name=name, label=label, value=score.value, unit=score.unit,
            band=band_for(name, score.value),
            coverage=score.coverage, languages=score.languages,
            unparsed=score.unparsed, count=score.count,
            diagnostics=getattr(score, "diagnostics", None),
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
        return "nothing yet says what was asked for"
    return None
