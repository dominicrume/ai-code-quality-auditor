> **Generated file — do not edit.**
> Extracted from `DISSERTATION_FULL.md` on 2026-09-14 by
> `scripts/split_chapters.py`. Edit the master and re-run; any change made
> here is overwritten. The master is the submission artefact.

---

# Chapter 3: Methodology

## 3.1 Research design

The study adopts a quantitative, between-conditions experimental design with
replication, chosen because the research questions are comparative and causal in
form (do tools differ, by how much, and does the difference depend on task?) and
because the dependent variables are machine-measurable, which makes a
quantitative design both feasible and preferable to a qualitative or
mixed-methods alternative. The independent variable is the *workflow condition*
(the tool, or the human baseline); the dependent variables are the five quality
and process metrics; and the *specification* is treated as a second, crossed
factor so that condition-by-task interactions can be estimated directly (RQ3).
Holding the specification fixed across conditions is the design's central control:
because every condition implements the identical brief, differences in the
measured artefacts are attributable to the workflow rather than to the task.
Figure 3.1 sets out the resulting pipeline end to end.

![Instrument architecture](figures/fig_3_1_architecture.png)

**Figure 3.1** The instrument's architecture. One fixed, versioned specification
is issued to every condition; one adapter per vendor captures the result into a
single capture contract; one analyser per metric scores that contract without
sight of which condition produced it; and a provenance-stamped report is
emitted. The file-level isolation (one adapter per vendor, one analyser per
metric) is what allows a condition or a metric to be added without touching any
other.

The use of three specifications spanning distinct domains (a web application, an
ETL pipeline, and a command-line tool) is a deliberate external-validity device:
a single-specification study could not distinguish a general tool property from
a task-specific one, and, as the results show (§4.4), that distinction turns out
to be essential.

Each condition produces *K* attempts at each of *S* specifications, yielding *N
= K × S* observations per condition for every metric. The five **conditions**
(independent variable) are the four commercial agentic tools (`claude_code`
(Anthropic Claude Code CLI), `cursor_agent` (Cursor Agent CLI), `replit_agent`
(Replit Agent, browser IDE, replay-captured), `antigravity` (Google Antigravity,
desktop IDE, Gemini-class model)) and a `human_control` hand-coded baseline. The
five **metrics** (dependent variables) are security-vulnerability density
(CWE-tagged Bandit findings per kLOC), mean cyclomatic complexity (McCabe, via
`radon`), code-duplication percentage (six-line shingles), hallucination count
(off-specification features, via a `manifest_deriver`), and keystroke-correction
frequency (backspace + delete per 1,000 keystrokes, via `pynput`; structurally
zero for agentic conditions). The three **specifications** (treatment stimuli,
identical across conditions) span distinct domains: `agent_education_system`
(CRUD + authentication web app), `data_pipeline` (ETL + scheduler), and
`internal_tool_cli` (a CLI with subcommands), each with six features and three
governance rules.

## 3.2 The capture contract

The methodological core of the instrument is the **capture contract**: every
condition, however different its native output, must surface its work as two
artefacts of a fixed shape, a `codebase` (`{files: {path: content}, manifest:
[feature_ids]}`) and an `interaction_log` (a list of typed events, where each
type is one of `keystroke`, `backspace`, `delete`, or `agent_action`). For
`human_control`, a `pynput` listener captures and classifies every key press at
the OS level; for the agentic conditions, every vendor event (tool-call, file
edit) is normalised to `agent_action` with vendor-native detail preserved in
sibling keys for forensics but hidden from the analysers. The contract is the
boundary that makes a human and an agent comparable, and it is enforced at load
time: malformed events abort the run rather than silently degrading a metric.

The normalisation this requires is shown in Figure 3.2.

![The capture contract](figures/fig_3_2_capture_contract.png)

**Figure 3.2** The capture contract. A human pressing keys and an agent
streaming tool-calls produce structurally unrelated traces; both are normalised
into the same two artefacts, a `codebase` mapping and a typed `interaction_log`,
before any analyser sees them. Vendor-native detail is preserved in sibling
fields for forensics, but comparability is enforced at this boundary rather than
inside each metric.

The design significance of the capture contract is that it relocates all
vendor-specific reasoning to a thin *adapter* layer, one file per vendor, whose
sole responsibility is to translate native output into the contract shape. The
analyser layer never imports an adapter and never branches on condition; it sees
only the contract. This separation is what makes the comparison defensible: a
critic cannot argue that a metric was implemented to favour one vendor, because
the metric code has no way of knowing which vendor produced the artefact it is
scoring. It also makes the instrument extensible (adding a fifth or sixth tool
requires writing one adapter, not modifying any metric) which is the property
that allows third parties to reproduce and extend the study (§3.7, §6.4).

## 3.3 Capture procedure

The capture procedure differs by vendor only in how the native output is
obtained; all four agentic conditions converge on the same contract before any
analysis. The two CLI-exposing tools (`claude_code`, `cursor_agent`) are driven
non-interactively via `subprocess` in a clean, per-run working directory,
capturing their streamed JSON event output line by line and persisting the raw
stream alongside the contract-shaped events for forensic re-analysis. Claude
Code is invoked in its non-interactive, permission-skipping mode (required
because no human is present to confirm individual tool calls in an unattended
run) and sandboxed to a per-run session directory; Cursor Agent is invoked under its free tier's automatic model selection, so the
study does not fix which model produced its output (§5.7). The two IDE-bound tools
(`replit_agent`, `antigravity`) expose no scriptable interface, Replit Agent
runs inside a browser IDE and Antigravity inside a desktop IDE, and are
therefore captured by a manual session in the vendor's interface, after which
the produced files and event log are handed to a replay adapter that loads them
through the *same* contract used by the CLI-driven conditions. The replay
adapters share their loader and persistence code with their live counterparts;
the only difference is the source of the input bytes, so the analyser cannot
distinguish a replayed capture from a live one. This equivalence is what
licenses treating the conditions together, subject to the documented
within-cell-variance consequence of replay (Deviation 001, §3.6). The `human_control` condition is detailed in §3.3.1 below.

Each run records the model it used: `claude-sonnet-4-6` for Claude Code,
automatic selection for Cursor Agent, Gemini 3.5 Flash (Medium) for Antigravity
and Replit Agent's unversioned default. The live captures were committed on
31 May 2026 and the full four-tool matrix on 1 June 2026.

### 3.3.1 Human-control condition (as executed)

The pre-registration specified 30 hand-coded sessions (three specs × ten reps)
of 60 minutes each. The executed collection deviated from this plan
(**Deviation 003**): a single completed session per specification was captured
(N = 1 per spec), each run to feature-completion rather than time-capped, with
all in-IDE AI assistance disabled and verified. All six features of each
specification were implemented and verified to execute before scoring. The
human baseline is therefore framed throughout as a **single-rep reference
point** against the AI distribution, not a variance-bearing condition, and is
excluded from the inferential tests. Because the recorder overwrites its log per
invocation, multi-attempt sessions were preserved by archiving each capture
segment and concatenating them at scoring time; the human interaction log for a
rep is thus the union of all capture segments for that spec (total typing effort
including debugging). One unrecoverable data-loss event is recorded and carried
as a limitation: for `agent_education_system`, an early ~2,133-event coding
segment was overwritten before the segment-archiving procedure existed, so that
rep's correction frequency is computed from a 75-event surviving fixing segment
and reported as a partial-capture outlier.

## 3.4 Analyser pipeline

Each metric is a single Python function with a uniform signature:
`analyze(codebase, interaction_log, spec) -> MetricScore`. This does two things
at once. It *formalises the capture contract* (an analyser sees exactly what the
contract defines, no more), and it *blinds the analyser by construction*: no
analyser receives a condition label, so no metric can be computed with
vendor-specific knowledge, and condition identity is attached only by the
orchestrator after scoring. The pipeline is blinded by interface design rather
than by discipline, a deliberate guard against the vendor-favouring bias that
hand-tuned evaluation harnesses are prone to.

![Decision bands for each metric](figures/fig_3_3_metric_bands.png)

**Figure 3.3** Decision bands applied to each metric when results are presented
to a non-specialist audience. The thresholds are interpretation *policy*, held
in one module (`auditor/core/calibration.py`) so that the command line, the
dashboard and the reporting client cannot report different verdicts for the same
number. They bound the reading of a value; they do not affect its measurement.

*Security density (§3.4.1).* The analyser materialises the captured codebase to
a temporary directory and invokes Bandit, counting only findings carrying a
non-null CWE identifier (preserving the OWASP/MITRE framing of §2.2–2.3) and
dividing by line count, scaled to one thousand lines. Assertion findings
(`B101`) inside test files are excluded, see §4.3 and Erratum 001. An earlier
design queried the SonarCloud REST API; it was abandoned during the pilot
(docs/PILOT_RESULTS.md §4.1) because per-project scoping shared one numerator
across conditions while the denominator varied, producing artefactually large
per-kLOC figures for small codebases.

*Cyclomatic complexity (§3.4.2).* `radon`'s control-flow visitor enumerates
every function's McCabe number and the analyser reports the arithmetic mean.
Files outside the source-suffix whitelist and inside excluded directories
(virtual environments, caches, vendored packages) are removed by the codebase
loader first, so the metric reflects produced code rather than transitive
dependencies. As §5.5 discusses, the per-function basis is the source of the
human baseline's CLI zero and a known cross-style confound.

*Duplication (§3.4.3).* The analyser hashes every six-consecutive-line shingle
across all source files (six being the conventional near-duplication window),
counts the lines participating in any shingle of cardinality two or more, and
divides by total source lines. It captures structural redundancy, including the
repeated-template scaffolding that drives the Replit result, rather than merely
verbatim copy-paste.

*Hallucination (§3.4.4).* The analyser defers to a `manifest_deriver` that scans
for evidence of each declared spec feature and for web routes and CLI
subcommands mapping to *no* declared feature; the count of unmapped routes and
commands is the score. Route detection covers both the Python decorator form
(FastAPI/Flask) and the JavaScript/TypeScript call form (Express), the latter
added after the κ validation found the detector blind to it (Erratum 002).
Subcommand detection (argparse/Click) was added after the main study revealed
the Replit behaviour, logged as analytical note 001. The deriver is a
token-matching heuristic; its validation against human judgement is reported in
§4.7.

*Keystroke correction (§3.4.5).* The analyser counts `backspace` and `delete`
events, divides by total `keystroke` count, and scales to one thousand. It is
structurally zero for the four agentic conditions and is the only metric for
which the human baseline produces a non-zero value by construction (§4.6, §5.5).

Scores reach a reader through a reporting layer, shown in Figure 3.4.

![The hosted report view](figures/fig_3_4_report_dashboard.jpg)

**Figure 3.4** The reporting surface. Every scored run is published to a hosted
report rendering the full condition-by-metric grid, normalised per row so colour
encodes rank within a metric rather than magnitude across metrics, with a
per-metric drill-down beneath. The instrument is therefore usable by a reader
who will not run it. This capture predates both errata, so its underlying values
are those Chapter 4 corrects.

## 3.5 Pre-registration

The design (sample size, model versions, metrics, statistical tests, and
multiple-comparison policy) was committed to the repository
(`docs/EXPERIMENT_PROTOCOL.md`) before any main-study data was captured; the
first commit of that file is the boundary between pilot exploration and the
dissertation result. Subsequent changes are appended to
`docs/PROTOCOL_DEVIATIONS.md` with date, rationale and analytical consequence.

## 3.6 Statistical analysis plan

The analysis plan is pre-registered and identical for every metric, which
removes the metric-by-metric analytic discretion that would otherwise threaten
the validity of the reported p-values. For each metric, normality is checked per
`(condition, spec)` cell with the Shapiro–Wilk test (Shapiro and Wilk, 1965) and
variance equality across conditions with Levene's test (Levene, 1960). If both
preconditions hold, a one-way ANOVA is run across the conditions; if either
fails, the non-parametric Kruskal–Wallis test (Kruskal and Wallis, 1952) is used
instead. The non-parametric fallback is not a marginal case here but the norm,
because the deterministic-replay conditions contribute zero within-cell variance
(Deviation 001), which violates the variance-equality precondition for every
metric. Significance is assessed at a Bonferroni-corrected threshold of α = 0.01
(0.05 across five metrics), a deliberately conservative choice that controls the
family-wise error rate across the metric family. Significant omnibus tests are
followed by the appropriate post-hoc: Tukey's HSD (Tukey, 1949) for an ANOVA omnibus, and
Dunn's test (Dunn, 1964) with Bonferroni adjustment for a Kruskal–Wallis
omnibus; because every omnibus was non-parametric, Dunn's test is the post-hoc
used throughout, and an earlier implementation that applied Tukey's HSD to a
Kruskal–Wallis omnibus was corrected to match the pre-registration. Effect sizes were registered as η² for the omnibus and rank-biserial
correlations for pairwise comparisons; because no omnibus is relied upon
(§4.5), only the pairwise sizes are reported, interpreted against Cohen's (1988) conventional benchmarks
for small, medium and large effects, and 95% confidence intervals on each
condition mean are obtained by bootstrap resampling with 10,000 replicates
(Efron, 1979).

The pre-registration additionally specified a two-way ANOVA with a
condition-by-specification interaction term to test whether condition effects are
stable across task domains (RQ3). This test proved **inadmissible on the executed
design** and is not reported: because the replay conditions contribute one
effective observation per cell (Deviation 001), the interaction term has no
residual degrees of freedom, and an interaction *F* computed over the replicated
rows would measure the replay mechanism rather than the tools. RQ3 is therefore
answered descriptively in §4.5.3. More generally, and departing from the
pre-registered plan in the direction of conservatism, the analysis reported in
§4.5 is stratified by the effective sample size each condition contributes:
formal inference is confined to the two conditions captured live with genuine
replication, and the four-condition comparison is reported descriptively with the
pseudoreplication-corrected omnibus given alongside. The rationale is stated
there in full; the principle is that the unit of analysis must be the
independently captured session, not the CSV row.

Three deviations and one analytical
note are logged with their analytical consequences: the replay-mode zero-variance
constraint (001), the deferred web-IDE cells (002), the human-control execution
change (003), and the Replit architectural-prior observation (analytical note
001); the security-metric instrument change from SonarCloud to local Bandit is
documented in the pilot report (docs/PILOT_RESULTS.md §4.1).

## 3.7 Reproducibility infrastructure

The instrument ships as a Python package and a GitHub Action; the headline CSV
(`data/reports/main_001.csv`) is accompanied by a provenance file, and a live
read-only dashboard renders the same CSV with a banner that flips from "pilot"
to "dissertation result" only when N ≥ 5 per condition is reached, a structural
guard against misrepresenting pilot data.

## 3.8 Ethical considerations

The study involved no human participants and collected no human-subject data,
and the approved project proposal records that ethics approval was not
required. Every specification and all application content are synthetic, and
no personal, customer or organisational data was given to any tool. The
human-control sessions were carried out by the researcher, and the recorder
logs only the type of each key event, never the characters typed. The two
raters in §4.7 acted as independent assessors of the instrument's output rather
than as research subjects; both took part voluntarily and gave signed consent
for their labels to be used and their names to appear.

---
