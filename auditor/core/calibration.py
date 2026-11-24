"""Decision thresholds for every metric — the single source of truth.

The bands are interpretation *policy*, not measurement. They are declared
once here so the CLI, the dashboard and the mobile client cannot drift
apart and tell a user three different stories about the same number.

Semantics: lower is better for every metric.
  value <  warning   -> "good"
  value <  critical  -> "warn"
  otherwise          -> "critical"
"""
from __future__ import annotations

from typing import Literal

Band = Literal["good", "warn", "critical"]

BANDS: dict[str, dict[str, float]] = {
    "security_density": {"ideal": 0.0, "warning": 50.0, "critical": 100.0},
    "complexity_mean":  {"ideal": 0.0, "warning": 3.0,  "critical": 6.0},
    "duplication_pct":  {"ideal": 0.0, "warning": 5.0,  "critical": 10.0},
    "hallucinations":   {"ideal": 0.0, "warning": 1.0,  "critical": 3.0},
    "correction_freq":  {"ideal": 0.0, "warning": 10.0, "critical": 25.0},
}


def band_for(metric: str, value: float) -> Band:
    """Classify ``value`` against ``metric``'s thresholds."""
    limits = BANDS.get(metric)
    if limits is None:
        return "good"
    if value >= limits["critical"]:
        return "critical"
    if value >= limits["warning"]:
        return "warn"
    return "good"


# A density cannot be allowed to speak for a severity.
#
# `security_density` warns at 50 findings per 1000 lines. That is one finding
# every twenty lines, which no real codebase reaches, so the metric banded
# "good" on every project it was ever pointed at. A 304,000-line CRM carrying
# nine HIGH dynamic-code-execution findings measured 2.40 and printed a green
# OK, because dividing by a large codebase is flattering and division discards
# severity entirely.
#
# scan.py already carries this exact reasoning about unreadable code: *0.00
# bands as OK, so the tool would report a clean bill of health for code it
# could not read*. This is the same error in the banding rather than in the
# coverage, and the same answer applies. See FINDING_005.
#
# HIGH goes straight to critical. The first fix stopped at "warn", on the
# argument that a HIGH static match is not a confirmed exploit. That argument
# is about *confidence in the finding*, and a band is not a confidence: it is
# what the reader is told to do next. "Warn" beside a green-ish dot is still a
# number a team scrolls past, and the thing being scrolled past is an
# unreviewed path to dynamic code execution. The rule, stated publicly on
# 23 November 2026 and now binding on this file:
#
#   the single worst problem decides the colour, because a house with one
#   open door is an unlocked house
#
# A HIGH finding that turns out to be a false positive costs a team one
# review. A HIGH finding banded comfortable costs them the breach. The
# instrument is not the arbiter of exploitability and must stop implying it is;
# `details` and the severity tally say what was found, so a reader can
# downgrade it themselves with the evidence in front of them. See FINDING_005,
# revised in 0.6.10 and again in 0.6.11.
#
# MEDIUM goes to warn, and never reads green. Decided by the owner on
# 23 November 2026, reversing the reasoning that stood here in 0.6.7 to
# 0.6.10. The rule as stated in public:
#
#   serious remains red no matter how much green code surrounds it; a small
#   problem will be amber and never green
#
# A known problem banded green is a clean bill of health the instrument has
# not earned, which is the same error FINDING_005 records for HIGH, one step
# down. Amber is not alarm: it tells a reader to look, and the severity tally
# and the findings list travel beside the band so they can see what to look at
# and dismiss it with the evidence in hand. MEDIUM stops at warn so that red
# keeps meaning something only HIGH (or a critical density) can earn.
#
# The earlier argument was that the CRM in FINDING_005 carried 694 MEDIUM
# findings and a MEDIUM floor fires on essentially every real codebase. That
# trade-off is real and is accepted, not denied: many real projects carrying
# MEDIUM findings will now read amber where they used to read green. The
# owner's answer is that those projects do carry known problems, and green
# beside them was the instrument flattering them.
#
# LOW does not move the band.
SEVERITY_FLOOR: dict[str, Band] = {"HIGH": "critical", "MEDIUM": "warn"}

_RANK: dict[Band, int] = {"good": 0, "warn": 1, "critical": 2}


def floor_for(band: Band, severity: dict[str, int] | None) -> Band:
    """The band, raised to whatever the worst finding present requires.

    Never lowers a band. A density high enough to be critical stays critical
    whatever the severities, because many low-severity findings in a small
    codebase is also a finding.
    """
    if not severity:
        return band
    worst = band
    for name, count in severity.items():
        if not count:
            continue
        need = SEVERITY_FLOOR.get(str(name).upper())
        if need and _RANK[need] > _RANK[worst]:
            worst = need
    return worst
