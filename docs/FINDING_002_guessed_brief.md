# Finding 002: a guessed brief, reported as a measurement

**Found:** 23 October 2026, by a user, in the field.
**Affects:** `auditor live` and `auditor scan` when no specification is supplied.
**Published dissertation figures affected:** none. See "Scope" below.
**Fixed in:** 0.6.1.

## What the user saw

A user opened the live view on a folder of working documents. The page
reported:

```
Specification fidelity          0 of 12 delivered
```

followed by twelve red crosses, among them "finalise the contract and
Ouaknine notes to paste-ready", "the 'why this role' screening answer for the
NHS service desk" and "add the Moonsong validation". Each was marked
`not found`, and a red block beneath restated all twelve as "asked for, and
nothing in the code declares it".

None of those twelve things is a software feature, nobody had asked for them
in that folder, and the reading was meaningless.

## Why it happened

When no specification is supplied, the instrument derives a provisional one
from whatever in the project states intent (`auditor/live/discover.py`). The
sources are tried in order of strength: a requirements document, then the
README, then the package metadata, then -- last and weakest -- the subjects
of recent `feat:` commits.

That last source is guarded by its own docstring: *"a commit says what was
done, which is only evidence of what was asked for."* The guard was accurate
and insufficient. The folder was a documents repository whose commits were
written `feat: <errand>`, so discovery harvested twelve errands, capped at
`MAX_FEATURES`, and handed them to the fidelity analyser as a specification.

The analyser then did its job correctly. It looked for a command or a route
implementing "finalise the contract", found none, and recorded `not found`
twelve times over.

## The defect, stated precisely

The defect is not in discovery, and not in the analyser. It is that **the
instrument reported a verdict derived from a guess with the same confidence
as a verdict derived from evidence.**

A specification the caller supplies is evidence. Scored against it, zero
delivered is a finding, and the study contains one: given a CLI
specification, an agent shipped a data pipeline and delivered none of the six
declared subcommands (FINDING_001, §4.3.1).

A specification the instrument guessed is not evidence. Scored against it,
zero delivered says far more about the guess than about the code. Every
feature unmatched is the signature of having read intent off the wrong thing.

The dissertation already states the governing principle, at §4.8.1: *a scope
drift figure is only as good as the brief behind it*, and the evidence README
declines to report two readings for exactly this reason. The principle was
written down and not enforced in code.

## The fix

One rule, narrow and deliberate:

> A discovered specification that matches nothing has falsified itself. The
> fidelity verdict and the scope-drift count are both withdrawn, together,
> because both rest on the same brief.

The condition requires **both** that the specification was discovered rather
than supplied, **and** that not one feature matched. Anything a caller hands
in is reported exactly as before, including zero.

Where a verdict used to be, the user now gets the reason and the remedy:

```
Intent unknown: Could not establish what this project was asked to build. The
provisional brief read from recent feat: commits matched nothing in the code,
which points at the brief rather than at the code. Scope drift is not
reported. Supply a specification with --spec, or write one into
.auditor/spec.yaml, and it will be.
```

## Scope

No figure in the dissertation changes. Every reading reported in Chapter 4
was scored against one of the three fixed specifications in `specs/`, all of
them supplied. Auto-discovery is a 0.6.0 feature, built after submission, and
no published number depends on it.

The field audits of §4.8 were each scored against that project's own
specification, supplied, and are unaffected. Plates F.10 and F.11 remain
excluded from the findings for the reason already recorded in the evidence
README: the specification behind them was not retained.

## Regression tests

`tests/test_scan.py`

- `test_guessed_brief_that_matches_nothing_is_withdrawn`
- `test_scope_drift_is_withdrawn_with_the_brief_it_rested_on`
- `test_a_supplied_brief_still_reports_zero_delivered`

The third is the important one. It pins the behaviour the fix must not break:
a supplied specification with nothing delivered still reports zero, because
that is the study's central result.

## What this cost, and what it bought

Reported by a user rather than caught by the suite, on a folder the author
would not have thought to test. That is the honest version: the instrument
shipped a reading it had no basis for, and somebody outside the project saw
it before anybody inside did.

It is also the fourth defect this instrument has had found in it and written
up rather than quietly patched, and the argument of §5.4 applies unchanged.
An instrument built to audit whether generated code stays inside its brief
earns the right to make that audit only by being demonstrably honest about
the readings it cannot support.
