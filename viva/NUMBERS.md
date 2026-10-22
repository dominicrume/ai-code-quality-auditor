# Every number you might say out loud

Verified 22 October 2026 by recomputation from the frozen CSVs, not quoted
from the text. If a figure is not on this page, do not state it from memory —
say "that is in chapter four and I would want to check it rather than guess."

## The study

| | |
|---|---|
| Conditions | 5 (4 agent + `human_control`) |
| Specifications | 3, pre-registered, externalised as YAML |
| Agent runs | 120 · **600 metric rows** |
| With human baseline | **615 rows** |
| Cell coverage | 10 reps in **all 12** condition × spec cells |
| **Effective** independent agent sessions | **66** — two conditions are replays |

## Means across the three specifications

| metric | antigravity | claude_code | cursor_agent | human_control | replit_agent |
|---|---|---|---|---|---|
| security density /kLOC | 1.47 | **9.65** | 5.93 | 0.00 | 0.00 |
| complexity, mean cc | 2.60 | 3.35 | 2.72 | **2.24** | 2.39 |
| duplication % | 4.26 | 0.00 | 0.90 | 0.00 | **9.56** |
| hallucinations, count | 0.33 | 0.00 | 0.17 | 0.00 | **1.33** |
| correction freq /1k keys | — | — | — | 334.45 | — |

## Hallucinations per specification — where the finding lives

| condition | education web app | data pipeline | **internal tool CLI** |
|---|---|---|---|
| antigravity | 1.00 | 0.00 | **0.00** ← Finding 001 |
| claude_code | 0.00 | 0.00 | 0.00 |
| cursor_agent | 0.50 | 0.00 | 0.00 |
| replit_agent | 1.00 | 0.00 | **3.00** ← headline |

**The sentence to say:** *"Antigravity and Claude Code both score 0.00 on the
CLI brief. One built the CLI. The other built a data pipeline."*

## The one inferential result

| | |
|---|---|
| Complexity, claude_code vs cursor_agent | U = 641.5, **p = 0.0047**, r = −0.426 |
| N | 30 per condition, **both arms genuinely replicated** |
| α | pre-registered 0.01 |
| Volunteer this | a four-metric correction is α = 0.0025 — **it would not survive** |

Duplication claude vs cursor is also significant (U = 330.0, p = 0.0028) but
weaker in kind: claude_code is 0.00 in all 30 rows, so the test compares a
constant against a distribution. Say so if you cite it.

Not significant: hallucinations p = 0.0419, security p = 0.3668.

## Pseudoreplication, the three levels

| | duplication | security | hallucinations | complexity |
|---|---|---|---|---|
| Level 1, nominal N=30 — **disowned** | p = 1.8e-13 | 9.2e-6 | 9.9e-9 | 7.3e-3 |
| Level 3, corrected N=3 | p = 0.096 | 0.151 | 0.328 | 0.760 |

**"Level 3 is a power result, not a null result."** Say it in those words.

## Reliability

| | |
|---|---|
| Items | 19 deduplicated, **18 scoreable** (item_04 SKIP) |
| Rater 1 × Rater 2 | **κ = 0.870** (94.4% raw) |
| Rater 1 × instrument | **0.852** |
| Rater 2 × instrument | **0.727** |
| Validated for | **detection, not magnitude** |
| Never quote | the post-repair 1.000 / 0.870 — circular |

## Corrections you should name before they do

| figure | was | is | source |
|---|---|---|---|
| security, claude_code | 42.05 | **9.65** | Erratum 001 — 77% was test assertions |
| security, cursor_agent | 43.67 | **5.93** | Erratum 001 |
| replit × education hallucinations | 0.00 | **1.00** | Erratum 002 |
| replit hallucination mean | 1.00 | **1.33** | Erratum 002 |
| self-audit scope drift | 19 | **12** | §4.8.1, wrong brief used |

## The instrument today

| | |
|---|---|
| Released version | **0.6.0**, 22 October 2026 |
| Tests | **258 passing** |
| Downloads, lifetime | **4,113** — *about 1,305 excluding mirrors* |
| Downloads, last 30 days | 1,031 — *about 250 real* |
| Source | 50 modules, ~6,000 lines, 30 test files |
| Errata | 3 · Deviations | 3 · Findings | 1 |

**Never quote 4,113 without the second number.** If asked how many are real,
"about thirteen hundred" is the honest answer and knowing the difference is
worth more than the bigger figure.
