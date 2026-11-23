# FINDING_004 — the scope-drift analyser reports its own detector vocabulary

**Status:** fixed 23 November 2026, in 0.6.4. All three required repairs
shipped, each pinned by a test in `tests/test_finding_004.py` that fails on
0.6.3. Removed from `auditor/standards/open_defects.yaml`, so receipts built by
0.6.4 and later no longer disclose it.
**Found:** 21 November 2026, by a hostile claim audit of this repository.
**Module:** `auditor/analyzers/definitions.py`, `auditor/analyzers/manifest_deriver.py`

## What happens

`auditor scan .` on this repository reports, as features nobody asked for:

    ~  export    auditor/analyzers/defin…   not asked for
    ~  name      auditor/analyzers/manif…   not asked for
    ~  add       auditor/analyzers/manif…   not asked for
    ~  /path     auditor/analyzers/manif…   not asked for

None of those is a feature. They are the strings the detectors search for,
sitting in the files that define them, being read back as findings.

## Why this one is worse than it looks

This is the defect FINDING_003 diagnosed, in a second place, after
FINDING_003 was marked fixed.

FINDING_003 set out two things a fix had to do. The first, a subject gate, was
built and holds: the governance checker now returns `NOT_APPLICABLE` on this
repository. The second was written down as:

> Exclude the instrument from its own scan, and more generally decline to credit
> a marker found only in a file whose role is to describe the standard.

That was done for `auditor/governance/`, by matching identifiers from the parsed
syntax tree instead of raw source text. It was never done for the fidelity
analysers, which still match text. So the record says fixed, and half of the
stated fix is not built.

Two related defects in the same path, found in the same audit:

- **Two distinct features credited to one identical line.** A brief asking for
  registration and log-in gets both ticked against the same `file:line`, because
  one route path matched both. `definitions.py:224` already carries a comment
  acknowledging exactly this, so it is known and unclosed.
- **A verdict that contradicts itself in one table.** A feature can be reported
  `not found` while the route that implements it is reported `not asked for`, in
  the same output, banded RISK. A reviewer sees that in ten seconds.

## What a fix has to do

Not a filter on the instrument's own paths. That would fix this repository and
leave every customer who happens to name a variable after a route unprotected.

1. **Match identifiers, not text**, in the fidelity path as in the governance
   path. A marker inside a string literal is a mention; a marker that is the
   name of something defined or called is a use. The machinery exists in
   `auditor/governance/subject.py` and is not reused here.
2. **One feature, one piece of evidence.** A line already claimed by one feature
   cannot be the evidence for another without saying so.
3. **A contradiction is a defect, not an output.** If a surface is both missing
   and unrequested, the reading is incoherent and should be withheld rather than
   banded.

## Until then

Scope drift on a codebase that contains route-like or command-like strings in
non-route positions may overstate drift. The count is not safe to quote without
reading the evidence lines. This is disclosed in every receipt through
`instrument_open_defects`, and FINDING_003's status has been corrected to say
which half of its fix shipped.

## What shipped, and where it departed from what was asked

### 1. Identifiers, not text — done differently, and deliberately

The record said to reuse the syntax-tree identifier matching from
`auditor/governance/subject.py`. That was not done, because applied here it
would have been wrong. A route's name is written *inside a string literal* by
design: in `@app.get("/orders")` the path is a string, and an identifier walk
discards every route in every codebase it reads.

What shipped instead is `auditor/analyzers/literals.py`: for each file, the
byte ranges that hold string and comment text, taken from Python's own
tokeniser where the file tokenises and from a lexical scan where it does not.
A detection is discarded when **the start of the whole construct** falls inside
one of those ranges. `@app.get("/orders")` in code starts at the `@`, which is
code; the same text in a docstring starts inside the string token. That one
distinction is the fix, and it generalises to any customer whose docstring
contains an example route, which path exclusion would not have.

It caught a second class the record had not identified. `scripts/demo_agent.py`
holds whole example codebases in string constants, and their four routes were
being counted as this repository's own surface. That is where the `4 of 4
delivered` in the finding's own reproduction came from.

### 2. One feature, one piece of evidence — done

A definition can now be the cited evidence of at most one feature. Allocation
order carries the fix: a feature with fewer candidate definitions is served
first, and among features with equally many, the one whose own words name the
definition. Given a single `POST /auth/register`, `auth.register` and
`auth.login` both match on `auth`; `register` is the word that says which of
them that line is.

When every definition a feature matches is already another feature's evidence,
the verdict is `ambiguous`, not `delivered` and not `not_found`. Something
matched, so absence would be false; the evidence is spoken for, so delivery
would be a second claim on one line.

### 3. A contradiction is a defect, not an output — done

A feature reported as nowhere declared, while the route on its own noun is
reported as unrequested, is one incoherent reading rather than two findings.
Both halves are now withheld together: the feature loses its verdict and the
route loses its accusation. `definitions.matches` takes `ignore_method` to
detect this, and that flag is never used to credit a feature — the HTTP method
is good evidence for crediting and not good enough to assert absence over.

## What this did not change

The published study figures. They were produced by `manifest_deriver.derive`
version 1, which matches tokens against a blob and is retained unchanged so
those figures stay reproducible (see ERRATUM_003). Nothing in this repair runs
in that path.

What it does change is the value of the version-2 reading, which is the default
for new audits and was not quoted in the dissertation. `completeness` can now
fall when a feature's reading is withheld, because a withheld feature counts in
the total and not in the delivered. That is the intended direction: the figure
should drop when the instrument cannot tell.
