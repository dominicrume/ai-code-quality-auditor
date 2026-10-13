# Changelog

## 0.5.2 — 14 October 2026

A security release, and the release that stops this tool doing the thing it
exists to catch. If you use `auditor live`, upgrade for the first section. If
you use `auditor scan`, read the second: four of the readings it printed were
wrong, and three of those four were wrong in the direction that favoured the
code being audited.

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
  are fixed; the 174 tests now actually run in CI.
