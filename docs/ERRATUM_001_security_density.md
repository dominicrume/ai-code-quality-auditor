# Erratum 001 — security density inflated by test assertions

**Date:** 6 September 2026
**Affects:** Table 4.1, §4.3 (Security density), §4.5 (Table 4.3), §5.2, Abstract
**Status:** magnitudes corrected; no conclusion reversed

## What was wrong

Bandit's `B101` check fires on every `assert` statement. The rule exists
because assertions are removed when Python runs under `-O`, so a security check
written as an assertion would silently vanish from a shipped build. That
reasoning does not apply inside a test file, where the assertion *is* the test.

The security analyser counted them. Three of the four agentic conditions wrote
test suites — antigravity in 30 of 30 runs, cursor_agent in 21 of 30 (66 test
files), claude_code in 16 of 30 — so their reported vulnerability density was
substantially a measurement of how thoroughly they tested their own output.

The metric was, in effect, penalising the conditions that wrote tests.

## Corrected figures

Recomputed from the frozen captures in `data/raw/`, scoring `codebase.json`
exactly as the analyser does. The published column reproduces to the decimal,
which establishes that the only change is the exclusion.

| Condition | Published | Corrected | Change |
|---|---:|---:|---:|
| claude_code | 42.05 | **9.65** | −32.40 |
| cursor_agent | 43.67 | **5.93** | −37.74 |
| replit_agent | 0.00 | 0.00 | — |
| antigravity | 1.48 | 1.47 | −0.01 |

Roughly 77% of the claude_code figure and 86% of the cursor_agent figure were
assertions inside test files.

## What this changes, and what it does not

**Unchanged — every conclusion holds.**

* Security density still differs significantly across the four conditions
  (Kruskal–Wallis: published *H* = 39.35, *p* = 1.5 × 10⁻⁸; corrected
  *H* = 26.07, *p* = 9.2 × 10⁻⁶ — significant at α = 0.01 either way).
* claude_code and cursor_agent still do not differ significantly from each
  other on this metric (published *p* = 0.599; corrected *p* = 0.367).
* Replit's 0.00 remains a denominator artefact of a TypeScript-dominated
  output, exactly as §5.2 describes. That reading is untouched.
* The feature-dense conditions still carry the higher density; the ordering
  among them is not a claim the study made or relies on.

**Changed — the magnitudes, and one interpretive sentence.**

§4.3 describes claude_code and cursor_agent as scoring "highest" at 42.05 and
43.67 per kLOC. The direction is right; the numbers are roughly four- to
sevenfold too large. The corrected values, 9.65 and 5.93, are also the more
plausible ones: 42 CWE-tagged findings per thousand lines of working code
should have invited scrutiny on its face.

## Why it was not caught before submission

The exclusion was identified while running the instrument against its own
repository, where `B101` in `tests/` produced 291 findings and raised the
project's own density from 3.27 to 47.05 per kLOC — a tenfold inflation caused
entirely by having a test suite. Applying the same reasoning to the study data
required the frozen captures, which were restored after submission.

## Reproducing

```bash
python scripts/reprice_security.py        # rewrites the corrected CSV
```

Per-run values for all 120 agentic runs, published and corrected side by side,
are in `data/reports/security_density_corrected.csv`.

## Metric contract

`docs/METRICS.md` §1 now records the exclusion, its rationale, and its
boundary: assertions in production code still count.
