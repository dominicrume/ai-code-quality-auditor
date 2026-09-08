# Response to independent statistical review

All figures in the review were independently recomputed from
`data/reports/main_001_plus_human.csv` and the restored captures in
`data/raw/`. Every one reproduces.

## 1. The flagged data point — resolved

The reviewer asked whether `human_control`'s `complexity_mean` of exactly 0.00
on `internal_tool_cli` is a genuine floor or a metric-extraction failure, and
recommended confirming which before the figure appears unqualified.

**It is genuine.** The captured submission
(`.../main_001__internal_tool_cli__human_control__rep00/human_control/code/tool.py`)
is 68 lines of working Python: an `argparse` subcommand tree, file I/O, and
ten branching constructs. It parses cleanly. It contains **zero function
definitions and zero classes** — every statement sits at module top level.

`radon`'s `cc_visit` therefore returns no blocks, and a mean over an empty set
is 0.00. Verified directly: 0 functions, 0 classes, 10 branches, 0 radon
blocks.

The submission is neither empty nor trivial; it is unmodularised. The reading
in §5.5 — that per-function McCabe is confounded with the author's
decomposition style — is confirmed rather than merely asserted, and the value
can be reported as a verified structural artefact. Recommended phrasing: *"0.00
because the implementation defines no functions, not because it was empty or
unmeasured; verified by inspection of the captured file."*

## 2. Reproduced figures

| Reviewer's figure | Recomputed | Match |
|---|---|:--:|
| claude vs cursor, complexity: *U* = 641.5, *p* = 0.0047, *r* = −0.43 | identical | ✅ |
| claude vs cursor, security: *U* = 415.0, *p* = 0.60 | identical | ✅ |
| 5-condition duplication: *H* = 9.67, *p* = 0.046 | identical | ✅ |
| 5-condition complexity *p* = 0.90, security *p* = 0.054, hallucinations *p* = 0.67 | 0.903 / 0.054 / 0.669 | ✅ |
| replit_agent and antigravity flat in every cell | 12/12 cells each | ✅ |

Also confirmed: `claude_code` is flat in 7 of 12 cells and `cursor_agent` in 2
of 12, matching the reviewer's description of partial independence.

## 3. Adopted

* **`correction_freq` is asymmetrically inapplicable, not null.** The review's
  framing is better than the dissertation's and will be used: the metric
  operationalises correction as a keystroke-level phenomenon, which has no
  analogue in a tool that plans and submits without an observable keystroke
  trace. A zero for an agentic condition is evidence the instrument cannot see
  in-process revision, not evidence that none occurred. This is a
  construct-validity limitation for cross-paradigm comparison.
* **Human zeros are occasion-specific.** With N = 1 per specification, zeros on
  security, duplication and hallucinations will be reported as "the baseline did
  not exhibit this behaviour on this occasion", never as a comparative claim.
* **Underpowered nulls are not equivalence.** The non-significant
  five-condition results reflect N = 3, and will be labelled as such.

## 4. One framing this response does not adopt

The review's "contribution beyond the numbers" section describes *"two of the
four agentic tools under test produced fully deterministic behaviour against
this instrument"* and suggests this asymmetry is itself a finding about tool
governance behaviour.

**That claim is not supportable from this dataset, and the study should not make
it.** `replit_agent` and `antigravity` expose no scriptable interface. Under
Deviation 001 each was invoked **once** per specification and the single
captured output was replayed ten times for CSV-shape consistency. Their
flatness is a property of the capture procedure, not an observed property of
the tools: the instrument never re-invoked them, so it cannot have found them
deterministic.

The review's own overall assessment states this correctly — it declines to
accept "a confirmed claim about replit_agent's or antigravity's behavioural
consistency (versus the tooling's failure to elicit variation from them)". The
earlier paragraph reads more strongly than that, and the weaker reading is the
correct one.

What *is* supportable, and is worth foregrounding: **the instrument cannot
currently measure output variability for IDE-bound tools at all**, because it
cannot drive them repeatedly. That is a real blind spot, it is a finding about
the instrument rather than about the vendors, and it makes live multi-session
re-capture (§6.4) the highest-value next step rather than a tidy-up.

## 5. Outstanding

The hallucination inter-rater validation (Cohen's κ, §4.7) remains the one
pre-registered step not completed. The captures required for it have been
restored, so it is now executable: 30 sampled runs, two independent raters,
blind, then `scripts/compute_kappa.py`.
