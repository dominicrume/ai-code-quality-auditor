# AI Code Quality Auditor — the Referee Tool

[![CI](https://github.com/dominicrume/ai-code-quality-auditor/actions/workflows/ci.yml/badge.svg)](https://github.com/dominicrume/ai-code-quality-auditor/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/ai-code-quality-auditor.svg)](https://pypi.org/project/ai-code-quality-auditor/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Downloads](https://static.pepy.tech/badge/ai-code-quality-auditor)](https://pepy.tech/projects/ai-code-quality-auditor)
[![Live dashboard](https://img.shields.io/badge/live-dashboard-purple)](https://auditor-dashboard-rume.fly.dev/report/main_001_plus_human)

> An empirical Safety Harness for agentic AI coding systems.
> Quantifies where AI-assisted development fails at governance, security,
> and ethical alignment — *before* the code reaches production.

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
          run-id: ${{ github.run_id }}
          conditions: claude_code,cursor_agent
```

**📊 Live dashboard:** https://auditor-dashboard-rume.fly.dev/report/main_001_plus_human

This is the experimental instrument for the MSc dissertation
**"AI-Assisted Coding Assessment Tool: Evaluating LLM Performance, Governance,
and Security in an Agent Education System"** (Aston University, MSc AI &
Business Strategy). The same instrument is the working prototype for the
PhD extension at the Aston-Capgemini Centre of Excellence for Enterprise AI.

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
auditor scan . --spec spec.yaml               # adds the scope-drift check
auditor scan . --fail-on critical             # gate a CI pipeline
auditor live .                                # watch a folder on a dashboard
```

Reproduce the study instead:

```bash
pip install -e ".[all]"
auditor experiment --reps 10 --run-label main_001     # full pre-registered design
auditor run --spec specs/agent_education_system.yaml \
            --workflow human_control --run-id main_001   # one condition, as JSON
python scripts/compute_kappa.py --pre-erratum002      # the κ figures of record
```

`compute_kappa.py --pre-erratum002` returns **0.870 / 0.853 / 0.727** — the
inter-rater agreement figures reported in the dissertation, computed against the
instrument as it stood when the raters labelled. Running it without the flag
returns the post-repair values, which are circular and are not the result; see
`docs/KAPPA_RESULTS_001.md`.

## Case study: the instrument audits its own maker

The fastest way to judge a measuring instrument is to point it at the person holding it.
Run on this repository's own source, on 12 September 2026:

```
$ auditor scan auditor
44 files · 3,971 lines · 44 analysable

  Security     3.27 per kLOC   OK
  Complexity   3.94 cc         WARN
  Duplication  9.54 %          WARN
```

These figures move as the code does — adding the shape detector took duplication
from 10.24% (RISK) to 9.54% (WARN) simply by adding lines that are not duplicated.
A self-audit is a reading taken at a commit, not a badge; re-run it rather than
trusting a number in a README.

**We publish the warning rather than tuning it away**, because an instrument that hides
its own findings cannot be trusted with anyone else's. Locating the duplication took one
pass: it is dominated by 24 shingles shared across the four vendor adapters, plus 10
shared between `dashboard/app.py` and `live/server.py`.

Those two findings get opposite verdicts, and saying so is the point:

- **Accepted.** The adapters are deliberately thin files of one shape — one per vendor,
  each translating native output into the capture contract. Their similarity *is* the
  architecture (see Principles below). Collapsing them into a clever abstraction would
  buy a better duplication score and a worse codebase.
- **Scheduled.** The dashboard/live overlap is genuine drift between two servers that
  grew apart, and it is queued for a shared core.

The same pass over three neighbouring codebases, for calibration:

| Codebase | Files / lines | Security (per kLOC) | Complexity | Duplication |
|---|---|---|---|---|
| this repo (`auditor/`) | 43 / 3,711 | 3.50 OK | 3.87 WARN | 10.24% RISK |
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
