# FINDING_006 — third-party code was reported as the project's own

**Status:** fixed 23 November 2026, in 0.6.7, on the scan path only. Pinned by
`tests/test_finding_005_to_008.py`.
**Found:** 23 November 2026, same field report as FINDING_005.
**Module:** `auditor/adapters/_shared.py`, now `auditor/analyzers/provenance.py`

## What happened

All nine HIGH findings were reported as the audited team's problem. They were
not:

| File | Who wrote it |
|---|---|
| `RGraph.common.core.js` | RGraph charting library |
| `jquery.json-2.3.js` | jQuery JSON plugin |
| `jquery.markitup.js` | markItUp! editor |
| `flashcanvas.js` | FlashCanvas |
| `imagemap.js` (×2) | pChart |
| `Chart.js` | Chart.js |
| `markerclusterer_packed.js` | Google MarkerClusterer |
| `jsclass_scheduler.js` | upstream SuiteCRM |

**Eight of nine are vendored libraries. The ninth is upstream. Not one was
written by the team being audited.**

The generated report's first recommendation was *"Manually validate the 9 high
security flags first"*. Following it sends an engineer to audit jQuery.

## Why

The guard existed and missed. `_shared.VENDOR_DIRS` matches **directory
names** — `vendor`, `third_party`, `node_modules` — and its own comment names
this exact failure mode:

> Counting them is how a tool reports 83% duplication on a repository whose own
> source is barely duplicated.

Projects of this age vendor into ordinary paths:
`include/javascript/jquery/`, `modules/AOR_Charts/lib/pChart/`. Nothing is
called `vendor`. The guard was built and it misses the commonest layout there
is.

## The fix

`auditor/analyzers/provenance.py` classifies each file as `first_party`,
`vendored` or `generated`, from three signals: a known library's name as a
filename stem or a path segment, a build-output filename, and line lengths no
author produces.

**Attribution, not exclusion.** The files are not dropped. A number that
quietly stopped counting things is the same class of error as one that quietly
counted them. Metrics about the project's code are computed over the project's
code, and everything else is carried in `codebase["not_authored"]` so the
report can say what was set aside and why.

Applied only when `respect_ignores` is on — `scan`, `watch`, `live` — for the
same reason that flag exists: the experiment walked what it walked, and the
published figures stay reproducible.

## On being wrong in the right direction

Misclassifying a project's own file as vendored hides a real finding, which is
the costlier mistake. Every rule therefore needs a positive signal. A directory
called `lib` or `libs` is **not** one: plenty of projects keep their own code
there. `modules/AOR_Charts/lib/pChart/` is caught by `pchart`, the name of the
library, and `app/libs/my_own_helper.js` and `src/lib/billing/charge.ts` stay
first-party. Both are pinned by tests.
