# Credits for defects found from outside this repository

Named here with the reporter's consent. Nobody is named without it; earlier
versions of these records described the reporters rather than naming them for
that reason.

## Lagos AI Summit, 23 November 2026

The free tools were run, on the day, by builders who had not written them. Six
numbered defects came out of it. These are the first defects in this
instrument's history found by anyone other than its author.

### Owen Tenumah

Read the auditor's own source rather than only its output, and reported
`urlopen` at `core/share.py:97` as accepting any URL scheme.

The reported cause was a false positive: a scheme check nine lines above does
block `file:`. The reported **line** was right. `urlopen` follows redirects,
and Python's own handler permits the new location to be `http`, so the https
promise in that function's docstring did not survive the first redirect. A
report that points at the correct line for the wrong reason is still a good
report, and this one found a defect no test here was looking for.

Also reported the crash on `auditor scan` from an unactivated virtual
environment, and proposed the `sys.executable -m` invocation that fixes it.

- FINDING_010 — the https promise broken by a redirect
- FINDING_009 — bandit invoked through PATH

### Bright

Ran the installer on Windows, under PowerShell, where it failed at the first
command with `CommandNotFoundException` — the failure that makes a person close
the window and never come back. Reported exactly what broke.

- FINDING_009 — and the field-conditions CI matrix now installs into a
  never-activated environment on Windows, macOS and Linux so this class cannot
  return quietly.
- `auditor doctor`, which exists so the next person in that position is told
  what is wrong and what to type.

### Ola

Ran the auditor on a large, long-lived production codebase rather than a clean
fixture, and brought back the readings. Three defects fell out of one report,
and they are the most serious three in the list: the instrument showed green
over nine HIGH findings, charged a team for vendored code they did not write,
and analysed minified build output as if it were authored source.

- FINDING_005 — the security band could not fail
- FINDING_006 — vendored code reported as the project's own
- FINDING_007 — minified files analysed
- FINDING_008 — still open, and disclosed in every receipt
