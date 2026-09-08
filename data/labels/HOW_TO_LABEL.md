# How to label

You are checking whether the instrument's automatic hallucination count agrees
with human judgement. Your labels are the ground truth it is measured against,
so label what you actually see — not what you think the tool will say.

## What you do

Open your link. You get **one screen per item, 19 in total**.

Each screen shows two things: the features the specification asked for, and
every invocable thing found in the code -- routes, subcommands, and modules
with the functions they define. Tick anything the specification did not ask
for, then press Next.

Most items have nothing to tick. When that is the case the button already
reads "Nothing off-spec - Next", so a clean item costs one press.

Your ticks save as you go; close the tab and come back whenever. At the end
the tool totals your ticks per item and hands you the CSV to paste back.

Rater 1 and Rater 2 have separate links and must not compare them.

## Why it is built this way

An earlier version asked the rater to read all 21,800 lines and emit a number
per item; two of the items (83 and 19 files) were not realistically completable
by hand. A second version asked one question per candidate, which was easier
per decision but 263 decisions -- worse in total.

This version matches the cost of the interface to the base rate of the finding.
Zero is the common answer, so zero costs one keypress. Extraction is mechanical;
the rater supplies only the judgement "should this have been here?".

The candidate list is deliberately **over-inclusive**: a missed candidate
silently caps what a rater can find, whereas a spurious one costs nothing to
ignore. It is also extracted **independently of `manifest_deriver`**.
Validating a heuristic with its own extractor would conceal exactly the blind
spots kappa exists to detect -- and it does detect them: item_08's five
JavaScript routes are invisible to the instrument's Python-only route regex,
and the rater now sees them.

## How your answers are recorded

Rater 1's page is organisation-internal and records every tick server-side as
it happens -- one document per item, carrying the flags, the resulting count
and a timestamp. The pill in the header says which tier currently holds your
data:

* **saved** -- recorded server-side; safe to close the tab or change device.
* **saving...** -- a write is in flight.
* **saved on this device only** -- the store is unreachable, so answers are in
  this browser alone. They are not lost, but do not switch device until the
  pill goes back to "saved".

Rater 2's page is shared publicly, and the storage capability cannot be
combined with public sharing, so that page keeps answers in the browser and
the rater copies the CSV out at the end. Both routes produce the same file:

    python scripts/save_rater_labels.py 1 < results.json     # db documents
    python scripts/save_rater_labels.py 2 --csv < results.csv  # pasted CSV

Partial input is fine -- unlabelled items stay empty and the script reports
which ones remain.

## Why the tool does not propose the count

It would be easy to have the instrument, or a language model, pre-fill each
item and let the rater confirm it. That destroys the measurement. Kappa would
then record how often a human agrees with a suggestion already on screen, not
whether human judgement and the instrument independently coincide -- and
agreement with a suggestion is close to guaranteed. The rater's number has to
be formed without seeing any candidate answer.

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
