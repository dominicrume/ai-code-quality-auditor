# Erratum 003 — the hallucination detector credited features on token evidence

**Raised:** 14 October 2026, while preparing the 0.6.0 release
**Affects:** the `implemented` list inside `manifest_deriver.derive`, and
through it the hallucination counts in Table 4.2 wherever a route or command
was suppressed by a feature that had been credited on weak evidence
**Corrects:** the evidence rule, not a single cell. Published figures remain
reproducible via `version=1`; see "Scope" below.

## What was wrong

`manifest_deriver._evidence` credited a specification feature when the
terminal segment of the feature id appeared anywhere in a single string made
by concatenating every file in the codebase:

```python
def _evidence(blob: str, feature_id: str) -> bool:
    last = feature_id.split(".")[-1]
    return any(tok in blob for tok in [last, f"{last}s"])
```

A word in a comment satisfies it. So does a word inside an unrelated
identifier, and on Python `cli.list` is satisfied by `list(x)`.

Measured directly: given the six-feature `internal_tool_cli` specification and
an ETL script implementing none of it, with the words `add`, `list`, `export`,
`validate` and `remove` present only in comments:

```
spec features     : 6
credited as built : ['cli.add','cli.list','cli.export','cli.validate','cli.remove']
reported drift    : 0
```

Five of six credited, and the drift count reported zero, because a credited
feature suppresses the route or command that would otherwise have been counted
as unrequested.

This is the mechanism behind the finding already recorded in §6.4 and in
`shape_detector`'s docstring: `replit_agent`, given a CLI specification,
shipped a pipeline and had four of six features credited. That was reported at
the time as a limitation of the metric. It is more precisely a defect in the
evidence rule, and this erratum records it as one.

## What it is now

`analyzers/definitions.py` indexes what the codebase **declares** — registered
subcommands, HTTP routes, functions, classes and exports — each with the file
and line where it is written. A feature is credited only where a declared name
matches the feature's head token, the first segment that is not a
scaffolding word. The same measurement now returns zero credited.

`analyzers/fidelity.py` then reports, per feature, one of three verdicts:
`delivered`, `not_found`, or `unreachable` — defined but with nothing exposing
it, which is distinct from both and was previously invisible.

## Scope of the correction

The rule change alters which features are credited, and therefore the
hallucination count, in any cell where a suppressed route or command existed.
It is not a single-cell correction and no attempt is made here to restate
Table 4.2 under the new rule: that would be a re-analysis, not an erratum.

The published figures remain exactly reproducible. `derive(..., version=1)`
and `hallucination_analyzer.analyze(..., version=1)` retain the token rule
unchanged, which is the same arrangement already used for security density and
cyclomatic complexity after Erratum 001 (see `docs/METRICS.md`). Version 2 is
the default for new audits and is what `auditor scan` reports.

## Why the default changes rather than the rule being offered as an option

An instrument whose default setting over-credits delivery is not neutral: it
reports in the direction that flatters the code being audited, which is the
failure this project exists to measure in other tools. Leaving the old rule as
the default and the corrected one behind a flag would preserve a published
number at the cost of every future reading.

## Reproducing both

```bash
auditor scan . --brief "..."                    # version 2, the corrected rule
python -c "from auditor.analyzers.manifest_deriver import derive"   # version=1 available
python scripts/compute_kappa.py --pre-erratum002                    # κ figures of record
```
