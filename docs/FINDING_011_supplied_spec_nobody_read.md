# FINDING_011 — a supplied specification that nothing read

**Status:** fixed 24 November 2026, in 0.6.11. Pinned by
`tests/test_finding_011.py`, every test of which fails on 0.6.10.
**Found:** 24 November 2026, from an external user's report. They ran 0.6.10
on their own project, wrote up what the tool found and what it missed, and
their write-up contains the defect.
**Module:** `auditor/live/brief.py`, `auditor/core/scan.py`

## What the user saw

    1 files · 16 lines · 1 analysable

    ● │ Security    │  0.00 │ OK  0 findings
    ● │ Complexity  │  1.00 │ OK  over 3 functions
    ● │ Duplication │  0.00 │ OK  0 lines
    ● │ Scope drift │  0.00 │ OK
    measured against spec.yaml

Four green dots, a scope-drift reading of 0.00 banded OK, and a footer
asserting that the reading was measured against the specification they
supplied.

**No fidelity table was printed at all**, and nothing said why.

## What they concluded

> It successfully identified that the implementation matched the stated
> requirements.

That is a reasonable reading of that output and it is false. The tool had not
checked a single requirement. The one reading it exists to produce, the one no
tool without a specification can produce, was silently absent, and a green dot
in the row next to it stood in for the answer.

The user's own account of the limits was more careful than the tool's: they
noted that the scan did not establish the absence of vulnerabilities, that
rework was not measurable from a directory, and that signed receipts were
unavailable without the optional cryptography extra. Every one of those is
correct and the tool told them each one plainly. On the single point where the
tool misled them, they had no way to know.

## Why

Their `spec.yaml` was written the obvious way:

    project: my-project
    requirements:
      - The program must add two numbers.
      - The program must subtract two numbers.
      - The program must print the results.

The fidelity analyser reads `spec["features"]` and requires each entry to
carry an `id`. There is no `features` key here, so the feature list was empty.
Three consequences, none of them announced:

1. `_render_fidelity` returns early when `report.total` is zero, so the table
   vanished rather than reporting that it had nothing to check.
2. Scope drift counts surface that no feature asked for. With zero features
   there is nothing to compare against, so the count is **structurally
   incapable of being anything but zero**, and 0.00 bands as OK. A green pass
   earned by having read nothing. This is FINDING_005's error in a third
   place, after the severity band and the coverage check.
3. The footer still printed `measured against spec.yaml`, which was true of
   the file being opened and false of anything being measured from it.

No validation, no warning, no exit code. The file was parsed successfully and
then ignored.

## The fix

### Read the sentences out of whichever key the author used

`brief.normalise_spec` reads a list of requirement sentences from `features`,
`requirements`, `acceptance_criteria`, `user_stories`, `stories`, `must_have`
or `deliverables`, and converts them with `parse_brief`, the same function
that has always turned a typed brief into features. The user's wording is kept
verbatim in `description`; only the `id` is added.

**Why this is parsing and not inference**, which is the distinction the whole
instrument rests on: a human wrote those sentences into that file. FINDING_002
was about features invented from commit subjects, where the thing in doubt was
the brief itself. Here the brief is not in doubt. It is in a different key.

Only a list of plain strings is read. A list of dicts is a structure the tool
does not understand, and stringifying it would put `{'id': ...}` into a report
as though a person had written it.

### Withhold scope drift when the specification declares nothing checkable

If no key yields anything, the metric is skipped with a reason that names the
keys it looked for, instead of printing 0.00 and a green dot:

    ○ │ Scope drift │   n/a │ the specification declares no requirements this
      │             │       │ tool can check: expected a list of sentences
      │             │       │ under one of features, requirements,
      │             │       │ acceptance_criteria, user_stories

## The near-miss, recorded because it is the more useful half

Reading the sentences was not sufficient, and the first version of this fix
was worse than the defect.

`slugify` takes the first three meaningful words, so *"The program must add two
numbers"* became `program.add.two`. The matcher tests the head word of an id
first. Nothing in that project declares `program`, so the same correct
three-function script came back as **0 of 3 delivered**: three red crosses and
a "Missing" list, against code that implements two of the three requirements
and runs.

A false red verdict against working code is a worse failure than the silence
it replaced, and it is the FINDING_002 shape again: a derived artefact of ours
presented as a statement about their work.

The cause was already documented in `brief._STOP`, one category short. That
set already drops verbs that tell *us* to produce software, on the stated
grounds that "build a course listing page" is a requirement about the page.
A noun naming the deliverable as a whole is the same category of filler:
`program`, `application`, `app`, `software`, `script`, `system`, `project`,
`codebase` are now dropped too.

Deliberately not dropped: `page`, `site`, `report`, `service`, `dashboard`.
Each names something somebody has to go and build, which is precisely what a
fidelity verdict is looking for. Both sides of that line are pinned by
`test_the_deliverable_naming_itself_is_filler_but_a_real_noun_is_not`.

## What this still cannot do, stated rather than implied

The same project's third requirement, *"The program must print the results"*,
is reported as not found. The program does print its results, from inside
`main()`, and there is no declared definition named for it.

That verdict is literally what the tool means by `not_found` (nothing in the
codebase declares it) and the reason column says exactly that. But a
requirement satisfied by a statement rather than by a declaration is a limit
of this method, not a gap in a user's code. Fidelity reads declared names. It
does not read behaviour, and it must not be quoted as though it does.

Not fixed here. Doing so needs call-graph or behavioural evidence, which is a
larger change than this defect justifies, and a bad version of it would credit
features on weak evidence, which is ERRATUM_003.

## What may not be claimed

That a green scope-drift reading means the requirements were met. It never
meant that: the metric counts work that was *not* asked for. The reading that
answers "is anything missing" is the fidelity table, and until 0.6.11 a
specification in the wrong key removed it without saying so.
