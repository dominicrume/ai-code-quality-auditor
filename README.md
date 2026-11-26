# AI Code Quality Auditor

[![CI](https://github.com/dominicrume/ai-code-quality-auditor/actions/workflows/ci.yml/badge.svg)](https://github.com/dominicrume/ai-code-quality-auditor/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/ai-code-quality-auditor.svg)](https://pypi.org/project/ai-code-quality-auditor/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Downloads](https://static.pepy.tech/badge/ai-code-quality-auditor)](https://pepy.tech/projects/ai-code-quality-auditor)
[![Live dashboard](https://img.shields.io/badge/live-dashboard-purple)](https://auditor-dashboard-rume.fly.dev/report/main_001_plus_human)

**Did the agent build what you asked for?**

A linter tells you whether code is well written. None of them knows what you
asked for, so none of them can tell you the agent quietly skipped a third of
it. This does:

```
$ auditor scan .

Specification fidelity  2 of 4 delivered

✓  add an item     cli.py:9   subcommand "add"
✓  list items      cli.py:13  subcommand "list"
!  export to csv   cli.py:23  function export_csv exists, but nothing exposes it
✗  validate input             not found
~  scheduler       cli.py:19  not asked for

Missing — asked for, and nothing in the code declares it:
  · validate input (validate.input)

Built but unreachable — the code exists, nothing exposes it:
  · export to csv — function export_csv at cli.py:23
```

That block is captured from a run, not written by hand. Through 0.6.11 the example here
was hand-written, showed an insurance API, and promised two things the tool does not
produce from that code: `route POST /claims` evidence from a Flask `@app.route` decorator,
and a `✓` for a requirement the matcher actually reports as not found. It is replaced with
real output and recorded in
[`docs/FINDING_012_readme_example_was_never_run.md`](docs/FINDING_012_readme_example_was_never_run.md).

Nothing was typed to get that. The specification is read from whatever already
states intent — a requirements document, the README, the package description,
recent `feat:` commits — written to `.auditor/spec.yaml`, and yours to correct.
**Never from your source code**, because a specification inferred from the code
it measures is satisfied by that code by construction. A project that documents
nothing gets no scope reading rather than a flattering one, and so does a
project whose derived brief matches nothing in the code: that points at the
brief, and a brief the tool is not sure of is not one it will grade you
against. Pointed at its own source, this instrument declines to report scope
drift for exactly that reason.

If you write the specification yourself, the features can sit under any of
`features`, `requirements`, `acceptance_criteria`, `user_stories`, `stories`,
`must_have` or `deliverables`, as a list of plain sentences. Before 0.6.11 only
`features` was read and the rest were opened, counted as measured, and
silently ignored.

Alongside it, four conventional readings: security density, cyclomatic
complexity, duplication, and rework from a captured session. Code the analysers
could not parse is reported as `unread`, never as `OK`.

**The worst single problem decides the colour.** A high-severity finding reads
red and a medium reads amber, however much clean code surrounds it, because a
band is an instruction to a reader and not a measure of our confidence in the
finding. A false positive at amber costs somebody one review. A real finding
banded green costs them the breach. Green does not mean safe; it means nothing
above low was found in the code that could be read, by the checks that ran.

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

### If `auditor` is "not recognized" or "command not found"

The command is installed into your environment's script directory, which is
very often not on `PATH`. The tool is there; the shell cannot see it. Reported
from a Windows PowerShell session and from an unactivated virtual environment
on macOS, so it is not a platform quirk.

**This always works, on every platform, activated or not:**

```
python -m auditor scan .
```

It uses the interpreter you just named, so there is no PATH to get wrong.

| | |
|---|---|
| Windows PowerShell | `python -m auditor scan .` |
| Windows, venv not activated | `.\env\Scripts\python -m auditor scan .` |
| macOS / Linux, venv not activated | `env/bin/python -m auditor scan .` |
| Activated venv, any platform | `auditor scan .` |

Nothing else needs to change, and every command below works the same way with
`python -m auditor` in place of `auditor`.

Or put the agent governance check inside the agent you already use, so the
assessment happens where the work happens.

> Needs 0.6.2 or later. Any current release carries `auditor mcp`; if you get
> `No such command 'mcp'` you are on 0.6.1 or earlier, and `pip install -U
> ai-code-quality-auditor` fixes it. Check what you have with `auditor doctor`.


```bash
claude mcp add kya -- auditor mcp     # Claude Code
```

```json
{"mcpServers": {"kya": {"command": "auditor", "args": ["mcp"]}}}
```

Three tools appear in your own tool: `kya_assess` scores an agent against the
five KYA conformance elements with an evidence grade on each,
`kya_classify_subject` decides whether the thing in front of it is an agent at
all, and `kya_standard` states what the standard measures and what it refuses to
conclude. Point it at something that is not an agent and it returns
`NOT_APPLICABLE` with no score, which is the behaviour the check exists for.
`skills/kya-conformance/` is the companion skill for an agent that will run it.

It is a stdio MCP server speaking protocol `2024-11-05`, not a wrapper around
the scan: it answers `initialize` and `tools/list` and advertises itself as
`ai-code-quality-auditor`. You can confirm that without a client:

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"probe","version":"1"}}}' '{"jsonrpc":"2.0","method":"notifications/initialized"}' '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' | auditor mcp
```

A tool that cannot complete its reading returns that as a result with the gap
named in it, not as a protocol error, because a model that receives an error
retries and a model that receives a stated limit has to account for it.

A finding you can hand to somebody who was not there:

```bash
auditor receipt .                     # the finding, as a file, free and unlimited
auditor verify receipt.json           # check it offline, anywhere, years later
auditor verify receipt.json --require-seal   # fail a CI gate on an unsealed one
```

A receipt records what was read as content hashes and never the source, so it
proves which exact bytes were assessed without carrying a line of them. It is
unsealed: complete, self-consistent, and carrying nobody's name. Sealing needs
`pip install 'ai-code-quality-auditor[seal]'`, and a signed, dated finding comes
from the assurance engagement rather than from your own machine, because nobody
attests their own work.

Reproduce the study instead:

```bash
pip install -e ".[all]"
auditor experiment --reps 10 --run-label main_001     # full pre-registered design
auditor run --spec specs/agent_education_system.yaml \
            --workflow human_control --run-id <your-run-id>   # one condition, as JSON
python scripts/compute_kappa.py --pre-erratum002      # the κ figures of record
```

`auditor run` needs captures on disk under `data/raw/<run-id>/`, and
`data/raw` is gitignored, so a fresh clone has none: run `auditor
experiment` first, or point `--captures-root` at your own.

`compute_kappa.py --pre-erratum002` returns **0.870 / 0.852 / 0.727** — the
inter-rater agreement figures reported in the dissertation, computed against the
instrument as it stood when the raters labelled. Running it without the flag
returns the post-repair values, which are circular and are not the result; see
`docs/KAPPA_RESULTS_001.md`.

> **Reading this because of the dissertation?** *Measuring the Unmeasured* was submitted on
> 22 September 2026 and its appendix links point at `main`, which has moved on since: the
> instrument was released as 0.6.0, dashboard routes were closed, CI was repaired and the
> self-audit was re-run. The repository exactly as the dissertation describes it is tagged
> [`submission-2026-09-22`](https://github.com/dominicrume/ai-code-quality-auditor/tree/submission-2026-09-22).
> Swap `main` for that tag in any appendix URL to see what the examiner was given.

## What it reports that nothing else does

Point it at a folder. If the project documents what it is for, often nothing
needs to be typed at all: the specification is derived from that and written to
`.auditor/spec.yaml` for you to correct. When the derivation does not produce a
brief the tool can stand behind, it says so and reports no scope reading. It
then tells you, feature by feature, what arrived, what did not, and where the
evidence is:

```
$ auditor scan . --brief "add an item
list items
export to csv
validate input"

Specification fidelity  2 of 4 delivered

✓  add an item     cli.py:9   subcommand "add"
✓  list items      cli.py:13  subcommand "list"
!  export to csv   cli.py:23  function export_csv exists, but nothing exposes it
✗  validate input             not found
~  scheduler       cli.py:19  not asked for

Missing — asked for, and nothing in the code declares it:
  · validate input (validate.input)

Built but unreachable — the code exists, nothing exposes it:
  · export to csv — function export_csv at cli.py:23
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
Run on this repository's own source on 26 November 2026, with 0.6.12:

```
$ auditor scan auditor
  68 files · 9,991 lines · 65 analysable
  Security     1.74 per kLOC   OK     17 findings, none above low
  Complexity   4.68 cc         WARN   over 396 functions
  Duplication  4.03 %          OK     331 lines
  Scope drift  n/a                    nothing yet says what was asked for
  Rework       n/a                    needs a captured session
```

Two of those five are not numbers, and that is the reading, not a gap in it. Pointed at
its own source the instrument cannot establish what this project was asked to build: the
brief it derived matched nothing in the code, which points at the brief rather than at the
code, so it withholds scope drift instead of printing a flattering zero. On the
best-documented project it will ever see, the derivation came up empty. Rework is not
measurable from a directory at all.

For comparison, the same scan on 14 October 2026 with 0.6.0, over 44 files and 3,971
lines, read `Security 2.82 OK` with 14 findings of which one was medium, `Complexity 4.31
WARN` over 212 functions, and `Duplication 6.64% WARN`. The codebase has since more than
doubled. Complexity rose, duplication and security density fell, and the medium finding is
gone — see below, because what happened to it is the more interesting half.

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

**The medium finding we called a false positive was pointing at a real hole one line
further on.** This is the part of the self-audit worth reading, and it did not go the way
we first wrote it up.

Through 0.6.10 this README said the finding was our scanner being wrong about us. It
flagged `core/share.py:97` for opening a URL without restricting the scheme (B310,
CWE-22); the line above rejects anything that is not `https://`, so the `file:` path the
rule warns about cannot be reached. That reasoning was correct and the conclusion was
wrong. The guard checks the URL you pass in. It does not check where that URL sends you.
A redirect from an `https://` address to any other scheme walked straight through a
function whose docstring promised it could not. The field report had the right line and
the wrong reason, and the version that dismissed it as noise was the version with the
defect in it. Recorded in full at
[`docs/FINDING_010_https_promise_broken_by_redirect.md`](docs/FINDING_010_https_promise_broken_by_redirect.md)
— including that a published false-positive claim had to be withdrawn.

So the current reading shows 17 findings and none above low: the medium is gone because
the hole was closed, not because the detector was taught to agree with us. We still do
not suppress rules on our own code. Teaching a detector to recognise one particular
guard, on the codebase that wrote the guard, is how an instrument starts agreeing with its
author, and a scanner with no false positives at that cost is a scanner fitted to someone's
code. What this episode changed is cheaper and harsher: a finding we have reasoned our way
past is still a finding, it still gets named beside the band, and since 0.6.11 a medium
holds the band at amber while we are being clever about it.

The same pass over three neighbouring codebases, for calibration. These are the 0.6.0
readings from 14 October 2026 and have not been re-run; the `auditor/` row is therefore
the old figure, not the one above, and the three external codebases have moved on since:

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
dissertation's §4.8 field audit scores the *whole repository* as it stood at submission
(141 files, 13,136 lines, including scripts, tests and tooling) and reports 3.14 security,
3.58 complexity, 4.01% duplication and 12 scope drift. Those are the figures of record and
are not restated here, because a figure in a submitted dissertation is corrected by an
erratum and not by an edit. The repository at that state is tagged
`submission-2026-09-22`; a whole-repository scan today reads 290 files and 69,186 lines, of
which 152 are analysable, and answers a different question about a different tree. Neither
is wrong, and a metric that did not move when you changed what you pointed it at would be
useless. Always state the scanned path and the version alongside the number.

## What it will not tell you

Run `auditor doctor` and it prints this list for your installation, including any open
defect that could affect the numbers you just read. As of 0.6.12:

- **Duplication is overstated on any repository that ships built assets beside their
  source**, and security findings are counted twice where the same code appears in both
  trees. This is open, it is
  [`FINDING_008`](docs/FINDING_008_duplicated_source_tree_counted_as_duplication.md), and
  it is disclosed in every receipt the tool writes. Read the duplicated paths before
  quoting the figure. Fixing it moves a figure already published, so it needs an erratum
  rather than a patch.
- **Security and complexity are Python-only**, via `bandit` and `radon`. On a JavaScript
  codebase the honest reading is "per-language vulnerability density", never "zero
  vulnerabilities".
- **The density bands are loose.** Security warns at 50 findings per 1,000 lines, which is
  one every twenty lines, so density alone reads green almost everywhere. What makes a
  security band move in practice is the severity floor, not the density.
- **Fidelity reads declared names, not behaviour.** A requirement satisfied inside another
  function, with nothing declaring it, reads as not found. The tool can tell you a name is
  absent; it cannot tell you the thing works.
- **Flask routes are not read as routes.** The Python detector recognises the
  `@app.get(...)` / `@app.post(...)` decorator family, so FastAPI and Typer surfaces cite
  `route POST /claims`. Flask's `@app.route("/claims", methods=["POST"])` does not match
  it, and the endpoint is cited as `function submit_claim` instead. The feature is still
  found; the evidence is weaker than it should be.
- **A requirement whose first word is a verb the code does not use may read as not
  found.** "Look up a claim by reference" becomes `look.up.claim`, and nothing in a
  codebase declares `look`, so a requirement that *is* implemented reads `✗`. This is the
  unfinished half of
  [`FINDING_011`](docs/FINDING_011_supplied_spec_nobody_read.md): a false red against
  working code is worse than a silence, and it is open.
- **Rework needs a captured session.** It is not measurable from a directory, and is
  reported as `n/a` rather than as zero.
- **A reading is not an attestation.** It is unsigned, undated in any binding sense, and
  addressed to nobody.

Every numbered defect above is in `docs/`, named, with the version that carried it. We
publish them because an instrument that hides its own findings cannot be trusted with
anyone else's.

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
other sixteen findings were already known. The composite security score read OK anyway,
because at the time no single finding could move a density band. Two changes came out of
that: the auditor names every medium and high finding beside the score, and since 0.6.11 a
medium floors the band to amber and a high floors it to red, however much good code
surrounds it. A known problem under a green badge is a clean bill of health the instrument
has not earned. Full account, including what the tool did not do:
[`docs/FIELD_REPORT_001.md`](docs/FIELD_REPORT_001.md).

On 24 November 2026 an entrant in a public challenge ran 0.6.10 over a three-function
script and got four green dots, `Scope drift 0.00 OK`, and a footer saying `measured
against spec.yaml`. The tool had opened their specification, reported it as measured, and
read none of it: their requirements sat under a `requirements:` key and the analyser
wanted `features:`. They concluded the implementation matched the requirements. It had
never been checked. 0.6.11 reads the sentences from whichever key holds them and withholds
the scope reading, by name, when it can read none —
[`docs/FINDING_011_supplied_spec_nobody_read.md`](docs/FINDING_011_supplied_spec_nobody_read.md),
including the false red the first version of that fix produced against working code.

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
