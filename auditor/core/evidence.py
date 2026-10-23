"""What a reading rests on, and therefore what may be said about it.

The instrument can do two different things that look identical in the output:
it can *measure* a codebase against a brief somebody wrote, and it can *guess*
a brief and then measure against that. Until this module existed it could not
tell you which one it had just done, and a field report (FINDING_002) is what
that cost: a folder of working documents scored "0 of 12 delivered" against
twelve errands scraped out of commit subjects.

The first fix for that was a boolean, ``discovery_failed``, set when a guessed
brief matched nothing at all. It was too narrow to be a concept. A guessed
brief matching one feature in twelve is no more trustworthy, and sailed
through it.

So the grade is attached to the reading at the point it is computed, and the
surfaces that render it cannot render without consulting it:

    MEASURED     a human supplied the brief. Report it.
    PROVISIONAL  the brief was derived, and the code corroborated some of it.
                 Report it, labelled, every time.
    WITHHELD     the brief was derived and corroborated nothing. Say so, and
                 report no verdict.

There is deliberately no threshold to tune. A derived brief is never a
measurement however much of it matches, because the thing in doubt is the
brief, not the degree of fit; and a derived brief that corroborates nothing
has supplied the one piece of evidence that bears on its own validity.
"""
from __future__ import annotations

from dataclasses import dataclass

MEASURED = "measured"
PROVISIONAL = "provisional"
WITHHELD = "withheld"


@dataclass(frozen=True)
class Evidence:
    """The standing of one reading, and the sentence that discloses it."""

    grade: str
    origin: str | None = None

    @property
    def reportable(self) -> bool:
        """Whether a verdict may be shown at all."""
        return self.grade != WITHHELD

    @property
    def needs_disclosure(self) -> bool:
        """Whether showing it obliges the surface to say what it rests on."""
        return self.grade == PROVISIONAL

    @property
    def note(self) -> str | None:
        """The disclosure. None when the reading stands on its own."""
        if self.grade == MEASURED:
            return None
        where = self.origin or "the project"
        if self.grade == PROVISIONAL:
            return (
                f"Provisional: nobody supplied a brief, so this was measured "
                f"against what {where} says the project is for. Correct it and "
                f"the reading follows."
            )
        return (
            f"Could not establish what this project was asked to build. The "
            f"provisional brief read from {where} matched nothing in the code, "
            f"which points at the brief rather than at the code. Scope drift is "
            f"not reported. Supply a specification with --spec, or write one "
            f"into .auditor/spec.yaml, and it will be."
        )


def grade(spec: dict | None, report) -> Evidence:
    """The standing of a fidelity reading.

    ``report`` is the FidelityReport, or None where none was produced.
    """
    if not spec:
        return Evidence(WITHHELD, None)
    if not spec.get("_discovered"):
        return Evidence(MEASURED, None)

    origin = spec.get("_discovered_from")
    # A derived brief that corroborates nothing has falsified itself. Zero
    # delivered against a brief a human wrote is a finding -- run_001 contains
    # one -- but against a brief this tool guessed it impugns the guess.
    if report is not None and report.total > 0 and not report.delivered:
        return Evidence(WITHHELD, origin)
    return Evidence(PROVISIONAL, origin)
