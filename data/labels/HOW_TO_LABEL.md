# How to label

You are checking whether the instrument's automatic hallucination count agrees
with human judgement. Your labels are the ground truth it is measured against,
so label what you actually see — not what you think the tool will say.

## What you do

Open `pack/item_01.md` and work through to `item_19.md`. Each file contains:

1. the features the specification asked for, and
2. the complete code that was produced.

For each item, count **how many distinct features, routes, endpoints or
subcommands exist in the code that are not in the specification's list**.

Write that number in the `n_offspec_features` column of your sheet:

* Rater 1 → `labels_rater1.csv`
* Rater 2 → `labels_rater2.csv`

Use the `notes` column for anything you were unsure about. Those notes matter
more than the number when the two of you disagree.

## Counting rules

**Count** a thing a user could invoke that nobody asked for: an HTTP route, a
CLI subcommand, a user-facing capability.

**Do not count** helper functions, configuration, imports, tests, logging,
error handling, or internal structure. An agent is free to organise its code
however it likes — that is not scope drift.

**Count once.** A feature spread across three files is one feature.

**Zero is a real answer** and will be common. Do not go looking for something
to find.

**`SKIP`** if an item says the capture contains no files.

## The rules that make this valid

**Do not look at `data/reports/main_001.csv`.** It contains the automatic
counts. Seeing them turns your judgement into agreement with a suggestion, and
the resulting κ would be worthless.

**Do not confer.** The two raters must label independently and must not compare
sheets until both are finished. If you discuss an item first, you are measuring
one opinion twice.

**You will not be told which tool produced which item.** That is deliberate.

## When both sheets are finished

```bash
python scripts/compute_kappa.py
```

It reports three values: rater 1 against rater 2 (are the humans reliable?),
and each rater against the instrument (is the instrument valid?). The
pre-registered threshold is κ ≥ 0.6 (Landis and Koch, 1977).

## Why 19 items and not 30

The pre-registered sample is 30 runs, but two conditions were captured once per
cell and replayed (Deviation 001), so 11 of those rows are byte-identical
copies. Labelling the same code four times would add nothing and would inflate
κ, because identical items agree by construction. Each distinct codebase is
labelled once and its label is propagated to the runs it covers; κ is computed
over the 19 independent items. `pack/index.csv` records which runs each item
covers.

## How long it takes

About 21,800 lines across 19 items — most are small, three are large monorepos.
Budget three to four hours, and stop when you get tired rather than pushing
through: a rushed second half is worse than a shorter sample.
