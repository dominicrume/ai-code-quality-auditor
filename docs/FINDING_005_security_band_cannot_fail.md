# FINDING_005 — the security band could not fail

**Status:** fixed 23 November 2026, in 0.6.7; revised in 0.6.10 and 0.6.11.
Pinned by `tests/test_finding_005_to_008.py`.
**Found:** 23 November 2026, in a field report. Ola ran `auditor scan .` on
SparkrCRM, a SuiteCRM-derived CRM, during the Lagos AI summit. Named with his
consent; see docs/CREDITS.md.
**Module:** `auditor/core/calibration.py`, `auditor/core/scan.py`

## What happened

The scan printed:

    Security      2.40   OK    719 findings

Among those 719 were **nine HIGH findings for dynamic code execution from a
string**, CWE-95. The tool showed a green dot and the word OK.

## Why

`security_density` is a rate, and its thresholds were:

    warning   50 findings per 1000 lines
    critical 100 findings per 1000 lines

Fifty per thousand is **one security finding every twenty lines**. On this
304,000-line codebase the tool would have needed 15,193 findings to say "warn"
and 30,386 to say "critical". It had 719.

No real codebase reaches one finding per twenty lines, so the band was green on
every project it was ever pointed at. The metric could not fail.

Two compounding errors:

1. **A density divides by size**, so a large codebase is rewarded for being
   large. The same nine HIGH findings in a 3,000-line service would have
   measured 240 per kLOC and banded critical. The code is identically
   dangerous; only the denominator changed.
2. **Division discards severity.** One HIGH `eval()` and one LOW style note
   count the same toward the rate, and the rate is all the band ever saw.

## This is the same error the scan already knew about

`core/scan.py` carries this comment about a metric that read nothing:

> The value is 0.00 because nothing was measured, and 0.00 bands as OK, so the
> tool would report a clean bill of health for code it could not read. That is
> the precise failure this instrument was built to detect in other tools.

That reasoning was applied to coverage and never to severity. This is the same
defect in a second place, which is the same way FINDING_004 related to
FINDING_003.

## The fix

`calibration.floor_for` raises a band to whatever the worst finding present
requires, and never lowers one. Applied in the scan path.

The floor is deliberately narrow:

- **HIGH only.** This codebase carried 694 MEDIUM findings. A MEDIUM floor
  would warn on essentially every real project, which is as useless as banding
  them all good, just in the other direction.
  `test_scan_names_serious_security_findings_without_changing_the_band` pinned
  that decision before this change and still passes after it.
- **To `warn`, not `critical`.** A HIGH static match is not a confirmed
  exploit, and the report says so itself. "warn" is the honest reading of an
  unreviewed HIGH finding: a human has to look at this. `critical` stays a
  statement about density.

## What this does not fix

The thresholds themselves. 50 and 100 per kLOC are still almost certainly
wrong by an order of magnitude, and nothing in the repository records where
they came from. Recalibrating them changes a published figure and needs an
erratum, so it is a separate decision and is not taken here.

## Revised in 0.6.10: the floor goes to `critical`, not `warn`

The fix above stopped at `warn`, on the argument that a HIGH static match is
not a confirmed exploit. That argument was wrong about what a band is.

Confidence in a finding and instruction to a reader are two different things.
A band is the second. `warn` beside an unreviewed path to dynamic code
execution is still a line a team scrolls past, and the whole defect recorded
here is that the instrument let a team scroll past nine of them.

The rule now binding on `calibration.py`, stated in public on
23 November 2026:

> The tool stops averaging. The single worst problem decides the colour. One
> serious, unresolved problem turns the whole thing red, however much good
> code sits around it, because a house with one open door is an unlocked
> house, and an attacker only needs the one.

Asymmetry of cost settles it. A HIGH that turns out to be a false positive
costs a team one review. A HIGH banded comfortable costs them the breach. The
instrument is not the arbiter of exploitability and should stop implying it is:
the severity tally and the findings list travel beside the band, so a reader
can downgrade it themselves with the evidence in front of them. FINDING_010 is
this instrument's own false positive, which is exactly why the band names the
risk and the reader names the verdict.

Unchanged: MEDIUM and LOW still do not move the band. 694 mediums were in that
one report, and a rule that always says red says nothing.

Verified end to end on a 12,121-line TypeScript project carrying one HIGH
JS101: density 0.08, which bands `good` on its own, now reads **critical**.
Pinned by `test_one_high_finding_decides_the_colour_however_much_good_code_surrounds_it`
and `test_a_high_finding_in_the_teams_own_code_turns_it_red`.

## Addendum, 23 November 2026, in 0.6.11: MEDIUM reads amber, never green

The owner decided that a MEDIUM finding raises the band to `warn` and never
lets it read green. `SEVERITY_FLOOR` is now
`{"HIGH": "critical", "MEDIUM": "warn"}`. HIGH is unchanged and LOW still does
not move the band. The rule as stated in public:

> Serious remains red no matter how much green code surrounds it. If it's a
> small problem it will be amber and never green.

This reverses the MEDIUM reasoning recorded twice above ("HIGH only" in the
0.6.7 fix, and "Unchanged: MEDIUM and LOW still do not move the band" in the
0.6.10 revision). That reasoning was that this codebase carried 694 MEDIUM
findings and a MEDIUM floor would fire on essentially every real project. The
facts in it stand; the conclusion drawn from them does not.

Why it moved. A known problem banded green is a clean bill of health the
instrument has not earned, which is the error this finding records for HIGH,
one step down. FIELD_REPORT_001 is the worked case: a real MEDIUM (B310, a URL
opener accepting `file:` paths) sat under a green OK. Amber is not alarm. It
tells a reader to look, and the severity tally and the findings list travel
beside the band so the reader can see what to look at and dismiss it with the
evidence in hand. MEDIUM stops at `warn` so that red keeps meaning something
only a HIGH, or a critical density, can earn.

The trade-off, stated rather than hidden: many real projects carrying MEDIUM
findings will now read amber where they read green before, and SparkrCRM with
694 of them would read amber even without its nine HIGHs. A team gating CI with
`--fail-on warn` will see builds fail that passed under 0.6.10; the default
(`never`) and `--fail-on critical` are unaffected by this change.

Scope. The floor is applied only in the scan path (`core/scan.py`), as before.
The experiment path and the published figures read `BANDS` and the density
values, not the floor, so no published figure changes. Dated readings recorded
elsewhere (the 0.6.0 self-audit in README.md, the 0.5.0 table in
FIELD_REPORT_001, which both show a MEDIUM beside an OK) are records of what
those versions printed and are left as they are; re-run under 0.6.11 the same
code would band `warn`.

Pinned by `test_a_medium_finding_reads_amber_and_never_green`,
`test_a_medium_stops_at_amber_and_red_still_belongs_to_high`,
`test_lows_do_not_move_the_band`, `test_the_floor_never_lowers_a_band`, and,
end to end, `tests/test_scan.py::test_scan_names_a_medium_finding_and_bands_it_amber_not_green`
(formerly `test_scan_names_serious_security_findings_without_changing_the_band`,
which pinned the opposite).
