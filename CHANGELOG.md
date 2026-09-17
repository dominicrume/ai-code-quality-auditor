# Changelog

## 0.5.2 — 17 September 2026

A security release. If you use `auditor live`, upgrade.

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
