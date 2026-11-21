# FINDING_004 — the scope-drift analyser reports its own detector vocabulary

**Status:** open. Recorded the day it was found, and disclosed in every receipt
until it is closed.
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
