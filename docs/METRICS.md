# Metrics — definitions and formulas

Each metric lives in its own analyzer file. This document is the contract.

## 1. Security vulnerability density
- **Languages (v2, from 0.5.0):** Python via Bandit, plus JavaScript and
  TypeScript via a curated CWE-tagged ruleset (`auditor/analyzers/js_security.py`).
  Every reading reports `coverage`, the share of source it could evaluate, so a
  density over part of a project is not mistaken for a verdict on all of it.
  Version 1 (Python only) is retained and reproduces the published study
  exactly: `analyze(..., version=1)`.
- **Definition:** count of CWE-tagged findings normalised per 1000
  lines of scanned source. This is a **per-language density** (v1 scans Python
  only), and it is **severity-unweighted** — every finding contributes 1
  regardless of severity, because severity weighting would conflate the
  independent variable with the dependent variable. It is not a
  whole-project security score; a total-CWE companion metric is the
  documented extension (dissertation §6.4).
- **Tool:** local `bandit -r -f json` over the captured codebase, wired in
  `analyzers/security_analyzer.py`. Only findings with a non-null
  `issue_cwe.id` are counted (preserving the OWASP/CWE framing).
- **History:** the original design queried SonarQube/SonarCloud
  (`SONARQUBE_URL`/`SONARQUBE_TOKEN` in `.env`). It was abandoned during
  the pilot because per-project scoping shared one numerator across
  conditions while denominators varied, producing artefactually large
  per-kLOC figures — see PILOT_RESULTS.md §4.1. Local Bandit scoping
  restores per-condition isolation, determinism, and version-pinning.
  SonarQube remains in CI for the host repo's own quality signal only.
- **Exclusion — assertions in test files.** `B101` fires on every `assert`,
  because assertions are stripped when Python runs under `-O` and a check
  written as an assertion would silently disappear from a shipped build. That
  reasoning does not apply to a test file, where the assertion *is* the test.
  Counting them makes the metric reward untested code: on this repository
  alone, B101 in `tests/` produced 291 findings and raised the density from
  3.27 to 47.05 per kLOC. Assertions are therefore not counted in files named
  `test_*.py`, `*_test.py`, `conftest.py`, or living under a `tests/`
  directory. Assertions in production code still count.
- **Output:** `MetricScore(name="security_density", value=float, unit="per_kloc")`.

## 2. Cyclomatic complexity
- **Definition:** McCabe cyclomatic complexity per function; aggregated as
  the unweighted **mean** across all functions in the codebase. Reports
  `complexity_mean` as the headline metric (used by the experiment CSV);
  the per-function detail is preserved alongside in the raw artefacts.
- **Tool:** `radon.complexity.cc_visit` for Python, AST-based; JavaScript and
  TypeScript are scored from version 2 by `auditor/analyzers/js_complexity.py`,
  a lexical decision-point counter that strips strings and comments first and
  tracks brace depth so nested functions are scored separately. Version 1 scores
  Python (`.py`) only, as the MSc study did; other languages are
  skipped and logged. This is documented as a scope limitation.
- **Aggregation:** if a codebase has zero scorable functions the metric is
  reported as 0.0 with `unit="cc"`. A file that fails to parse is logged
  and excluded — never silently counted as zero.
- **Output:** `MetricScore(name="complexity_mean", value=float, unit="cc")`.

## 3. Code duplication
- **Definition:** percentage of source lines that appear inside at least one
  duplicated block. A "block" is a window of **k=6 consecutive non-blank,
  whitespace-normalised lines** that appears identically in two or more
  locations across the codebase.
- **Method:** token-free, language-agnostic shingle detection. Each file is
  reduced to a list of non-blank stripped lines; every k-line shingle is
  hashed; shingles seen ≥2 times mark all their constituent lines as
  duplicated. The metric is `100 * duplicated_lines / total_lines`.
- **Rationale:** the original SonarQube duplication metric uses a similar
  k-line shingle approach; reimplementing in-tree keeps duplication
  measurable for non-Java codebases without a SonarQube round-trip, and
  removes one external dependency from the metric.
- **Which files count (version 2, default from 0.6.0):** code only, the
  suffixes in `duplication_analyzer.CODE_ONLY`. The loader also ingests
  Markdown, YAML and TOML for other purposes, and because this metric needs
  no parser it had been measuring all of them. On this instrument's own
  repository that was 41,116 lines of Markdown against 12,431 of Python, so
  roughly three-quarters of the reported figure was a statement about prose.
  Repeated prose in a changelog is not duplicated code. Version 1 counts
  every ingested file and is retained so the published figures remain
  reproducible: `analyze(..., version=1)` returns what
  `data/reports/main_001.csv` records.
- **Output:** `MetricScore(name="duplication_pct", value=float, unit="%")`.

## 4. Hallucination frequency
- **Definition:** count of features present in the codebase manifest but
  **NOT** declared in the spec — i.e. things the agent shipped that nobody
  asked for. Spec-declared features that were *not* implemented are a
  different metric (completeness) and are out of scope here.
- **Method:** parse the spec features (`spec["features"][*]["id"]`), parse
  the codebase manifest (`codebase["manifest"]`), compute set-difference
  `manifest \ spec`. Each adapter is responsible for producing an accurate
  manifest (see docs/METHODOLOGY.md capture contract). When an adapter emits
  no manifest (the agentic conditions), the analyzer falls back to an
  auto-derived manifest from `analyzers/manifest_deriver.py`, which scans the
  produced code for token evidence of each spec feature plus off-spec web
  routes and CLI subcommands (the CLI-subcommand detector was added in
  response to the main-study Replit observation and is logged as analytical
  note 001 in PROTOCOL_DEVIATIONS.md). The heuristic is exploratory pending
  blind hand-label validation (Cohen's κ, dissertation §4.7); headline
  findings are additionally confirmed by direct code inspection.
- **Evidence rule (version 2, default from 0.6.0):** a feature is credited
  only where the codebase declares something -- a registered subcommand, an
  HTTP route, a function, a class or an export -- indexed with its file and
  line by `analyzers/definitions.py`. The match is on the feature's *head*
  token, the first dotted segment that is not a scaffolding word, so
  `remove.item` is not satisfied by `def add_item` and no feature is satisfied
  by a bare `def cli()`.
  Version 1 credited a feature when the terminal token appeared anywhere in
  every file concatenated together, which a word in a comment satisfied; it is
  retained for reproducibility and documented in
  `docs/ERRATUM_003_token_evidence.md`.
- **The other half of the question (from 0.6.0):** `analyzers/fidelity.py`
  reports a verdict per specified feature -- `delivered`, `not_found`, or
  `unreachable` (declared, but with nothing exposing it) -- each citing a file
  and line or stating plainly that it has none. `completeness` is the share
  delivered. This is reported as a table beside the five metrics and is
  **not** a sixth metric: it is not in the experiment CSV and does not enter
  Table 4.1.
- **Known blind spot, and the diagnostic that covers it:** the count asks
  what *extra* was shipped, so it cannot see a substitution. An agent given
  a CLI specification that ships an ETL package with no subcommands adds
  nothing and scores 0.00, the same as an agent that built the CLI correctly
  (run_001; dissertation §6.4). `analyzers/shape_detector.py` separates those
  cases by comparing the shape the spec asks for with the shape actually
  built. From 0.6.0 its verdict is reported beside the metric, as a sentence,
  whenever the detector is both in disagreement and confident.
  It is deliberately **not a sixth metric and not folded into this value**:
  doing either would change figures already published and is a decision for
  an erratum, not a side effect. `MetricScore.diagnostics` carries it.
- **Output:** `MetricScore(name="hallucinations", value=float, unit="count")`,
  with `diagnostics={"shape": ..., "surface": ...}` on the derived path.

## What the analysers are given, and what they claim

These rules sit above the five metrics because a reading is only about the
files the walk actually handed over.

- **Ignored and vendored files (from 0.6.0).** The user-facing commands
  (`scan`, `watch`, `live`) honour the project's own `.gitignore` and
  `.auditorignore`, and skip `_shared.VENDOR_DIRS`. A repository's
  `.gitignore` is its authoritative statement of what is not part of it, and
  measuring a frozen data capture or a build output and reporting the result
  as a property of the user's code is a false reading. `--include-all`
  measures everything present.
  Supported pattern syntax: comments, a trailing `/` for directory-only, a
  leading or interior `/` for root-anchored, a bare name matching at any
  depth, `*`, `?`, `[...]`, `**`, and `!` to re-include. **Not** supported:
  `.gitignore` files in subdirectories, and `.git/info/exclude`.
  The experiment path (`auditor run`, `auditor experiment`) is unchanged and
  still walks every ingested file, so the figures in Table 4.1 remain
  reproducible.
- **Coverage counts what was read, not what was attempted (from 0.6.0).** A
  file whose lines were added to the scanned total before the parse was
  attempted made an unreadable project report full coverage and a value of
  0.00, which bands as OK. Where a metric's languages are present and none of
  the source parsed, the metric reports `unread` with the reason instead of a
  band, and unreadable source raises the worst band to at least `warn`: an
  unreadable file is an unknown, not a pass.
- **Densities are reported with their numerator.** Two findings in twelve
  lines is 166.67 per kLOC, which bands as RISK and tells a reader nothing
  actionable. `MetricScore.count` carries what the value is a density or mean
  of, and the reporter prints it beside the number.

## 5. Keystroke dynamics (correction frequency)
- **Definition:** count of `backspace` + `delete` events per 1000
  `keystroke` events in the interaction log.
- **Source:** the interaction log produced by each adapter, conforming to
  the capture contract in docs/METHODOLOGY.md. For agent conditions where
  every event is `agent_action`, the metric evaluates to 0 by construction
  — this is the intended behaviour and is what makes keystroke dynamics
  meaningful only as a differentiator for the human-control baseline.
- **Output:** `MetricScore(name="correction_freq", value=float, unit="per_kkey")`.
