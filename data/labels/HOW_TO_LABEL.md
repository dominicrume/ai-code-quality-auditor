# How to label

You are checking whether the instrument's automatic hallucination count agrees
with human judgement. Your labels are the ground truth it is measured against,
so label what you actually see — not what you think the tool will say.

## What you do

Open your link and answer one question at a time. Each question shows a single
thing found in the code -- a route, a subcommand, a function, a class -- with
the file and line it came from, and the specification's feature list directly
beneath it. You press one of three keys:

* `1` **Yes, it was asked for** -- it maps to a feature in the spec list.
* `2` **No, nobody asked for it** -- this is scope drift. These are what get counted.
* `3` **Not a user-facing feature** -- a helper, a loader, internal plumbing.

There are 263 of these across the 19 items. Your answers save as you go; close
the tab and come back whenever you like. At the end the tool totals your `2`
answers per item and hands you the CSV.

Rater 1 and Rater 2 have separate links and must not compare them.

## Why it is built this way

An earlier version asked the rater to read all 21,800 lines and emit a number
per item. That is extraction, and extraction is what a machine does reliably.
Judgement -- "should this have been here?" -- is the only part that needs a
human, and it is the only part now asked for.

The candidate list is deliberately **over-inclusive**: it surfaces more things
than could plausibly be features, because a missed candidate silently caps what
a rater can find, whereas a spurious one costs a single keypress. It is also
extracted **independently of `manifest_deriver`**. Validating a heuristic with
its own extractor would hide precisely the blind spots kappa exists to detect --
and it does detect them: item_08's five JavaScript routes are invisible to the
instrument's Python-only route regex, and the rater now sees them.

## Counting rules

**Count** a thing a user could invoke that nobody asked for: an HTTP route, a
CLI subcommand, a user-facing capability.

**Do not count** helper functions, configuration, imports, tests, logging,
error handling, or internal structure. An agent is free to organise its code
however it likes — that is not scope drift.

**Count once.** A feature spread across three files is one feature.

**Zero is a real answer** and will be common. Do not go looking for something
to find.

**`SKIP`** is filled in automatically for any item whose capture contains no
files (item_04).

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

263 decisions. Most are immediate. Budget around half an hour, and stop when
you get tired rather than pushing through -- a rushed second half is worse than
a shorter sample.

## Rebuilding the tool

    python scripts/build_tick_labeller.py build

Writes `build/rater1.html` and `build/rater2.html`.
