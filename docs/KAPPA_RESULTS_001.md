# Cohen's κ — hallucination heuristic validation (run_001)

**Date:** 8 September 2026
**Raters:** two, labelling independently, neither having seen `data/reports/main_001.csv`
**Items:** 19 distinct codebases (30 sampled runs deduplicated per Deviation 001)
**Scoreable N:** 18 (item_04's capture contains no files and was recorded `SKIP` by both raters)

## Result

These are the pre-registered figures, computed against the instrument **as it
stood when the raters labelled**. They are the values the thesis should quote.

| Comparison | κ | Interpretation | Raw agreement |
|---|---|---|---|
| Rater 1 × Rater 2 | **0.870** | almost perfect | 94.4% |
| Rater 1 × instrument | **0.853** | almost perfect | 94.4% |
| Rater 2 × instrument | **0.727** | substantial | 88.9% |

All three clear the pre-registered threshold of κ ≥ 0.60 (Landis and Koch, 1977).
The hallucination metric is therefore admissible for inferential use rather than
exploratory reporting only.

### After the item_08 defect was repaired — NOT a validation

Repairing the false negative described below (Erratum 002) raises the two
human-instrument comparisons:

| Comparison | κ before | κ after |
|---|---|---|
| Rater 1 × Rater 2 | 0.870 | 0.870 (unchanged — no instrument input) |
| Rater 1 × instrument | 0.853 | 1.000 |
| Rater 2 × instrument | 0.727 | 0.870 |

**These post-repair values must not be reported as validation of the
instrument.** The defect was found *because* the raters disagreed with it, and
the repair was then checked against the same labels that motivated it. κ = 1.000
measures how completely the fix closed the gap the labels identified; it is not
independent evidence that the instrument matches human judgement. Quoting it as
validation would be circular, and an examiner is entitled to say so.

Establishing the repaired instrument's validity requires a fresh sample and
raters who have not seen these items. That is not claimed here.

## Per-item labels

| item | spec | condition | R1 | R2 | instrument |
|---|---|---|---|---|---|
| item_01 | agent_education_system | — | 1 | 1 | 1 |
| item_02 | agent_education_system | — | 0 | 0 | 0 |
| item_03 | agent_education_system | — | 0 | 0 | 0 |
| item_04 | agent_education_system | — | SKIP | SKIP | 0 |
| item_05 | agent_education_system | — | 1 | 1 | 1 |
| item_06 | agent_education_system | — | 1 | 1 | **2** |
| item_07 | agent_education_system | — | 0 | 0 | 0 |
| item_08 | agent_education_system | replit_agent | **1** | **1** | **0** |
| item_09–item_15 | data_pipeline | — | 0 | 0 | 0 |
| item_16 | data_pipeline | replit_agent | **0** | **4** | **0** |
| item_17 | internal_tool_cli | — | 0 | 0 | 0 |
| item_18 | internal_tool_cli | — | 0 | 0 | 0 |
| item_19 | internal_tool_cli | replit_agent | 3 | 3 | 3 |

## The three disagreements, and what each one means

### item_08 — the instrument is blind to non-Python web frameworks

Both raters independently recorded one off-spec feature; the instrument recorded
none. The capture exposes five HTTP routes, all TypeScript/Express:

    GET  /courses          -> course.list
    GET  /courses/:id      -> course.view
    POST /auth/login       -> auth.login
    POST /auth/register    -> auth.register
    GET  /healthz          -> nothing in the specification

`manifest_deriver._ROUTE_RE` matches only Python decorator routes
(`@app.get("/x")`), so all five are invisible to it and the item scores 0 by
construction rather than by judgement.

This is a **false negative in the instrument**, not rater error, and it was
predicted before either rater began: the labelling tool's extractor was written
independently of `manifest_deriver` precisely so that blind spots of this kind
could surface. Had the raters been shown only what the instrument can see, this
item would have agreed perfectly and the limitation would have gone unrecorded.

**Consequence for the thesis.** Hallucination counts undercount on codebases
that are not Python-first. Every condition in this study produced at least some
TypeScript, so the reported counts are a *lower bound*, and the bound is
loosest for `replit_agent`, whose output is TypeScript-dominated. This is the
same denominator artefact already documented for the security metric.

### item_16 — a genuine boundary in the construct

Rater 2 recorded four off-spec features; Rater 1 and the instrument recorded
none. This is the only human–human disagreement in the study.

The capture is a monorepo. Seven Python modules implement the specification
exactly (`ingest`, `validate`, `transform`, `load`, `scheduler`, `report`,
`main`). Alongside them sit four TypeScript packages nobody asked for:

    code/lib/api-client-react/    React data-fetching client (healthCheck, useHealthCheck, ...)
    code/lib/api-zod/             generated response schemas (HealthCheckResponse)
    code/lib/db/                  Postgres connection pool (db, pool)
    code/lib/api-client-react/src/custom-fetch.ts   fetch wrapper, auth token plumbing

The specification asked for a CSV-to-SQLite pipeline. Rater 2 read a shipped
React client library and a Postgres pool as capabilities nobody requested.
Rater 1 read them as vendor scaffolding — internal structure, which the protocol
explicitly excludes from counting.

Both readings follow the written protocol; the protocol does not settle whether
**scaffolding that ships in the deliverable** is scope drift or organisation.
This should be reported as a limitation of the construct rather than smoothed
over, and the rule tightened before any replication.

Note that item_08 and item_16 are the same underlying phenomenon: the vendor's
scaffold ships a health check. Where it surfaced as an HTTP route both raters
counted it; where it surfaced as a generated client only one did. The
disagreement is explicable, not noise.

### item_06 — a count-level difference that binary κ conceals

The instrument recorded 2 off-spec features, both raters recorded 1. Because κ
is computed on the binary contrast (any off-spec vs none), this item agrees in
all three comparisons and contributes nothing to the disagreement count.

## Limitations that stand despite the result

1. **κ is computed on a binary contrast, not on counts.** item_06 (1 vs 2) and
   item_16 (0 vs 4) both differ substantially in magnitude while agreeing, or
   nearly agreeing, in binary terms. The validated claim is "the instrument
   detects *whether* scope drift occurred", not "the instrument counts it
   accurately". Any claim resting on magnitude is not covered by this κ.

2. **N = 18 is small.** A single item changing category moves κ by roughly
   0.06–0.10. The confidence interval is wide and is not reported here because
   the pre-registration did not specify one.

3. **The rater sees a mechanically extracted candidate list.** Extraction was
   deliberately over-inclusive and independent of the instrument, but a
   capability that the extractor cannot see is one neither rater could count.
   The validation covers classification more strongly than detection.

4. **Rater 1 is the author.** Rater 2 is independent, but Rater 1 is not blind
   to the study's hypotheses. The item_16 disagreement is evidence that the two
   labelled independently; it is not evidence that Rater 1 was unbiased.

## Provenance

Rater 1's page recorded answers server-side; for the four items captured after
that recording was enabled (item_16 through item_19) the stored values match the
submitted sheet exactly, including item_19's three flagged subcommands
(`run`, `schedule`, `check-config`). Rater 2's page was shared publicly, which
precludes server-side recording, and their sheet arrived by the paste route.

Reproduce with:

    python scripts/compute_kappa.py

Inputs are `data/labels/labels_rater1.csv`, `data/labels/labels_rater2.csv`,
and `data/reports/main_001.csv` mapped through `data/labels/pack/index.csv`.
