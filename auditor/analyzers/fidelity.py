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

# A reading that contradicts itself is a defect, not an output. This status is
# how the analyser declines to band one. See FINDING_004.
AMBIGUOUS = "ambiguous"

_MARKS = {DELIVERED: "✓", UNREACHABLE: "!", NOT_FOUND: "✗", AMBIGUOUS: "?"}


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
        if self.status == AMBIGUOUS:
            return self.evidence or "withheld: the reading is not coherent"
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
    def ambiguous(self) -> list[FeatureVerdict]:
        """Features whose reading was withheld because it did not cohere."""
        return [v for v in self.verdicts if v.status == AMBIGUOUS]

    @property
    def headline(self) -> str:
        line = f"{len(self.delivered)} of {self.total} delivered"
        held = len(self.ambiguous)
        if held:
            line += f", {held} withheld"
        return line

    @property
    def completeness(self) -> float | None:
        """Share of specified features that were delivered, 0-100."""
        if not self.total:
            return None
        return round(100.0 * len(self.delivered) / self.total, 2)


def _identity(definition: defs.Definition) -> tuple:
    """What makes one definition a different fact from another.

    Kind and name are not enough: the same function name in two files is two
    definitions, and a feature allocated one of them has not consumed the
    other.
    """
    return (definition.kind, definition.name, definition.file, definition.line)


def _pick(candidates: list[defs.Definition], feature_id: str) -> defs.Definition:
    """The candidate that best fits this feature, earliest found on a tie.

    ``sorted`` is stable, so equal candidates keep the order the index found
    them in, which is file order: a verdict cites the first place the thing is
    written rather than an arbitrary one.
    """
    return sorted(candidates,
                  key=lambda d: not defs.discriminates(d, feature_id))[0]


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

    # Does this codebase expose anything at all a user could invoke? When a
    # specification asks for a command-line tool and the project contains no
    # subcommand and no route anywhere, nothing internal can be user-reachable,
    # however many other internal functions call it. Without this, a scheduled
    # data pipeline scored two of six on a six-subcommand CLI brief, because
    # `_init_db` and `validate_row` are called from inside the pipeline.
    has_surface = any(d.is_surface for d in index)

    report = FidelityReport()

    # Every definition each feature could rest on, computed before any of them
    # is allocated. The allocation below needs to know how many alternatives a
    # feature has, which cannot be known while walking the list once.
    hits_for = {f["id"]: [d for d in index if defs.matches(d, f["id"])]
                for f in features}

    claimed: set[tuple[str, str]] = set()     # names a feature accounted for
    for hits in hits_for.values():
        for d in hits:
            claimed.add((d.kind, d.name))

    # One line cannot be the delivery of two different features.
    # `definitions.py` carried a comment acknowledging this defect; this is its
    # repair, and the order of allocation is the whole of it.
    #
    # Two rules, in this order. A feature with fewer alternatives is served
    # first, because specification order let the first feature take the only
    # definition the second had. Then, among features with equally many, the
    # one the definition actually names: given one `POST /auth/register`, both
    # `auth.register` and `auth.login` match on `auth`, and `register` is the
    # word that says which of them this line is.
    def _priority(feature: dict) -> tuple:
        fid = feature["id"]
        hits = hits_for[fid]
        return (len(hits),
                not any(defs.discriminates(d, fid) for d in hits))

    cited: dict[tuple, str] = {}              # definition identity -> feature

    verdicts: dict[str, FeatureVerdict] = {}
    for feature in sorted(features, key=_priority):
        fid = feature["id"]
        hits = hits_for[fid]
        free = [d for d in hits if _identity(d) not in cited]
        surface = [d for d in free if d.is_surface]
        internal = [d for d in free if not d.is_surface]
        note: str | None = None

        if surface:
            best = _pick(surface, fid)
            status = DELIVERED
        elif internal and not wants_surface:
            # For a library or a pipeline, a defined function is the delivery.
            best = _pick(internal, fid)
            status = DELIVERED
        elif internal:
            best = _pick(internal, fid)
            # Only call it unreachable when nothing calls it. A helper invoked
            # by a route is wired up and working, and telling a team otherwise
            # costs more than missing a finding would: the verdict needs
            # evidence of absence, not absence of evidence.
            invoked = has_surface and any(defs.is_invoked(d.name, codebase)
                                          for d in internal)
            status = DELIVERED if invoked else UNREACHABLE
        elif hits:
            # Everything this feature matches is already the evidence for
            # another one. Saying "delivered" here would credit two features to
            # one line; saying "not found" would be false, because something
            # matched. Neither is a reading, so neither is given.
            held = hits[0]
            owners = sorted({cited[_identity(d)] for d in hits})
            best, status = None, AMBIGUOUS
            note = (f"the only match is {held.describe()} at {held.where}, "
                    f"already cited for {', '.join(owners)}")
        else:
            best, status = None, NOT_FOUND

        if best is not None:
            cited[_identity(best)] = fid

        verdicts[fid] = FeatureVerdict(
            feature_id=fid,
            description=str(feature.get("description") or "").strip(),
            status=status,
            where=best.where if best else None,
            evidence=note if note else (best.describe() if best else None),
        )

    # Surface nobody asked for. Only the surface counts: an unrequested helper
    # function is how code is organised, not a feature that was shipped.
    spare = [d for d in index
             if d.is_surface and (d.kind, d.name) not in claimed]

    # A feature reported as nowhere declared, while the route on its own noun
    # is reported as unrequested, is not two findings. It is one incoherent
    # reading, and a reviewer sees the contradiction in ten seconds. The
    # method test is what usually produces it: it is good evidence for
    # crediting a feature and not good enough to assert absence over. So the
    # pair is withheld together -- the feature loses its verdict and the route
    # loses its accusation.
    withdrawn: set[tuple] = set()
    for fid, verdict in verdicts.items():
        if verdict.status != NOT_FOUND:
            continue
        near = [d for d in spare if defs.matches(d, fid, ignore_method=True)]
        if not near:
            continue
        verdict.status = AMBIGUOUS
        verdict.where = near[0].where
        verdict.evidence = (
            f"nothing declares it, yet {near[0].describe()} at {near[0].where} "
            f"is reported as unrequested; both cannot be true"
        )
        withdrawn.update(_identity(d) for d in near)

    # Reported in the order the specification was written, not the order the
    # allocator worked in: the person reading the table wrote the list.
    report.verdicts = [verdicts[f["id"]] for f in features]
    report.extras = [Extra(name=d.name, kind=d.kind, where=d.where)
                     for d in spare if _identity(d) not in withdrawn]

    return report
