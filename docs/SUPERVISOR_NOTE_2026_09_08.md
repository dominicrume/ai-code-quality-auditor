# Note to supervisors — 8 September 2026

**To:** Julien Barney, Kate Sugden
**From:** Uririe, Orume Dominic (JBKS1)
**Subject:** Hallucination validation complete; one headline claim corrected

Three things have changed since you last saw Chapter 4. One of them corrects a
claim I previously made to you, so I would rather flag it than let you find it.

## 1. The Cohen's κ validation is done, and it passes

The hallucination heuristic was validated against human judgement as
pre-registered. Two raters labelled independently: Ikenna Onyedebelu (MSc Data Science and AI)
and Matthew Brian Tahir, neither with any other involvement in the study.
Neither saw the instrument's output. The 30-run sample deduplicates to 19 distinct codebases,
because 11 of those rows are byte-identical replays under Deviation 001 and
labelling the same code twice would inflate agreement by construction.

| Comparison | κ |
|---|---:|
| Rater 1 × Rater 2 | 0.870 |
| Rater 1 × instrument | 0.852 |
| Rater 2 × instrument | 0.727 |

All three clear the pre-registered 0.6 threshold, so §4.7 now reports a result
instead of a plan, and the hallucination metric is admissible for inferential
use.

Two limits on that, which the chapter states: κ is computed on the binary
contrast, so the instrument is validated as an answer to *whether* scope drift
occurred and **not** to *how much*. Both raters are independent of the study, and the single human–human
disagreement shows the two sheets were produced without conferring.

## 2. The labelling exposed a real defect, and it changes a claim I made to you

Both raters counted an off-specification route in the `replit_agent` web-app
capture that the instrument had scored zero for. The cause: the route detector
matched only the Python decorator form (`@app.get(...)`), and that capture is an
Express service written in TypeScript. It exposes `GET /healthz`, which no
specification requests. The cell scored zero **by construction rather than by
judgement**, and no scrutiny of the reported number could have revealed it.

It surfaced only because the labelling tool extracted its candidate list
independently of the instrument. Had I reused the instrument's own extractor,
the item would have agreed perfectly and the defect would have gone into the
thesis.

**The claim that does not survive** is the one I have previously put to you as
the study's cleanest result: that Replit's off-spec output was *"entirely
concentrated in the CLI specification — zero in the other two."* It is not. The
web-app cell is 1.00, not 0.00, and on the corrected figures Replit and
Antigravity **tie** there. The related argument that a web-app-only study would
have exonerated Replit is also wrong.

**What survives unchanged:** Claude Code's zero in every cell, confirmed
independently by both raters; Replit's CLI figure of 3.00 and its position as
the worst condition; and the task-conditionality that justifies the
three-specification design — Replit now reads 1.00 / 0.00 / 3.00, which is if
anything more uneven than before.

Re-deriving all 120 runs: every previously published value reproduces exactly,
and precisely 10 rows change — the whole of that one cell, since Deviation 001
makes its ten runs replays of a single capture. Table 4.1 (1.00 → 1.33),
Table 4.2, Table 4.4, both Kruskal–Wallis levels and Figure 4.3 are corrected
throughout. Written up as `docs/ERRATUM_002_hallucination_false_negative.md`.

## 3. A caveat I want to be explicit about

Repairing the detector raises κ against the instrument to 1.000 and 0.870. **I
am not reporting those as validation and they appear nowhere in support of any
claim.** The defect was found by the raters' disagreement and the repair then
measured against the labels that found it, which is circular. The figures of
record are the pre-repair ones in the table above, and
`scripts/compute_kappa.py --pre-erratum002` reproduces them exactly from a
snapshot taken before the repair. Validating the repaired instrument properly
would need a fresh sample and raters who have not seen these items; I have
listed that as future work rather than claiming it.

## Reading order, if you want the detail

1. `docs/KAPPA_RESULTS_001.md` — the validation, per-item labels, and all four limitations
2. `docs/ERRATUM_002_hallucination_false_negative.md` — the defect and its scope
3. `docs/ERRATUM_001_security_density.md` — the earlier security-density correction
4. `docs/REVIEW_RESPONSE_001.md` — the response to the independent statistical review

## What I would value your steer on

- Whether the word limit is a hard 12,000 for main text. The draft is currently
  ≈13,810 including tables, so I would need to cut ≈1,800 words, and I would
  rather know before cutting than after.
- Whether the handbook requires a Declaration of own work; the draft does not
  currently carry one.
