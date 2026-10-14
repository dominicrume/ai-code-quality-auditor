# AI Code Quality Auditor — the Referee Tool

[![CI](https://github.com/dominicrume/ai-code-quality-auditor/actions/workflows/ci.yml/badge.svg)](https://github.com/dominicrume/ai-code-quality-auditor/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/ai-code-quality-auditor.svg)](https://pypi.org/project/ai-code-quality-auditor/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Downloads](https://static.pepy.tech/badge/ai-code-quality-auditor)](https://pepy.tech/projects/ai-code-quality-auditor)
[![Live dashboard](https://img.shields.io/badge/live-dashboard-purple)](https://auditor-dashboard-rume.fly.dev/report/main_001_plus_human)

> An empirical Safety Harness for agentic AI coding systems.
> Quantifies where AI-assisted development fails at governance, security,
> and ethical alignment — *before* the code reaches production.

> **Reading this because of the dissertation?** *Measuring the Unmeasured* was submitted on
> 22 September 2026 and its appendix links point at `main`, which has moved on since: the
> instrument was released as 0.6.0, dashboard routes were closed, CI was repaired and the
> self-audit was re-run. The repository exactly as the dissertation describes it is tagged
> [`submission-2026-09-22`](https://github.com/dominicrume/ai-code-quality-auditor/tree/submission-2026-09-22).
> Swap `main` for that tag in any appendix URL to see what the examiner was given.

**🟢 Try it in 30 seconds:**
```bash
pipx install ai-code-quality-auditor
auditor --help
```

**🚀 Or wire it into your CI in 6 lines** (`.github/workflows/auditor.yml`):
```yaml
jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: dominicrume/ai-code-quality-auditor@main
        with:
          spec: spec.yaml       # optional; turns on the scope-drift check
          fail-on: never        # raise to warn or critical once you have a baseline
```
It scans the tree you just checked out, writes the findings to the job summary
and uploads a JSON decision record. It fails nothing until you ask it to.

**📊 Live dashboard:** https://auditor-dashboard-rume.fly.dev/report/main_001_plus_human

This is the experimental instrument for the MSc dissertation
**"Measuring the Unmeasured: An Empirical Instrument for Auditing the
Code-Quality and Governance Behaviour of Agentic AI Coding Workflows"**
(Aston University, MSc AI & Business Strategy, September 2026). The same
instrument is the working prototype for the PhD extension at the
Aston–Capgemini Centre of Excellence for Enterprise AI.

---

## What it does
Given a fixed specification (the "spec box"), the Auditor:
1. Runs five workflow conditions against the same brief — a hand-coded
   `human_control` baseline plus four commercial agentic tools: `claude_code`,
   `cursor_agent`, `replit_agent` and `antigravity`.
2. Captures every produced file and every interaction event through one capture
   contract, so a human's keystrokes and an agent's tool-calls become comparable.
3. Scores each result on five metrics: security-vulnerability density, cyclomatic
   complexity, code duplication, specification-hallucination count (scope drift),
   and keystroke-correction frequency.
4. Emits CSV/JSON for statistical comparison.

The analysers never see which condition produced the code they are scoring —
the comparison is blinded by interface design, not by discipline.

## Quick start
Audit any folder you already have, in one command:

```bash
pip install ai-code-quality-auditor
auditor scan .                                # the four spec-free metrics
auditor init                                  # say what you asked for, once
auditor scan .                                # now with scope drift, every run
auditor scan . --brief "a CLI with add and list"   # or say it inline, no setup
auditor scan . --fail-on critical             # gate a CI pipeline
auditor scan . --include-all                  # measure ignored files too
auditor live .                                # watch a folder on a dashboard
auditor history                               # every scan this machine has recorded
auditor history --project myapp               # one folder, with the change between scans
auditor forget --all                          # delete that history, and the random ids
auditor share                                 # see what an opt-in share would contain
```

Reproduce the study instead:

```bash
pip install -e ".[all]"
auditor experiment --reps 10 --run-label main_001     # full pre-registered design
auditor run --spec specs/agent_education_system.yaml \
            --workflow human_control --run-id main_001   # one condition, as JSON
python scripts/compute_kappa.py --pre-erratum002      # the κ figures of record
```

`compute_kappa.py --pre-erratum002` returns **0.870 / 0.852 / 0.727** — the
inter-rater agreement figures reported in the dissertation, computed against the
instrument as it stood when the raters labelled. Running it without the flag
returns the post-repair values, which are circular and are not the result; see
`docs/KAPPA_RESULTS_001.md`.

## What it reports that nothing else does

Point it at a folder and say what you asked for. It tells you, feature by
feature, what arrived, what did not, and where the evidence is:

```
$ auditor scan . --brief "add an item
list items
export to csv
validate input"

Specification fidelity  2 of 4 delivered

✓  add.item        cli.py:7    subcommand "add"
✓  list.items      cli.py:13   subcommand "list"
!  export.csv      cli.py:17   function export_csv exists, but nothing exposes it
✗  validate.input              not found
~  scheduler       cli.py:20   not asked for

Missing: validate.input — asked for, and nothing in the code declares it.
Built but unreachable: export.csv — the code exists, nothing exposes it.
```

A linter cannot produce this, because a linter does not know what was asked
for. The three verdicts are deliberate: `unreachable` code is neither
delivered nor missing, and calling it either discards the most useful thing
the audit knows, which is where the work already is.

Every claim cites a file and a line. Before 0.6.0 a feature was credited when
its name appeared anywhere in the codebase, including in a comment, which
credited all six features of a CLI specification to an ETL script that
implemented none of them. That defect and its correction are recorded in
`docs/ERRATUM_003_token_evidence.md`.

## Case study: the instrument audits its own maker

The fastest way to judge a measuring instrument is to point it at the person holding it.
Run on this repository's own source, on 14 October 2026, with 0.6.0:

```
$ auditor scan auditor
  Security     2.82 per kLOC   OK     14 findings: 1 medium, 13 low
  Complexity   4.31 cc         WARN   over 212 functions
  Duplication  6.64 %          WARN   275 lines
```

These figures move as the code does, and two of them moved in 0.6.0 because the
instrument was corrected rather than because the code changed. Duplication went
10.24% → 9.54% when the shape detector added lines that are not duplicated,
9.54% → 7.84% when the dashboard/live overlap below was resolved by deletion,
and 7.84% → 6.64% when the metric stopped counting Markdown as code. The
version that reports a figure is part of the figure. A self-audit is a reading
taken at a commit, not a badge; re-run it rather than trusting a number in a
README.

Pointed at the whole repository rather than at `auditor/`, 0.5.1 reported
`Duplication 83.58 RISK`. That was a true count of `data/raw`, a frozen set of
research captures git ignores and the package does not ship, and it is the
defect that 0.6.0's ignore handling fixes. It is recorded here because an
instrument that hides its own false alarms is not one to trust with yours.

**We publish the warning rather than tuning it away**, because an instrument that hides
its own findings cannot be trusted with anyone else's. Locating the duplication took one
pass: it was dominated by 24 shingles shared across the four vendor adapters, plus 10
shared between `dashboard/app.py` and `live/server.py`.

Those two findings got opposite verdicts, and saying so is the point:

- **Accepted.** The adapters are deliberately thin files of one shape — one per vendor,
  each translating native output into the capture contract. Their similarity *is* the
  architecture (see Principles below). Collapsing them into a clever abstraction would
  buy a better duplication score and a worse codebase.
- **Resolved, and it mattered.** The dashboard/live overlap was two copies of the same
  routes. Chasing the duplication score is what surfaced *why* they were duplicated: the
  public report viewer had inherited `/api/scan` and `/api/drift/acknowledge` from the
  local live server, where they are safe because that server binds to 127.0.0.1. On the
  public host they were reachable with no authentication — one would walk any path the
  container could read, the other would write to a file on the server. Nothing called
  either. Deleting them closed the exposure and took duplication to 7.84%. A structural
  metric found a security defect that the security metric did not.

**The one medium finding is our scanner being wrong about us,** and it stays on the
record as such. It flags `core/share.py:97` for opening a URL without restricting the
scheme (B310, CWE-22). The line above it rejects anything that is not `https://`, so the
`file:` path the rule is warning about cannot be reached. This is the mirror of
[`docs/FIELD_REPORT_001.md`](docs/FIELD_REPORT_001.md), where the same rule caught a
genuine one. We are not suppressing it: teaching the detector to recognise this
particular guard, on the codebase that wrote the guard, is how an instrument starts
agreeing with its author. A scanner with no false positives at this cost is a scanner
that has been fitted to someone's code.

The same pass over three neighbouring codebases, for calibration:

| Codebase | Files / lines | Security (per kLOC) | Complexity | Duplication |
|---|---|---|---|---|
| this repo (`auditor/`) | 44 / 3,971 | 3.27 OK | 3.94 WARN | 9.54% WARN |
| a Next.js app (`app/`) | 20 / 2,372 | 1.69 OK | 4.16 WARN | 2.11% OK |
| its components | 54 / 4,913 | 0.81 OK | 3.25 WARN | 5.57% WARN |
| a Node agent pipeline | 47 / 5,531 | 0.00\* OK | 4.02 WARN | 6.45% WARN |

\* A per-language artifact, not a security win: the codebase is JavaScript and the
scanner reads Python. The dissertation documents this caveat, and the honest reading is
"per-language vulnerability density", never "zero vulnerabilities". Reporting that
plainly is the same discipline as publishing our own RISK.

**Scope note.** The figures above score `auditor/` — the instrument's own source. The
dissertation's §4.8 field audit scores the *whole repository* (141 files, 13,136 lines,
including scripts, tests and tooling) and reports 3.14 security, 3.58 complexity, 4.01%
duplication and 12 scope drift. Neither figure is wrong; they answer different questions,
and a metric that did not move when you changed what you pointed it at would be useless.
Always state the scanned path alongside the number.

## When a reading is not enough

Everything above is a reading. It is reproducible, it is honest about its own
false positives, and it costs nothing. It is also not signed, not dated, and
not addressed to anybody, which means it is not the thing a regulator, a board
or an acquirer asks for.

When the finding has to carry a name and a date, that is a different piece of
work: one agent or workflow assessed against the Know Your AgenticAi standard,
with a decision map of what the agent may decide alone, an auditability score,
an accountability chain with named owners, a regulator-readiness verdict and a
remediation plan. The framework is a pending UK patent application,
GB2611754.9.

**[The assurance engagement →](https://rumedominic.com/assurance)**

The instrument stays free and open source either way. That is deliberate: a
measurement you have to pay for is a measurement you cannot check.

## In the field

On 15 September 2026 a workshop team installed 0.5.0 from PyPI into a private
health-advertising prototype (27 files, about 4,040 lines). The scan surfaced one real
medium finding their own audit had missed: a URL opener that accepted `file:` paths. The
other sixteen findings were already known. The composite security score still read OK,
because one finding cannot move a density band, so the auditor now names every medium and
high finding beside the score. Full account, including what the tool did not do:
[`docs/FIELD_REPORT_001.md`](docs/FIELD_REPORT_001.md).

## Read in this order
1. `docs/ARCHITECTURE.md` — how the pieces fit
2. `docs/METHODOLOGY.md` — how an experiment is run
3. `docs/METRICS.md` — what each metric means and how it's computed
4. `docs/ETHICS.md` — GDPR, synthetic data, academic integrity
5. `docs/DISSERTATION_LINKAGE.md` — which folder serves which proposal section
6. `docs/ROADMAP.md` — the PhD extension (API security + enterprise risk)

## Principles
- One analyzer per metric. One adapter per AI workflow. Single responsibility.
- The spec is data, not code — externalised in `specs/` for reproducibility.
- Synthetic data only. No PII, no proprietary corporate records, ever.
- Every analyzer has a test. Green tests = trustable experiment.
