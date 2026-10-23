# Changelog

## 0.6.1 — 24 October 2026

A user pointed 0.6.0 at a folder of working documents and it answered
"0 of 12 delivered" against twelve things nobody had asked for. It had fallen
through to its weakest source of intent, the subjects of recent `feat:`
commits, harvested twelve errands from a documents repository, and scored the
folder against them.

Every component behaved correctly. The system still stated as measurement
something it did not know.

**What changed.** Every fidelity reading now carries what it rests on, graded
where the reading is computed and consulted by every surface before anything
renders:

- `MEASURED` — a human supplied the brief. Reported plainly.
- `PROVISIONAL` — derived, and the code corroborated some of it. Reported,
  labelled, every time.
- `WITHHELD` — derived, and it corroborated nothing. No verdict; the reason
  and the remedy instead.

A derived brief is never a measurement however much of it matches, because the
thing in doubt is the brief rather than the degree of fit. There is no
threshold to tune: the only line is corroboration versus none, and a brief
matching nothing has supplied the one piece of evidence bearing on its own
validity.

**What did not change.** A specification you supply reports exactly as before,
including zero delivered — that reading is a finding, and a test pins it.

Written up in full as `docs/FINDING_002_guessed_brief.md`. It is the fourth
defect recorded against this instrument rather than quietly patched, and the
first found by somebody outside the project.

## 0.6.0 — 14 October 2026

One release, and the only one to install. It closes a vulnerability the
published 0.5.1 still carries, stops the tool reporting numbers about code it
never read, and makes it answer the question it exists for: was each thing you
asked for actually built?

A 0.5.2 was prepared as a security-only patch and **never published**. Rather
than ship two releases days apart and leave anybody on the smaller one,
everything it contained is in this release. Whatever version you are on, this
is the upgrade.

### Fixed — security

- **`auditor live` accepted state-changing requests from other pages.**
  The server binds to 127.0.0.1, which keeps other machines out but does not
  keep out a page the user already has open in the same browser: any site can
  POST to localhost. Only `/api/brief` checked the `Origin` header. The four
  routes that did not include `/api/remediate`, which rewrites files across the
  watched tree, and `/api/drift/strip`, which deletes an endpoint from source.
  The check is now a decorator applied to every POST route, and a test walks
  the route table so a route added later cannot arrive unguarded.
- **The scope-drift controls interpolated filenames into `onclick` strings.**
  Every other value on the live page was escaped; these were not. An
  apostrophe in a path broke the handler, and a crafted filename could extend
  it. Values are now escaped and carried in data attributes, handled by one
  delegated listener.
- **The published dashboard served two routes it should never have had.**
  `auditor.dashboard` carried copies of `/api/scan` and
  `/api/drift/acknowledge` from the live server. On a public host they were
  reachable with no authentication — one would describe the structure of any
  path the process could read, the other would write to `.auditor/spec.yaml`.
  Nothing called either. Both are removed.

### Fixed — readings that claimed more than was read

- **Unreadable code was reported as `OK`.** A directory whose only Python file
  would not parse printed `Security 0.00 OK`, `Complexity 0.00 OK`. The lines
  of a file were added to the scanned total before the parse was attempted, so
  coverage read 100%, the value stayed 0.00 for want of any finding, and 0.00
  bands as OK. Coverage now counts what was read. Where a metric's languages
  are present and nothing parsed, the row reads `unread` with the reason
  instead of a band, the files are named, and the worst band is raised to at
  least `warn`, so `--fail-on warn` no longer exits 0 on code nobody could
  read. An unreadable file is an unknown, not a pass.
- **Ignored and vendored files were measured.** Pointed at this repository,
  `auditor scan` reported `Duplication 83.58 RISK`. The arithmetic was right
  and the subject was wrong: it was describing `data/raw`, a frozen set of
  research captures that git ignores and the project does not ship. `scan`,
  `watch` and `live` now honour the project's own `.gitignore` and
  `.auditorignore` and skip vendored directories. `--include-all` restores the
  old behaviour. The same scan now reads 217 files instead of 2,300.
- **Code duplication counted prose.** The metric needs no parser, so it had
  been shingling Markdown too: 41,116 lines of documentation against 12,431 of
  Python on this repository, which made three-quarters of the figure a
  statement about a changelog. It now counts code only, and the same scan reads
  `3.60 OK`. `analyze(..., version=1)` keeps the old behaviour so the published
  study figures stay reproducible.
- **A density was printed without its numerator.** Six lines of TypeScript with
  one hardcoded password scored `250.00 RISK`, which is arithmetically true and
  tells a reader nothing. Every density and mean now prints what it counted
  beside it: `250.00 RISK · 1 finding`.

### Changed — the evidence rule (see docs/ERRATUM_003_token_evidence.md)

- **A feature was credited as delivered when a word appeared anywhere in the
  codebase.** `manifest_deriver._evidence` concatenated every file into one
  string and asked whether the feature id's terminal token was in it. A word
  in a comment satisfied it; on Python `cli.list` was satisfied by `list(x)`.
  Measured: a six-feature CLI specification against an ETL script implementing
  none of it credited **all six**, and reported drift of 0, because a credited
  feature suppresses the unrequested command that would otherwise be counted.
  That is the mechanism behind the finding in §6.4, recorded there as a
  limitation and corrected here as the defect it was.
- A feature is now credited only where the codebase **declares** something:
  a registered subcommand, an HTTP route, a function, a class or an export,
  indexed with its file and line by the new `analyzers/definitions.py`. The
  match is on the feature's head token, and a scaffolding name such as `cli`
  is never evidence on its own — it had been crediting four features to a
  single `def cli()` group function.
- `version=1` retains the old rule unchanged, so the published study figures
  stay exactly reproducible. This is the arrangement already used for security
  density and complexity after Erratum 001. Version 2 is the default, because
  an instrument whose default over-credits delivery reports in the direction
  that flatters the code it is auditing.

### Added — what is missing, which was never reported

- **`auditor scan` now prints a per-feature verdict table.** Every specified
  feature is `delivered`, `not_found`, or `unreachable`, each with the file and
  line of its evidence or a plain statement that there is none:

  ```
  Specification fidelity  2 of 6 delivered

  ✓  add.item        cli.py:7    subcommand "add"
  ✓  list.items      cli.py:13   subcommand "list"
  !  export.csv      cli.py:17   function export_csv exists, but nothing exposes it
  ✗  validate.input              not found
  ✗  show.help                   not found
  !  remove.item     store.py:1  function remove_item exists, but nothing exposes it
  ~  scheduler       cli.py:20   not asked for
  ```

- **The report names what you asked for, in your words.** The id is a key
  written for the matcher: "Notify the assessor when a claim is submitted"
  slugs to `notify.assessor.when`, which is accurate, unreadable, and the
  wrong thing to put in front of a client. The sentence is the label on every
  surface; the id stays in the file, in the JSON and on hover, where a machine
  or a person matching rows needs it.
- **A language hook is never a feature.** `__init__` was credited as the
  `init` subcommand of a CLI specification.
- **Nothing internal is user-reachable in a codebase with no surface.** When a
  specification asks for a command-line tool and the project declares no
  subcommand and no route anywhere, an internal function cannot be invoked by
  a user however many other internal functions call it. Run against the
  study's own `antigravity x internal_tool_cli` capture (docs/FINDING_001),
  the report said two of six delivered on a brief that was not implemented at
  all, because `_init_db` and `validate_row` are called from inside the
  pipeline. It now reads nought of six, which is what the finding records.
- **`unreachable` requires evidence of absence, not absence of evidence.** The
  verdict first rested on a definition not itself being a command or a route,
  which describes most working code: a helper invoked by a route on the line
  above was reported as something nothing exposes. It now also requires that
  nothing in the codebase calls the name, and an exported name counts as
  reached. This is a reference count rather than a call graph, and it is used
  only to withhold the accusation, never to make one, because telling a team
  their working feature is broken costs more than missing a finding.
- **`unreachable` is a verdict in its own right.** Code that exists but that
  no user can invoke is neither delivered nor missing, and calling it either
  throws away the most useful thing an audit knows: where the work already is.
- The verdicts are in `--json` under `fidelity`, with `completeness_pct`, so a
  pipeline can gate on what is missing rather than on a density.
- Where a specification names no shape, whether delivery means something
  invokable is inferred from the project's own delivered features rather than
  assumed.

### Added — the reading no other tool offers, now reachable

- **`auditor init`** records what the project was asked to be, in plain
  English, and writes it to `.auditor/spec.yaml` for you to edit. `scan` and
  `watch` pick that file up automatically from then on.
- **`auditor scan . --brief "a CLI with init, add and list"`** does the same
  thing for one run without writing anything first.
  Scope drift was the one metric no other tool offers and it was gated behind
  hand-authoring YAML, which is why most scans reported four of five metrics as
  `n/a`. A user already typed what they wanted once; that sentence is enough.
- **Building the wrong kind of thing is now reported.** The scope-drift count
  asks what *extra* was shipped, so it cannot see a substitution: an agent
  given a CLI specification that ships an ETL package with no subcommands adds
  nothing and scores 0.00, exactly like an agent that built the CLI correctly.
  `shape_detector` had been computing that verdict since the study and the
  report discarded it. It now appears as a sentence: *you asked for a
  command-line tool, and what is here looks like a data pipeline*.
  It is **not** a sixth metric and is **not** folded into the scope-drift
  value. Either would change figures published in the dissertation, which is a
  decision for an erratum rather than a side effect.

### Added — nothing to set up, and nothing to type

- **The specification is derived on first run.** Installing this tool already
  means handing over the repository; asking the developer to then retype what
  that repository is for is asking twice for something already on disk, and it
  was the step at which most people stopped. `auditor scan` and `auditor live`
  now read whatever states intent and audit against it immediately, writing
  the result to `.auditor/spec.yaml` where it can be corrected. In order of
  authority: a requirements document, the README's feature or usage list, the
  package description, then recent `feat:` commit subjects.
- **Intent is never read from the source tree, and that is a rule rather than
  a preference.** A specification inferred from the code it measures would be
  satisfied by that code by construction: every feature delivered, nothing
  ever missing, a clean bill of health that means nothing. A project that says
  nowhere what it is for gets no specification and no scope reading, because
  inventing one would manufacture the finding.
- A derived specification is marked provisional in the file, in the terminal
  and on the live page, naming the document it came from. One somebody wrote
  is never overwritten.

### Fixed — a watch that stopped watching

- **Restarting the auditor left the page dead until someone reloaded it.** A
  browser abandons an `EventSource` after a few failed attempts and sets it to
  `CLOSED`, and nothing retried after that. Reconnection is now handled by the
  page itself: it backs off, it caps at five seconds, and it has no terminal
  state. It also re-checks when the tab becomes visible again and when the
  machine comes back online, because a socket killed by a closed lid usually
  dies without an error ever firing.
- The stream tells the browser to retry in **500ms** rather than the default
  three seconds, and sends a heartbeat every five seconds instead of twenty,
  so a connection that died silently is noticed in five seconds rather than
  twenty.
- **A momentary drop no longer flashes a warning.** A restart takes well under
  a second, and announcing a problem for that long teaches a reader to ignore
  the warning on the one occasion it means something. The page waits 1.5
  seconds of continuous failure before saying anything, and announces the
  recovery to a screen reader when it returns.

### Interface — one instrument, two themes

- The dashboard, the live page and the CLI had drifted into three looks for
  the same verdicts, because the colours were copied inline into each
  template. There is now one stylesheet, `auditor/assets/theme.css`, served by
  both web applications from the same file, and a test asserts the two serve
  identical bytes.
- **Light and dark, switchable and remembered.** Dark for a projector in a lit
  room, light for a screenshot that has to sit in an appendix and survive
  greyscale printing. The choice is resolved before first paint, because doing
  it in a deferred script flashes the wrong theme, and there is a print
  stylesheet.
- **No verdict depends on colour alone.** Every band carries a glyph as well
  as a hue, so a washed-out projector and a reader who cannot separate red
  from green both still get the reading.
- Plotly bakes colours into a chart, so the charts read theirs from the
  stylesheet and redraw when the theme changes.
- **The live page now shows the per-feature verdict.** The server was
  computing the fidelity report and discarding it, so the one surface meant to
  demonstrate the one reading no other tool produces was showing five metric
  cards and none of it. It is now the largest element on the page.
- **A dropped connection no longer looks like a healthy one.** The live page
  had two states where it needed three: "reconnecting" was drawn in the same
  accent colour as "watching", so a page whose figures were the last ones
  received looked exactly like a page whose figures were current. It is amber
  now, "not running" is red, and a line above the readings says in words that
  they may be out of date. An instrument that presents a stale number as a
  live one is doing the thing this one exists to catch.
- A rebuild of the report template dropped four things that were there for a
  reason, one of them a disclosure: `provenance.warning` was rendered inside
  an `{% if spec_summary %}`, so the case where it mattered most, a thin
  report with little else on the page, was the case where it vanished. That,
  the calibrated/raw view switch, the spec-set label and the adoption guidance
  are restored, and tests now pin the things a redesign may not move.

### Fixed

- **A brief discarded the verb, which is the feature.** `slugify` treated
  `add`, `create` and `remove` as filler, so "add an item" became the id
  `item` and "export to csv" became `csv`: the action somebody has to go and
  build was dropped and the object kept, leaving nothing for a subcommand to
  match. Verbs that name an operation the software performs are kept; verbs
  that merely instruct us to produce software ("build a course listing page")
  are still filler. Prepositions are no longer stripped, because "log in"
  without its particle is `log`.
- A feature is no longer credited to a different verb on the same noun:
  `remove.item` was being satisfied by `def add_item`.
- **A route is a method and a path, not just a path.** "Submit a claim" and
  "look up a claim" both matched `POST /claims`, so one line was cited as
  evidence for two features and the second was credited to code that does
  something else. The path carries the noun and the method carries the verb,
  and a feature whose verb implies a method no longer matches a route that
  uses a different one. A verb the mapping does not recognise still matches
  any method: the method narrows a match, it is never required to make one.

### Fixed — behaviour

- `Strip` deletes code and cannot be undone, so it now confirms before acting,
  and is coloured as the destructive action it is. Three of its CSS tokens
  were copied from a different palette and were undefined, so it had been
  rendering with no warning colour at all.
- The live page said "reconnecting" forever after the server stopped. It now
  distinguishes a retry in flight from a closed connection and says which.
- The dashboard's "Auto-Fix Issues" button POSTed to a route that app has
  never served. Every click ended in an alert. Removed.

### Fixed — the GitHub Action

- **The published action never worked.** It called
  `auditor experiment --conditions ...`, and there has never been a
  `--conditions` option, so every run exited 2 on its first command. It also
  required a pre-captured session under `data/raw/<run-id>/`, which a CI job
  does not have. It now runs `auditor scan` against the checked-out tree,
  writes the metrics to the job summary, uploads a JSON decision record, and
  defaults `fail-on` to `never` so adding it cannot break a pipeline on day
  one. The version pin moved from 0.3.0 to current.

### Accessibility

- Visible focus rings, landmarks, skip links, descriptions, a favicon,
  reduced-motion support and coarse-pointer touch targets across all four
  dashboard pages, none of which had any of them. Metric changes that cross a
  band are announced to screen readers; decimal movements are not.

### Internal

- CI ran `pytest` without installing it and had exited 127 on every run while
  being a required status check. The SonarCloud job had never had a token. Both
  are fixed; the tests now actually run in CI.
