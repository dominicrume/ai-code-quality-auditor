# Field report 001: a health-advertising assurance prototype

**Date:** 15 September 2026
**Version used:** `ai-code-quality-auditor` 0.5.0, installed from PyPI
**Who ran it:** the author's own workshop team, inside a private repository. This is
practitioner evidence from people close to the tool, not an independent evaluation.

## What was audited

A prototype that checks healthcare adverts against regulatory guidance and issues an
evidence trail for a human reviewer, built in Python over two days of a workshop week:
27 source files, about 4,040 lines. The team ran three scanners on the source with every
API key removed from the environment, so nothing could be sent or spent: Bandit and radon,
which the auditor installs, and the auditor's own composite scan. Afterwards they started
`auditor live` on the source folder.

## What it found

The figures below were reproduced independently from the repository at two commits: just
before the team acted on the scan, and just after.

| | Before | After |
|---|---|---|
| Bandit findings | 17: 1 medium, 16 low | 16: 1 medium, 15 low |
| Auditor: security (per kLOC) | 4.21 OK | 3.96 OK |
| Auditor: complexity (cc) | 4.94 WARN | 4.96 WARN |
| Auditor: duplication | 1.61% OK | 1.61% OK |
| Auditor: scope drift, rework | n/a (no brief, no captured session) | n/a |

## What mattered

**One finding the team's own line-by-line audit had missed.** The medium finding (Bandit
B310, CWE-22) was a URL opener that would accept any scheme, including `file:` paths. The
team restricted it to `https://` and added a test that a `file:` URL is refused. Bandit
still reports B310 afterwards, because the rule flags the call itself rather than the
missing check, so the accurate status is *mitigated and accepted*, not *fixed*. A second,
low-severity finding (a subprocess called by partial path) was also corrected.

**Everything else was already known.** Fifteen low findings were subprocess calls with
argument lists and fixed inputs, and a seeded random generator that is meant to be
reproducible; the team recorded them as accepted. The complexity warning pointed at a
command-line module that had grown to a thousand lines in a day, which the hand audit
had already flagged. The yield was one finding, and saying "the tool found seventeen
problems" would be exactly the overclaim this instrument exists to expose.

## What it did not do, and what changed because of it

**The composite verdict read OK while the one real finding sat underneath it.** Security
density divides findings by lines, and its warning starts at 50 per thousand lines: one
medium finding in 4,000 lines scores about 0.25 and cannot move the band. The finding was
visible only because the team also ran Bandit directly.

The auditor now names every medium- and high-severity finding beside the score, in the
command-line table, in `--json` output and on the live dashboard, with its rule, CWE, file
and line. The density value and its band are unchanged, so every published figure still
reproduces; the finding simply cannot hide inside an OK any more.

**Scope drift needs a brief.** The live dashboard sat on its "What did you ask the agent to
build?" prompt, and the scan reported scope drift as n/a. The most distinctive metric only
works once someone writes down what was asked for, and that step is the adoption gate to
design around.

## Reproduce

```
pip install ai-code-quality-auditor
auditor scan src
bandit -r src -f json -q
```
