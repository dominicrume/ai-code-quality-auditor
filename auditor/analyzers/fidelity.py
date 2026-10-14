"""Specification fidelity: was each thing that was asked for actually built?

Why this exists
---------------
The scope-drift count answers "did anything extra appear?". That is half a
question. The half every user has is "is anything missing?", and the
instrument never asked it: ``manifest_deriver.derive`` computed the list of
implemented features and nothing consumed it.

Missing work is also the failure mode that matters most in the field. An agent
that does four of five things and reports success is the common case, and no
tool built on linting can see it, because none of them knows what was asked.

What a verdict can be
---------------------
``delivered``    a definition exists that a user can reach: a registered
                 subcommand, or a route.
``unreachable``  something with the right name is defined, but only as an
                 internal function, class or export, while the specification
                 asks for a command-line tool or a service. The code is there
                 and nobody can invoke it. This is a distinct finding from
                 absence and more useful than either "built" or "missing".
``not_found``    nothing in the codebase declares it.

A fourth line is not a feature verdict at all: ``extras`` are parts of the
surface that no feature asked for, which is what the published scope-drift
count has always measured.

On evidence
-----------
Every verdict cites a file and a line, or says plainly that it has none. A
claim about delivery with nothing to point at is the thing this module was
written to replace.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from auditor.analyzers import definitions as defs
from auditor.analyzers.shape_detector import specified_shape

# Shapes whose whole point is a surface a user invokes. For a library, an
# exported function *is* the deliverable, so "unreachable" cannot apply.
_SURFACE_SHAPES = frozenset({"cli", "web_service"})

DELIVERED = "delivered"
UNREACHABLE = "unreachable"
NOT_FOUND = "not_found"

_MARKS = {DELIVERED: "✓", UNREACHABLE: "!", NOT_FOUND: "✗"}


@dataclass
class FeatureVerdict:
    feature_id: str
    description: str
    status: str
    where: str | None = None
    evidence: str | None = None

    @property
    def mark(self) -> str:
        return _MARKS[self.status]

    @property
    def name(self) -> str:
        """The whole id, which is what the spec file calls this feature.

        Not the terminal segment: an id derived from a sentence reads in
        English order, so `add.item` shown as `item` names the object and
        hides the action, which is the part somebody has to go and build.
        """
        return self.feature_id

    @property
    def label(self) -> str:
        """What to show a person.

        The id is a key: stable, matchable, and written for the matcher. It is
        made by slugging the first few meaningful words, so "Notify the
        assessor when a claim is submitted" becomes `notify.assessor.when`,
        which is accurate, unreadable, and the wrong thing to project onto a
        wall. The sentence somebody actually wrote is the label; the id stays
        in the file and in the JSON, where a machine reads it.
        """
        return self.description or self.feature_id

    def short(self, width: int = 46) -> str:
        """The label, cut to fit a column without cutting mid-word."""
        text = self.label
        if len(text) <= width:
            return text
        cut = text[:width].rsplit(" ", 1)[0]
        return (cut or text[:width]).rstrip(" ,;:") + "…"

    def reason(self) -> str:
        if self.status == DELIVERED:
            return self.evidence or "found"
        if self.status == UNREACHABLE:
            return f"{self.evidence} exists, but nothing exposes it"
        return "not found"


@dataclass
class Extra:
    """A piece of surface nobody asked for."""
    name: str
    kind: str
    where: str


@dataclass
class FidelityReport:
    verdicts: list[FeatureVerdict] = field(default_factory=list)
    extras: list[Extra] = field(default_factory=list)
    shape: dict | None = None

    @property
    def total(self) -> int:
        return len(self.verdicts)

    @property
    def delivered(self) -> list[FeatureVerdict]:
        return [v for v in self.verdicts if v.status == DELIVERED]

    @property
    def missing(self) -> list[FeatureVerdict]:
        return [v for v in self.verdicts if v.status == NOT_FOUND]

    @property
    def unreachable(self) -> list[FeatureVerdict]:
        return [v for v in self.verdicts if v.status == UNREACHABLE]

    @property
    def headline(self) -> str:
        return f"{len(self.delivered)} of {self.total} delivered"

    @property
    def completeness(self) -> float | None:
        """Share of specified features that were delivered, 0-100."""
        if not self.total:
            return None
        return round(100.0 * len(self.delivered) / self.total, 2)


def assess(spec: dict, codebase: dict) -> FidelityReport:
    """Judge every specified feature against what the codebase declares."""
    features = [f for f in (spec or {}).get("features") or [] if f.get("id")]
    index = defs.index(codebase)
    shape = specified_shape(spec or {})

    # Does delivery here mean something a user can invoke? The specification
    # says so when it names a shape. A brief written as a list of features
    # often names none, and in that case the project's own delivered features
    # answer it: if any of them arrived as a subcommand or a route, that is
    # what delivery looks like in this codebase, and a feature with only an
    # internal definition is unreachable rather than done. Inferred from the
    # evidence present, never assumed.
    wants_surface = shape in _SURFACE_SHAPES or any(
        d.is_surface and any(defs.matches(d, f["id"]) for f in features)
        for d in index
    )

    report = FidelityReport()
    claimed: set[tuple[str, str]] = set()      # definitions a feature accounted for

    for feature in features:
        fid = feature["id"]
        hits = [d for d in index if defs.matches(d, fid)]
        surface = [d for d in hits if d.is_surface]
        internal = [d for d in hits if not d.is_surface]

        if surface:
            best = surface[0]
            status = DELIVERED
        elif internal and not wants_surface:
            # For a library or a pipeline, a defined function is the delivery.
            best = internal[0]
            status = DELIVERED
        elif internal:
            best = internal[0]
            # Only call it unreachable when nothing calls it. A helper invoked
            # by a route is wired up and working, and telling a team otherwise
            # costs more than missing a finding would: the verdict needs
            # evidence of absence, not absence of evidence.
            invoked = any(defs.is_invoked(d.name, codebase) for d in internal)
            status = DELIVERED if invoked else UNREACHABLE
        else:
            best = None
            status = NOT_FOUND

        report.verdicts.append(FeatureVerdict(
            feature_id=fid,
            description=str(feature.get("description") or "").strip(),
            status=status,
            where=best.where if best else None,
            evidence=best.describe() if best else None,
        ))
        for d in hits:
            claimed.add((d.kind, d.name))

    # Surface nobody asked for. Only the surface counts: an unrequested helper
    # function is how code is organised, not a feature that was shipped.
    for d in index:
        if d.is_surface and (d.kind, d.name) not in claimed:
            report.extras.append(Extra(name=d.name, kind=d.kind, where=d.where))

    return report
