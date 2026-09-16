> **Generated file — do not edit.**
> Extracted from `DISSERTATION_FULL.md` on 2026-09-17 by
> `scripts/split_chapters.py`. Edit the master and re-run; any change made
> here is overwritten. The master is the submission artefact.

---

# Chapter 4: Results

## 4.1 Overview

The four agentic conditions produced 600 metric observations: 4 conditions × 3
specifications × 10 replications × 5 metrics. That comparison is the primary
analysis. The `human_control` baseline is reported separately in §4.6 as a
single-rep reference point.

## 4.2 Headline cross-vendor comparison

Table 4.1 gives each metric's mean over the nominal N = 30 per condition. The
two IDE-bound conditions contribute three effective sessions each under the
replay design (Deviation 001); §4.5 analyses what that costs. Lower is better on
every row except complexity, which is two-sided (§2.3).

**Table 4.1** Headline cross-vendor comparison: metric means over the nominal
N = 30 per condition (10 replications × 3 specifications).

| Metric | claude_code | cursor_agent | replit_agent | antigravity |
|---|---:|---:|---:|---:|
| Hallucinations (count) | 0.00 | 0.17 | 1.33 | 0.33 |
| Cyclomatic complexity (cc) | 3.35 | 2.72 | 2.39 | 2.60 |
| Code duplication (%) | 0.00 | 0.90 | 9.56 | 4.26 |
| Security density (per kLOC) | 9.65 | 5.93 | 0.00 | 1.47 |
| Keystroke correction (per 1k) | 0.00 | 0.00 | 0.00 | 0.00 |

![Per-condition means with bootstrap confidence intervals](figures/fig_4_1_condition_means.png)

**Figure 4.1** Per-condition means with bootstrap 95% confidence intervals
(10,000 replicates). Keystroke correction is omitted, being structurally zero for
every agentic condition. The intervals for `replit_agent` and `antigravity`
collapse to a point by construction: those conditions contribute one captured
session per specification (Deviation 001, analysed in §4.5).

![Distribution of every run, by condition and metric](figures/fig_4_2_distribution.png)

**Figure 4.2** Every run plotted, by condition and metric, with the condition
mean marked. Open points are the two IDE-bound conditions, whose ten runs per
cell are replays of one captured session; filled points are independently
captured. The difference between a column of independent measurements and a
column of copies is the clearest statement of what this design supports.

No column wins every row. Claude Code wins on hallucinations and duplication.
Complexity needs interpretation because it is two-sided, and security density
because Replit's apparent lead is an artefact explained below. The fifth metric is
structurally zero for every agentic condition and becomes interpretable only
against the human baseline (§4.6). The conditions occupy different trade-off
profiles rather than one ranking.

## 4.3 Per-metric findings

**Hallucinations.** Claude Code shipped zero off-spec features across all 30
runs. Cursor averaged 0.17, occasional "helpful" `/health` or `/metrics`
endpoints on the web-app spec. Antigravity averaged 0.33, all on that same spec,
as unrequested root and admin-style routes. Replit Agent averaged 1.33, the
largest gap in the table and the study's most consequential finding.

The counts hide a qualitative difference. Cursor's and Antigravity's extras are
*helpful overreach*. Replit's are *architectural substitution*, which the
per-spec breakdown in §4.4 makes visible.

*4.3.1 The Replit architectural-prior finding.* The `internal_tool_cli`
specification asks for six subcommands: `init`, `add`, `list`, `export`,
`validate`, `help`. Given that brief, in a fresh isolated workspace, under an
instruction that explicitly prohibited pipeline output, Replit Agent shipped a
*data-pipeline CLI*: `run`, `schedule` and `check-config` around a `run_pipeline`
routine. The intersection with the specification is empty.

The controls are what make this matter. The workspace was confirmed clean before
capture and the prompt forbade the pipeline shape, so neither contamination nor
an ambiguous brief explains it. It is recorded as *measured architectural-prior
dominance* (analytical note 001): the agent's pretrained scaffolding bias is
strong enough to override an unambiguous specification that contradicts it.

This is the result that most sharply illustrates the thesis. A functional
benchmark would record only whether the produced pipeline's tests passed, and is
structurally incapable of noticing that the wrong artefact was built. One caveat
is carried openly: this cell is an effective singleton under the replay design,
so its ten listed replications are mechanical copies of one session and add no
independent evidence of stability. The finding rests on the controlled capture
conditions and on direct code inspection. A live multi-session re-capture is the
stated next step (§6.4).

![What the specification asked for, and what was shipped](figures/fig_4_3_replit_evidence.png)

**Figure 4.3** The finding in full. Left, the six subcommands declared in
`internal_tool_cli.yaml`. Right, the three shipped by `replit_agent` in the
captured session, with the pipeline package supporting them. The intersection is
empty. Both columns are read directly from the specification file and the frozen
capture, so the figure cannot drift from its evidence.

**Cyclomatic complexity.** Claude Code produced the densest code, mean McCabe
3.35, and Replit the least, 2.39. The gap of roughly one cc unit holds across all
three specifications. The reading is "denser, not worse". Claude's single-file
style inlines control flow that other tools spread across modules, which raises
the per-function path count without necessarily harming quality. Moderate
complexity with zero duplication is arguably healthier than low complexity bought
by scattering logic across duplicated scaffolding. The metric is most informative
read next to duplication.

**Duplication.** Claude Code produced zero duplication across all 30 runs. Cursor
averaged 0.90%, Antigravity 4.26%, and **Replit Agent 9.56%**, by far the largest
in the table. Inspection identifies the source: Replit ships enterprise monorepo
scaffolding, meaning workspace configuration hierarchies, shared-utility
libraries and generated OpenAPI and ORM code, whatever the spec's domain, and
that scaffolding repeats template fragments across packages. The metric is doing
its job, measuring the agent's *architectural footprint* rather than the logic the
spec asked for. A buyer should expect roughly a tenth of the produced code to be
scaffolding redundancy before any feature work begins.

**Security density.** These figures exclude Bandit's `B101` assertion findings
inside test files, which the analyser first counted. `B101` exists because
assertions vanish under `python -O`, and that reasoning does not apply where the
assertion *is* the test. Counting them penalised the conditions that tested their
own output most thoroughly: claude_code read 42.05 instead of 9.65, and
cursor_agent 43.67 instead of 5.93. The correction is Erratum 001. It swaps the
order of those two conditions and reverses no inferential conclusion.

The exclusion exposed something the metric had been hiding. Whether a tool writes
tests at all varies enormously. `antigravity` produced a test file in all 30
runs, `cursor_agent` in 21, `claude_code` in 16 and never on the CLI
specification, and `replit_agent` in none. While assertions counted as findings,
the metric penalised thoroughness and rewarded its absence, exactly the inversion
a governance instrument must not make.

The corrected pattern still inverts the other metrics. The two feature-dense
tools score *highest*: Claude Code 9.65 and Cursor Agent 5.93 CWE-tagged findings
per kLOC, against Replit 0.00 and Antigravity 1.47. Replit's zero is not a
security result. Bandit scans only Python, and Replit's output is dominated by
TypeScript, so almost nothing it wrote was scanned. `security_density` is
therefore a *per-language* density, not a total vulnerability count, and a
companion metric of total CWE-tagged findings per run would be needed for a
whole-project claim (§5.2).

![Language composition of each condition's output, and its effect on security density](figures/fig_4_4_language_composition.png)

**Figure 4.4** The artefact made visible. Left, the share of produced lines by
language across all 30 runs per condition: Replit's output is 6% Python against
52% TypeScript and 42% configuration, while every other condition is
Python-first. Centre, the number of runs containing a test file. Right, security
density against Python share. Replit's 0.00 is not a security result: almost
nothing it wrote is scannable.

**Keystroke correction.** Structurally zero for every AI condition, because
agents do not press keys. The metric exists for the human comparison in §4.6. It
provides the empirical floor that makes the agentic zero read as a category
difference rather than an absence (§5.5).

## 4.4 Per-specification breakdown

Table 4.2 gives the hallucination count per (condition × spec) cell, N = 10 per
cell nominal. The distribution is *not uniform across specifications*, which is
the strongest justification for using three of them.

**Table 4.2** Per-specification hallucination breakdown: mean off-spec feature
count per (condition × specification) cell.

| Hallucinations by spec | agent_education | data_pipeline | internal_tool_cli |
|---|---:|---:|---:|
| claude_code | 0.00 | 0.00 | 0.00 |
| cursor_agent | 0.50 | 0.00 | 0.00 |
| replit_agent | 1.00 | 0.00 | 3.00 |
| antigravity | 1.00 | 0.00 | 0.00 |

![Off-spec features by tool and task domain](figures/fig_4_5_hallucination_heatmap.png)

**Figure 4.5** Table 4.2 as a heatmap. The concentration of off-spec output in
`replit_agent` on the CLI specification, three off-spec subcommands per run
against at most one anywhere else, is the study's most consequential result. The
unevenness of the surrounding cells is the clearest statement that tool behaviour
is task-conditional rather than uniform.

Three patterns are visible. Cursor's hallucinations sit only in the web-app spec.
Antigravity's sit in that same spec, at a full off-spec route per run. Replit's
are heaviest on the CLI spec, three per run against one on the web app and none
on the pipeline, which is what the architectural-prior account predicts: its
pipeline-shaped defaults fit worst when the brief asks for a command-line tool.

No tool's hallucination behaviour is constant across the three domains. A
single-specification study would therefore have produced a different and
misleading ranking depending on which spec it picked. A CLI-only study would have
indicted Replit and left Antigravity looking clean. A web-app-only study would
have found Replit and Antigravity equally culpable at 1.00 each, and missed
Replit's worst failure entirely. The non-uniformity is descriptive, since the
design cannot test the interaction (§4.5.3), and it is why the external-validity
claim is task-conditional throughout.

## 4.5 Statistical tests

### 4.5.1 The unit-of-analysis problem

The inferential analysis has to face a constraint that a naive reading of the
CSV would hide. Under Deviation 001 the two IDE-bound conditions were captured
**once** per (condition × specification) cell, and that single capture was
replayed ten times for CSV-shape consistency. The data confirm it: the maximum
number of distinct values in any (spec × metric) cell is **ten** for
`claude_code` and `cursor_agent`, and **one** for `replit_agent` and
`antigravity`.

So the two replay conditions contribute **three effective observations each**,
not thirty. Treating their ten rows as independent is *pseudoreplication*, and it
inflates every statistic computed over the nominal N = 30. The analysis is
reported at three levels of conservatism, and the conclusions drawn only from the
level the design supports.

### 4.5.2 Three analyses

**Level 1, nominal analysis, reported for transparency and not relied upon.**
Kruskal–Wallis over all four conditions at nominal N = 30 returns significance
on all four testable metrics. Duplication H = 62.41, p = 1.8 × 10⁻¹³. Security H
= 26.07, p = 9.2 × 10⁻⁶. Hallucinations H = 40.14, p = 9.9 × 10⁻⁹. Complexity H
= 12.03, p = 7.3 × 10⁻³. **These values are inflated by pseudoreplication and are
not the study's inferential claim.** They are reported so a reader reproducing the
CSV gets the same arithmetic and can see why it must be discounted. Condition-by-specification interaction *F*-statistics from an earlier
draft are **withdrawn**: with one effective observation per cell in two
conditions, the interaction term has no residual degrees of freedom and the
statistic is undefined on this design.

![Nominal versus effective sample size per condition](figures/fig_4_6_effective_n.png)

**Figure 4.6** Why Level 1 must be discounted. Each condition contributes 30 rows
to the report, but only the two CLI-driven conditions contribute 30 independently
captured sessions. The IDE-bound conditions contribute three apiece, one per
specification, replayed ten times. The omnibus tests above treat the grey bars as
the sample size; the analysis that follows treats the teal ones.

**Level 2, the inferential core, live conditions only.** Only `claude_code` and
`cursor_agent` were captured live with genuine per-replication variance, with
within-cell SD up to 2.32 for duplication and 38.79 for security density, so only
their comparison supports inference at full replication.

**Table 4.3** Live-condition comparison, `claude_code` versus `cursor_agent`
(N = 30 per condition; two-sided Mann–Whitney *U*; rank-biserial *r*).

| Metric | *U* | *p* | rank-biserial *r* | Claude mean | Cursor mean |
|---|---:|---:|---:|---:|---:|
| Duplication (%) | 330.0 | 0.0028 | 0.267 | 0.00 | 0.90 |
| Complexity (cc) | 641.5 | 0.0047 | −0.426 | 3.35 | 2.72 |
| Hallucinations (count) | 390.0 | 0.0419 | 0.133 | 0.00 | 0.17 |
| Security density (per kLOC) | 508.0 | 0.3668 | −0.129 | 9.65 | 5.93 |

At the pre-registered threshold of α = 0.01 (§3.6), **duplication and complexity
differ significantly**; hallucinations and security density do not. A further
correction for the four metrics tested here (0.0025) is not part of the
registered plan, and neither result would survive it.

The two significant results are not equal in kind. On *complexity*, both
conditions vary across all three specifications, so the comparison rests on
genuine run-to-run replication at both ends. On *duplication*, `claude_code`
returns 0.00 in every replication of every specification, so the test compares a
fixed value against a distribution rather than two distributions. The gap is real
and visible in Table 4.1, but it is not evidence of the same kind.

One claim rests on unambiguous independent replication in **both** arms:
complexity. On identical tasks, Claude Code produces measurably more control-
flow-dense code than Cursor Agent (Mann–Whitney *U* = 641.5, *p* = 0.0047, *N* =
30 per condition, rank-biserial *r* = −0.43). The duplication result
is reported alongside as a strong descriptive difference with partial
inferential support.

**Level 3, pseudoreplication-corrected omnibus, all four conditions.** Collapse every condition to one value per specification, the honest unit of
analysis, and N = 3 per condition. No metric then reaches significance.
Duplication H = 6.34, p = 0.096. Security H = 5.30, p = 0.151. Hallucinations H
= 3.45, p = 0.328. Complexity H = 1.17, p = 0.760. This is a **power result, not a null
result**. With three cells per condition only an overwhelming effect could reach
α = 0.01. It is reported to establish that the four-condition comparison here is
descriptive, not inferential.

### 4.5.3 What the design does and does not license

The differences in Table 4.1 are large, consistent, and explained mechanistically
by direct inspection of the captured code: duplication spans 0.00% to 9.56% and
hallucinations 0.00 to 1.33 per run. For the two IDE-bound vendors they rest on
one captured session per task, so they are presented as **descriptive case
evidence**. The task-dependence claim (RQ3) is reframed the same way: Table 4.2
shows that no vendor's hallucination behaviour is constant across domains, which
is a descriptive demonstration, reported without an inferential interaction test.
Closing the gap requires live multi-session re-capture of the two IDE-bound
vendors (§6.4).

## 4.6 Human-control baseline

The human baseline (N = 1 per spec, all six features implemented and verified)
scored zero hallucinations, zero duplication and zero security density on all
three specifications. That is a minimal, exactly-on-spec implementation without
the over-delivery driving the AI conditions' figures.

**Table 4.4** Human-control baseline versus AI-condition means, per
specification. Human values are single sessions (N = 1, Deviation 003); AI values
are the mean of the four agentic conditions. Reported descriptively; no
inferential comparison is made.

| Metric | Web app (human / AI) | Pipeline (human / AI) | CLI (human / AI) |
|---|---:|---:|---:|
| Security density (per kLOC) | 0.00 / 10.48 | 0.00 / 1.09 | 0.00 / 1.23 |
| Complexity (cc) | 1.71 / 1.56 | 5.00 / 3.20 | 0.00 / 3.54 |
| Duplication (%) | 0.00 / 3.59 | 0.00 / 5.87 | 0.00 / 1.57 |
| Hallucinations (count) | 0.00 / 0.62 | 0.00 / 0.00 | 0.00 / 0.75 |
| Keystroke correction (per 1k) | 829.27 / 0.00 | 51.80 / 0.00 | 122.27 / 0.00 |

![Human baseline against the agentic mean, per specification](figures/fig_4_7_human_vs_ai.png)

**Figure 4.7** Table 4.4 at a glance. The human baseline is at or near zero on
every artefact metric in every domain, the signature of a spec-minimal
implementation rather than superior craft. The exception is complexity, where the
human sits above the agentic mean on the web app and the pipeline, and at exactly
zero on the CLI. That zero is the decomposition confound of §5.5, not a simpler
program.

Mean complexity was 1.71 on the web app and 5.00 on the pipeline. For the CLI it
was 0.00, a structural artefact: the human wrote top-level script code with no
function definitions, and the analyser measures per-function complexity, while
the AI conditions wrapped the same logic in functions (3.1 to 4.1).

Keystroke correction is the one metric where the human is the point of
comparison. On the representative complete session (`data_pipeline`, 6,619
events) it was 51.8 per 1,000, so the researcher backspaced about 5% of the time.
The `agent_education_system` figure of 829 per 1,000 is a partial-capture outlier
from the documented data-loss event and is not a representative authoring rate.

## 4.7 Inter-rater reliability

The hallucination heuristic was validated against human judgement, as
pre-registered. Two raters independently labelled the 30-run sample, deduplicated
to 19 distinct codebases, because 11 of the 30 rows are byte-identical replays
under Deviation 001 and labelling identical code twice would inflate agreement by
construction.

Rater 1 was Ikenna Onyedebelu (MSc Data Science and AI) and Rater 2 Matthew Brian
Tahir, both named here with their consent. Neither contributed to the study's design,
its instrument or its data. Neither saw `data/reports/main_001.csv`, and neither
was told which condition produced which item. One capture contains no files and
was recorded `SKIP` by both, giving N = 18 scoreable items. Labels are compared
on the binary contrast: any off-specification feature, against none.

**Table 4.5** Cohen's κ against the instrument as it stood when the raters
worked. Threshold κ ≥ 0.6 (Landis and Koch, 1977).

| Comparison | κ | Interpretation | Raw agreement |
|---|---:|---|---:|
| Rater 1 × Rater 2 | 0.870 | almost perfect | 94.4% |
| Rater 1 × instrument | 0.852 | almost perfect | 94.4% |
| Rater 2 × instrument | 0.727 | substantial | 88.9% |

All three clear the threshold, so the metric's detection of scope drift is
admissible, on the two terms below.

![Per-item comparison of both raters and the instrument](figures/fig_4_8_kappa_agreement.png)

**Figure 4.8** Every label in the study, item by item. Shaded cells carry at
least one off-specification feature; item_04's capture is empty and was recorded
`SKIP` by both raters. The two boxed columns are the only disagreements. At
item_08 both raters saw a route the instrument could not (Erratum 002). At
item_16 the raters differ from each other over whether shipped vendor scaffolding
counts as scope drift.

**The validated claim is detection, not magnitude.** κ is computed on the binary
contrast. Two items agree in binary terms while differing in count: one where the
instrument recorded two off-spec features against the raters' one, and one where
the raters differed from each other by four. The instrument is validated as an
answer to *whether* scope drift occurred, not *how much*. No claim in this
chapter rests on a hallucination magnitude alone.

**The labelling exposed a defect, recorded as Erratum 002.** Both raters counted
an off-specification route in the `replit_agent × agent_education_system` capture
that the instrument scored zero for. Its route detector matched only the Python
decorator form, and that capture is an Express service written in TypeScript. The
detector was blind to the whole class. Because the labelling tool extracted its
candidates independently of the instrument, the blind spot surfaced instead of
being reproduced. Had the raters seen only what the instrument could see, the
item would have agreed perfectly and the defect would have survived into the
thesis. The affected cell is corrected from 0.00 to 1.00 throughout, and
hallucination counts should be read as a lower bound on codebases that are not
Python-first.

Repairing the defect raises κ(Rater 1, instrument) to 1.000 and κ(Rater 2,
instrument) to 0.870. **Those post-repair values are not reported as validation
and support no claim.** The defect was found by the raters' disagreement and the
repair then measured against the same labels, which is circular. Establishing the
repaired instrument's validity needs a fresh sample and raters who have not seen
these items. The figures of record are those in Table 4.5.

Neither rater designed the study or built the instrument, which removes the
concern that a rater might label towards the hypotheses. The single human-human
disagreement, at item_16, is evidence that the two sheets were produced without
conferring.

## 4.8 Application outside the controlled study

The design so far tests the instrument on captures built to be scored. Three
further audits were run on codebases outside the study. They are descriptive, not
pre-registered, and carry no inferential weight. They establish only that the
metrics return meaningful readings on ordinary code.

**Table 4.6** Field audits. Each project was scored against its own
specification. Scope drift is the hallucination metric applied outside the
experiment.

| Project | Files | Lines | Python | Security | Complexity | Duplication | Scope drift |
|---|---:|---:|---:|---:|---:|---:|---:|
| kya-rails | 43 | 4,620 | 15 | 7.49 | 4.13 | 1.79% | 0 |
| GovSignal | 30 | 1,923 | 17 | 2.26 | 4.79 | 0.89% | 4 |
| This instrument | 141 | 13,136 | 86 | 3.14 | 3.58 | 4.01% | 12 |

![The same project before and after a specification was supplied](figures/fig_4_9_scope_needs_spec.png)

**Figure 4.9** Why the metric needs a brief. Two captures of
`lcx-enterprise-core-v2` four minutes apart, during which twenty-two lines were
added. In the first the tool has no specification and scope drift reports `n/a`,
because there is nothing to measure against. In the second a specification has
been supplied and the same codebase reports six off-specification features. The
other four metrics are unchanged, since they do not depend on knowing what was
asked for. This is the study's argument in one image: fidelity is not a property
of code that can be read off the code alone.

Two points follow. Scope drift discriminates: `kya-rails` returns 0, the reading
the metric is designed to produce when output matches its brief, while
`GovSignal` returns 4. A metric returning the same value on every real project
would measure nothing. And `GovSignal` was audited by a third party on their own
machine, so these readings occur in other hands.

![The published package installed by a third party](figures/fig_4_10_installation.jpg)

**Figure 4.10** How that audit began. The published package is installed from
PyPI on another user's Windows machine, resolving its dependencies and reporting
success, in the project directory it then audited. Adoption of a research
instrument is ordinarily asserted; here it is a terminal transcript.

*4.8.1 The instrument audits itself.* The third row is the most uncomfortable and
the most useful. Its declared scope is transcribed from the pre-registration and the standing
brief of 30 May 2026, and reproduced in `specs/auditor_instrument.yaml`. Scored
against it, the instrument carried twelve capabilities nobody specified: four
command-line verbs (`scan`, `watch`, `live`, `fix`), and eight HTTP endpoints
belonging to a local web interface the declared design did not contain. The declaration described two commands and no web surface. The `fix`
verb has since been removed from the published package (release 0.5.0). Git dates
every addition to August 2026, months after the protocol was fixed, none of them
required by the experiment.

This is the phenomenon the study measures, occurring in the author's own work,
and it sharpens rather than undermines §5.3. The drift here is *deliberate and
dated*: each capability was chosen, committed with a message explaining it, and
is visible to anyone reading the history. Replit's substitution of a pipeline for
a command-line tool (§4.3.1) was none of those things. The governance distinction
is therefore not between projects that stay in scope, since almost none do, but
between scope expansion a reviewer can see and substitution a reviewer cannot.

One caveat on provenance. An earlier self-audit, retained in the evidence set,
reported scope drift of 19. It scored the instrument against the study's
demonstration specification for a student-course application, under which almost
everything the instrument contains is off-specification by construction. That is
an artefact of the wrong brief, not a finding; the figure of record is 12. The
evidence set shows the 19 reading (Figure F.3), not the 12. The same caution
excludes the scope drift counts in Figures F.10 and F.11, whose brief was not
retained.

## 4.9 Summary of findings

1. **Hallucination is the most consequential governance metric.** The agentic conditions span 0.00 to 1.33 off-spec features per run. That range
matters in any deployment evaluation, and functional benchmarks do not surface
it. Between the two live tools the difference is not significant (§4.5.2).

2. **Replit Agent's architectural prior dominates the specification.** Given a
   CLI specification it ships a data pipeline; given a web-app specification, an
   enterprise TypeScript monorepo. The hallucination count, the duplication of
   9.56% and the security-density 0.00, because almost none of it is Python, are
   three readings of one behaviour. Its stability across independent sessions
   awaits the live re-capture (§6.4).

3. **Claude Code produces the most disciplined output**: zero hallucinations and
   zero duplication across all 30 runs, at the cost of the highest structural
   density, mean complexity 3.35. Of its two gaps from Cursor, complexity is the
   study's single result supported by genuine replication in both arms (§4.5.2).

4. **Cursor Agent is the median performer**, neither best nor worst on any
   metric, its modest hallucinations confined to the web-app spec.

5. **Antigravity's hallucinations fall entirely in the web-app spec**, 1.00 per
   run there and none elsewhere, and it records the lowest security density of
   any condition with substantive Python output.

6. **Tool behaviour is not constant across task domains.** Every vendor's hallucination profile changes with the specification (Table 4.2).
So the strongest claim is not "agent X is better than agent Y" but "agent X
behaved better *for this task type*". This is established descriptively
(§4.5.3).

---
