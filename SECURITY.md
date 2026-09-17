# Security policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.3.x   | ✅ current |
| 0.2.x   | ⚠️ upgrade — the README shipped a dead dashboard link and the keystroke recorder could lose captured data |
| 0.1.x   | ❌ no |

Install or upgrade with:

```bash
pip install --upgrade ai-code-quality-auditor
```

## Reporting a vulnerability

Please report privately rather than opening a public issue.

- **Preferred:** the **Report a vulnerability** button under this repository's
  *Security* tab (GitHub private vulnerability reporting).
- **Alternative:** email admin@veritaport.co.uk with `SECURITY` in the subject.

Please include the version, your platform, what you did, and what happened.
A proof of concept is welcome but never required.

**What to expect:** acknowledgement within 5 working days, an assessment
within 15, and a fix released before public disclosure wherever the issue is
confirmed and within my control. This is a research instrument maintained by
one person alongside a doctorate — I would rather commit to a timeline I can
keep than one that sounds impressive.

## What this project does with your code

Worth stating plainly, because the tool reads source files:

- **Everything runs locally.** Analysis happens on your machine. No source
  code, metric, or filename is transmitted anywhere.
- **No telemetry.** The `auditor` command makes no network calls of its own:
  it never reports that you ran it, what you scanned, or what it found.
  (`auditor.dashboard`, the module behind the hosted site at
  auditor-dashboard-rume.fly.dev, ships in the wheel but is not started by any
  CLI command. It can email an operator when someone submits the pilot form,
  and only when SMTP credentials are configured in the environment.)
- **A local history, on your machine only.** From 0.6.0, `auditor scan` appends
  one line per scan to `~/.auditor/history.jsonl`: metric values, file and line
  counts, languages read, and the folder's path. It is yours. Read it with
  `auditor history`, find it with `auditor history --where`, delete it with
  `auditor forget --all`, and switch it off entirely with `AUDITOR_NO_HISTORY=1`
  or per scan with `--no-history`. Nothing in the scan path can send it: the
  module that can open a socket is separate and is not imported by `scan`,
  `watch` or `live`, which a test asserts.
- **Sharing is opt-in, aggregate, and off unless you type it.** `auditor share`
  prints exactly what it would send and sends nothing without both a `--to
  https://...` destination and `--yes`. What it can carry is fixed by an
  allowlist: metric values, units, bands, coverage, file and line counts,
  languages, whether a specification was supplied, the tool version, the OS
  family, the Python version, and a random installation id you can delete. What
  it never carries: a path, a folder name, a specification name, a file name, a
  finding, or a line of code. Projects appear as `p1`, `p2` inside one payload,
  numbered afresh each time. See `docs/PRIVACY.md`.
- **`auditor live` binds to `127.0.0.1` only** — the dashboard is not reachable
  from other machines on your network.
- **Nothing is written outside the audited directory**, except the spec you
  create through the browser, which is saved to `.auditor/spec.yaml` inside
  that directory so you can read and edit it.

## Security of the tool itself

`auditor` invokes [Bandit](https://bandit.readthedocs.io/) as a subprocess and
reads files under the directory it is pointed at. It does not execute the code
it audits. `auditor fix` edits files only with `--apply`, and only after the
change has been verified against a re-scan; every other invocation is a dry run.

The project audits itself in CI. Findings in its own source are visible with:

```bash
auditor scan .
```
