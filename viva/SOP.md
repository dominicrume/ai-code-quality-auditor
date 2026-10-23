# How this was built, end to end

A reproducible account, in the order it happened. Anyone with this file, the
repository and three vendor accounts can rebuild the study.

---

## 0. Before anything was captured

**30 May 2026** — the standing brief was written: one analyser per metric, one
adapter per vendor, the specification externalised as data, synthetic content
only. It is `CLAUDE.md` in the repository and it is dated in git.

**31 May 2026** — `docs/EXPERIMENT_PROTOCOL.md` was committed. It fixed, before
a single capture: the five conditions, the three specifications, five metrics,
ten repetitions per cell, the statistical tests, Shapiro–Wilk and Levene as
gates, Bonferroni at α = 0.01, and the multiple-comparison policy.

**The first commit of that file is the boundary** between pilot exploration and
the dissertation result. Everything after it is bound by it; every departure is
logged in `docs/PROTOCOL_DEVIATIONS.md` with its date and its analytical
consequence.

---

## 1. The specifications

Three YAML files in `specs/`, each six features and three governance rules:

| file | domain |
|---|---|
| `agent_education_system.yaml` | CRUD + authentication web app |
| `data_pipeline.yaml` | ETL + scheduler |
| `internal_tool_cli.yaml` | command-line tool with six subcommands |

They are data, never code. No specification content is hardcoded anywhere in
the instrument — that is the rule that makes the comparison extensible.

---

## 2. The capture contract

Every condition, however different, must produce two artefacts:

```
codebase        { files: {path: content}, manifest: [feature_ids] }
interaction_log [ {type: keystroke | backspace | delete | agent_action, ...} ]
```

One adapter per vendor translates native output into that shape. The analysers
never import an adapter. Enforced at load time: a malformed event aborts the
run rather than quietly degrading a metric.

---

## 3. How each condition was captured

| condition | how |
|---|---|
| `claude_code` | driven non-interactively via `subprocess`, clean per-run directory, streamed JSON captured line by line |
| `cursor_agent` | same, under the free tier's automatic model selection |
| `replit_agent` | **no scriptable interface.** Captured by hand in the browser IDE, then loaded through a replay adapter |
| `antigravity` | **no scriptable interface.** Same, desktop IDE |
| `human_control` | hand-coded with all in-IDE AI switched off and verified; `pynput` logged the *type* of every key event, never the characters |

The replay adapters share loader and persistence code with the live ones. Only
the source of the bytes differs, so an analyser cannot tell a replay from a
live capture. **That is also the study's most serious limitation** — see
Deviation 001.

Live captures committed 31 May 2026; the full four-tool matrix 1 June 2026.

---

## 4. Running the study

```bash
pip install -e ".[all]"
auditor experiment --reps 10 --run-label main_001
```

Produces `data/reports/main_001.csv` — 600 rows — with a provenance file
beside it. One condition per row per metric per rep.

A single condition, as JSON:

```bash
auditor run --spec specs/agent_education_system.yaml \
            --workflow human_control --run-id main_001
```

---

## 5. Analysis

```bash
python scripts/compute_kappa.py --pre-erratum002
jupyter notebook notebooks/statistical_analysis.ipynb
```

The κ flag matters: **`--pre-erratum002` returns the figures of record**
(0.870 / 0.852 / 0.727), computed against the instrument as it stood when the
raters labelled. Without the flag you get the post-repair values, which are
circular and are not the result.

Everything in Chapter 4 re-derives from the frozen CSV. Nothing is typed in by
hand.

---

## 6. Validation by people who were not me

Two raters, neither of whom designed the study, built the instrument or saw
`main_001.csv`, labelled 19 deduplicated codebases independently. One capture
was empty, giving N = 18 scoreable. Both gave signed consent to be named.

The labelling tool extracted its candidate list **independently of the
instrument**. That is why Erratum 002 surfaced: had the raters been shown only
what the instrument could see, the blind spot would have agreed perfectly and
survived into the thesis.

---

## 7. What went wrong, and what was done about it

| | what happened | consequence |
|---|---|---|
| Deviation 001 | two IDE tools captured once per cell, replayed ten times | effective N = 3 each; all nominal statistics disowned; interaction test withdrawn |
| Deviation 002 | two cells deferred on 31 May | captured 1 June; the log entry was never closed — a closing note was added 22 Oct 2026, dated, not backdated |
| Deviation 003 | human baseline reduced to one session per spec | excluded from all inferential tests |
| Erratum 001 | security density counted `assert` inside test files | claude 42.05 → **9.65**, cursor 43.67 → **5.93** |
| Erratum 002 | route detector blind to TypeScript | one cell 0.00 → **1.00**; replit mean 1.00 → **1.33** |
| Erratum 003 | *(post-submission)* feature credited if its name appeared anywhere, including a comment | evidence rule replaced; `version=1` keeps published figures reproducible |
| Finding 001 | the hallucination count cannot see substitution | not an erratum; no published number changes |

---

## 8. Releasing it

```bash
python -m build
python -m twine check dist/*
python scripts/final_launch_check.py     # must read 0 failures
python -m twine upload dist/ai_code_quality_auditor-X.Y.Z*
```

`final_launch_check.py` refuses a release if the working tree is dirty, if any
module outside the opt-in sharer gains a network call, or if a report file
disagrees with Table 4.1.

---

## 9. To reproduce the whole thing from nothing

```bash
git clone https://github.com/dominicrume/ai-code-quality-auditor
cd ai-code-quality-auditor
pip install -e ".[all]"
python -m pytest -q                                   # expect 258 passed
python scripts/compute_kappa.py --pre-erratum002      # 0.870 / 0.852 / 0.727
jupyter notebook notebooks/statistical_analysis.ipynb # every Chapter 4 figure
```

Re-running the captures needs accounts with all four vendors and, for the two
IDE tools, a person at a keyboard. That is the part that is not automatable,
and it is exactly what §6.4 says must be fixed first.

---

## The one-sentence version

**Fix the brief, fix the analysis plan, capture every condition into one shape,
score it blind, log every departure, and publish the defects you find in your
own instrument.**
