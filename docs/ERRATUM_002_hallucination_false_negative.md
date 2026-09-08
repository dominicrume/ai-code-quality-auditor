# Erratum 002 — a false negative in the hallucination detector

**Raised:** 8 September 2026, by the two-rater Cohen's κ validation
**Affects:** Table 4.2, Figure 4.3, and the prose describing `replit_agent`'s
task-conditionality
**Corrects:** one cell, `replit_agent × agent_education_system`, from **0.00 to 1.00**

## What was wrong

`manifest_deriver._ROUTE_RE` matched only the Python decorator form of a web
route:

    @app.get("/path")        matched
    router.get("/path")      NOT matched

The `replit_agent × agent_education_system` capture is an Express service
written in TypeScript. It exposes five routes, four of which map to
specification features and one of which — `GET /healthz` — appears in no
specification. Because none of the five matched, the cell scored zero by
construction rather than by judgement, and no amount of scrutiny of the
reported number could have revealed it.

Both raters, labelling independently from a candidate list extracted without
reference to `manifest_deriver`, counted the route.

## Scope of the correction

Under Deviation 001 the ten runs in this cell are replays of a single capture,
and the instrument returned an identical 0.00 for all ten. The correction
therefore applies to the whole cell, not to a sampled fraction of it.

Re-deriving all 120 runs with the repaired detector:

* 120 of 120 previously published values reproduce exactly, confirming the
  analysis pipeline is deterministic and the stored report was not stale.
* Exactly 10 rows change: `replit_agent × agent_education_system`, 0 → 1.
* No other metric, condition or specification is affected.

**Table 4.2, corrected**

| Hallucinations by spec | agent_education | data_pipeline | internal_tool_cli |
|---|---:|---:|---:|
| claude_code | 0.00 | 0.00 | 0.00 |
| cursor_agent | 0.50 | 0.00 | 0.00 |
| replit_agent | **1.00** | 0.00 | 3.00 |
| antigravity | 1.00 | 0.00 | 0.00 |

## Claims that do not survive

The statement that Replit's hallucinations are *"entirely concentrated in the
CLI spec — zero in the other two"* is false, and Figure 4.3's caption claiming
*"its isolation from every other cell"* is false with it. Replit drifts in two
of the three specifications.

The accompanying argument that *"a web-app-only study would have indicted
Antigravity and exonerated Replit"* is also wrong: on the corrected figures the
two tie at 1.00 in the web-app specification. Only the CLI comparison separates
them.

## Claims that survive unchanged

* **Claude Code shipped zero off-spec features in every cell.** Confirmed
  independently by both raters on every claude_code item.
* **Replit's drift is worst on the CLI specification** (3.00 against 1.00 and
  0.00). The magnitude ranking is untouched.
* **Hallucination behaviour is task-conditional.** Replit now reads
  1.00 / 0.00 / 3.00 across the three specifications, which is still markedly
  non-uniform. The three-specification design is if anything better justified,
  because the corrected table shows drift in more places than the original.
* Every other cell in Table 4.2.

## What this says about the metric generally

The detector was blind to an entire class of web framework. Every condition in
this study produced some TypeScript, so hallucination counts should be read as
a **lower bound**, and the bound was loosest for the condition whose output is
TypeScript-dominated. This is the same shape of problem as the security-density
denominator artefact recorded in Erratum 001: the instrument was not wrong
about what it saw, it was wrong about what it could see.

The defect is repaired in `auditor/analyzers/manifest_deriver.py` with a
regression test (`tests/test_manifest_deriver.py::test_express_routes_are_detected`),
and `data/reports/main_001.csv` has been regenerated.

## The repaired instrument is not thereby validated

Repairing the defect raises κ(Rater 1, instrument) from 0.853 to 1.000 and
κ(Rater 2, instrument) from 0.727 to 0.870. **Those figures are circular and
must not be quoted as validation.** The defect was identified by the raters'
disagreement, and the repair was then measured against the labels that
identified it. The pre-registered κ values — 0.870, 0.853, 0.727 — are computed
against the instrument as it stood when the raters worked, and remain the
figures of record. See `docs/KAPPA_RESULTS_001.md`.
