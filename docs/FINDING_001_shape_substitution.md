# Finding 001 — scope *substitution* is invisible to a scope-drift count

**Raised:** 12 September 2026, by the structural-shape detector added in
`auditor/analyzers/shape_detector.py`
**Status:** a limitation of the construct, **not an erratum.** No published
number is wrong. Every one of the 120 published hallucination values
re-derives identically with the detector integrated.

## The observation

The hallucination metric asks *what extra did the agent ship?* It is therefore
blind to the case where an agent ships nothing extra because it shipped
something **instead**.

Given `internal_tool_cli` — a brief for a command-line tool with six
subcommands — `antigravity` produced:

    code/main.py
    code/pipeline.py
    code/scheduler.py
    code/schema.py
    code/tests/test_pipeline.py

There is no `add_parser`, no `@click.command`, no subcommand of any kind. It is
a scheduled data pipeline. Because it added no off-specification *commands*, it
scored **0.00 hallucinations — the same score as `claude_code` and
`cursor_agent`, both of which built the CLI correctly.**

Both human raters scored item_17 (this capture) 0 as well, and agreed with the
instrument. That agreement is not rater error: the labelling protocol asks for
off-specification features, and there were none. The protocol asks a question
this failure mode does not answer to.

## Why this matters to the thesis rather than against it

The dissertation's central argument is that functional benchmarks are
structurally incapable of noticing that the wrong artefact was built. This
finding shows the argument reaches further than the text claims: the study's
own governance metric was *partly* subject to the same blindness, and caught
`replit_agent` only because that agent happened to leave three off-specification
subcommands (`run`, `schedule`, `check-config`) lying around as evidence. Had
Replit shipped its pipeline without any argparse surface — as Antigravity did —
the headline finding of the dissertation would have scored 0.00 and gone
unrecorded.

The instrument found the drift by accident of the vendor's style. That is not a
safe foundation for a governance claim, and naming it is worth more than the
tidier story.

## The new signal

`shape_mismatch(spec, codebase)` compares the shape the brief asks for against
the shape actually built, from structural signals (subcommand registration,
route binding, ETL stage functions, schedulers), and reports a mismatch only
when both are known and the built shape wins by a margin. It abstains rather
than guessing.

Across all 120 runs:

| condition | agent_education_system | data_pipeline | internal_tool_cli |
|---|---:|---:|---:|
| claude_code | 0.00 | 0.00 | 0.00 |
| cursor_agent | 0.00 | 0.00 | 0.00 |
| replit_agent | 0.00 | 0.00 | **1.00** |
| antigravity | 0.00 | 0.00 | **1.00** |

Two of four conditions substitute the architecture, both only on the CLI brief,
and where it happens it happens in every run. Read against Table 4.2, the two
metrics say different things: hallucinations rank Replit (3.00) far above
Antigravity (0.00); shape mismatch says both failed the brief completely. Both
readings are true, because they measure addition and substitution respectively.

**Deviation 001 applies.** The `replit_agent` and `antigravity` cells are
replayed singletons, so "1.00 in every run" means one captured session
replicated mechanically, not ten independent observations. The rate is
descriptive of the captures, not an estimate of the tools' stability.

## What has deliberately *not* been done

Shape mismatch is **not** folded into the hallucination count. Doing so would
change figures already published in the dissertation, and that is a decision to
take deliberately, with an erratum and a re-run, rather than as a side effect of
adding a detector. The `derive()` output carries `shape` and `surface` as
additive keys; the three published keys are asserted exactly in
`tests/test_manifest_deriver.py` so that adding a signal can never silently move
a reported number.

## On validation

The detector is written from the protocol, not fitted to the rater labels, and
its behaviour on item_17 and item_19 is a **smoke test, not validation** — those
captures motivated the work. Establishing that shape detection agrees with human
judgement requires a fresh sample and raters who have not seen these items, for
exactly the reason `docs/KAPPA_RESULTS_001.md` refuses the post-repair κ.

A second κ study should ask raters two questions rather than one:

1. *Did the deliverable add anything the brief did not ask for?* (the current
   construct — addition)
2. *Is the deliverable the kind of thing the brief asked for?* (the new one —
   substitution)

item_16 suggests a third, which this module surfaces but does not settle:
whether scaffolding that ships inside the deliverable is drift or organisation.
`classify_surface()` reports capability and scaffolding separately so that the
choice is declared rather than made by accident.
