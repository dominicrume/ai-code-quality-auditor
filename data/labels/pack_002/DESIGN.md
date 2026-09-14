# Pack 002 — design, and the limits of what it can establish

**Built:** 13 September 2026 · `scripts/make_labelling_pack_002.py` (seed 20260913)
**Scored by:** `scripts/compute_kappa_002.py`
**Status:** apparatus complete, **rater labels not yet collected**. Nothing here
is a validation result until two people have filled in the answer sheets.

## Why a second study

Study 001 validated one construct: *addition* — "what did the agent ship that
nobody asked for?" — at κ = 0.870 / 0.852 / 0.727.

`docs/FINDING_001_shape_substitution.md` shows that construct is blind to
*substitution*. Given the `internal_tool_cli` brief, `antigravity` shipped a
scheduled pipeline with no subcommands, added nothing, and scored 0.00 — the
same as the two conditions that built the CLI correctly. Both raters scored it 0
and were right to: the protocol asked about additions and there were none.

Two different failures need two different questions. This pack asks both.

## The questions

| | Question | Answer | Construct |
|---|---|---|---|
| **Q1** | How many features/routes/subcommands exist that are NOT in the spec? | integer | addition (as in study 001, so κ is comparable) |
| **Q2** | Is this deliverable *the kind of thing* the brief asked for? | yes / no / unsure | substitution (new) |
| **Q3** | Is shipped library/infrastructure code *drift* or *organisation*? | drift / organisation / n-a | the item_16 boundary — exploratory, descriptive only |

Q2 is deliberately indifferent to correctness: a CLI brief answered with a CLI
whose subcommands are all wrong is still `yes`. That keeps Q2 measuring shape
and leaves feature-level correctness to Q1.

## The sampling problem, and what the design does about it

Under Deviation 001 the IDE-bound conditions were captured once per cell and
replayed. `replit_agent` and `antigravity` therefore contribute **exactly one
distinct artefact each per specification**, and every one of them appears in
pack 001. Counted precisely:

| cell | reps | distinct artefacts | already seen by raters | fresh |
|---|---:|---:|---:|---:|
| claude_code × each spec | 10 | 10 / 10 / 10 | 2 / 4 / 0 | 8 / 6 / 10 |
| cursor_agent × each spec | 10 | 9 / 10 / 9 | 4 / 2 / 1 | 5 / 8 / 8 |
| replit_agent × each spec | 10 | **1** | 1 | **0** |
| antigravity × each spec | 10 | **1** | 1 | **0** |

**There is no fresh naturalistic material in the two cells where shape mismatch
actually fires.** A pack drawn only from unseen artefacts would contain no
positive case for Q2, and a κ computed on it would measure specificity while
looking like validation. Saying so is the whole point of writing this down.

The design answers it with two interleaved blocks, 30 items total:

- **Block A — naturalistic (24 items).** Distinct `claude_code` and
  `cursor_agent` artefacts appearing in no item of pack 001, each paired with
  its own specification. Stratified across (spec × condition), 15/15 by
  condition.
- **Block B — positive controls (6 items).** Unseen artefacts deliberately
  paired with a *different* brief, so the ground truth for Q2 is known by
  construction: the deliverable is not the kind of thing that brief asked for.

Raters are not told which block an item belongs to; the shuffle interleaves
them. `index.csv` carries the ground truth and **must be withheld from raters**.

## What this design can establish

1. **κ for the addition construct on fresh data.** Study 001's items motivated
   two errata; these did not.
2. **Specificity for the shape construct.** If shape detection flags correct
   work as the wrong kind, 24 naturalistic items will show it.
3. **Sensitivity against known ground truth.** If it cannot identify six
   deliberately mispaired deliverables, it cannot detect substitution at all.
4. **Whether humans can agree on Q2 at all.** If κ(rater 1, rater 2) on Q2 is
   low, the construct is ill-defined and no instrument can be validated against
   it. That is a real possible outcome and it is worth knowing.

## What this design canNOT establish

**Sensitivity on naturalistic substitution.** The controls are constructed by
mispairing, not observed in the wild. A tool that substitutes an architecture
unprompted — which is the behaviour the dissertation reports — is represented in
this corpus by exactly two artefacts, both already labelled. Establishing that
shape detection catches *naturally occurring* substitution requires **new
captures** from the IDE-bound tools against briefs they have not seen. That is a
data-collection task, not an analysis one, and it is the honest next step.

A second limitation: the instrument's author also built the controls. The
detector was written from the protocol rather than fitted to any labels, and
these artefacts were not consulted while writing it, but "author-constructed
controls" is weaker evidence than "independently constructed controls" and is
recorded as such.

## Instrument self-check, run before any rater sees the pack

    python scripts/compute_kappa_002.py

- controls identified as wrong kind: **6 / 6**
- naturalistic items not flagged: **24 / 24**

**This is not validation.** It is the instrument agreeing with ground truth that
the instrument's author constructed. It is reported here, before labelling, so
that it cannot later be presented as though the raters confirmed it — the same
reason `docs/KAPPA_RESULTS_001.md` refuses the post-repair κ.

## Running the study

1. Send each rater the 30 `item_XX.md` files and one blank
   `labels_raterN_002.csv`. **Do not send `index.csv` or this file.**
2. Raters work independently and do not confer.
3. Return both sheets, then run `python scripts/compute_kappa_002.py`.
4. Record the result as `docs/KAPPA_RESULTS_002.md`, including any disagreement
   that exposes a defect — as item_08 did in study 001 — and resist quoting any
   post-repair figure as validation.

Rater 1 should ideally **not** be the author this time. Study 001 records that
limitation; the cheapest way to remove it is to recruit two independent raters.
