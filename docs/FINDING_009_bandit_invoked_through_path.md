# FINDING_009 — bandit was invoked through PATH, so a correct install crashed

**Status:** fixed 23 November 2026, in 0.6.8. Pinned by
`tests/test_finding_009_and_010.py`.
**Found:** 23 November 2026, against 0.6.4. Reported by Owen Tenumah from an
unactivated virtual environment, and independently by Bright on Windows under
PowerShell. Named with their consent; see docs/CREDITS.md.
**Module:** `auditor/analyzers/security_analyzer.py`

## What happened

    python3 -m venv env
    env/bin/pip install ai-code-quality-auditor
    env/bin/auditor scan .

    FileNotFoundError: [Errno 2] No such file or directory: 'bandit'

The whole scan died. Not a degraded reading: a traceback.

## Why

`_run_bandit` ran `["bandit", "-r", ...]`. A bare command name is resolved
through PATH. `pip install` puts the console script in that environment's `bin`
directory, and **PATH does not contain it unless the environment has been
activated.** Bandit was installed, correctly, exactly where it should be, and
could not be found.

Running a tool from `env/bin/` without activating is normal, is what every CI
job does, and is the sequence in the reporter's own steps.

## Why the test suite never caught it

It was caught by a user and not by six acceptance runs from "clean" virtual
environments, including ones written in this repository to prove 0.6.3, 0.6.4
and 0.6.5 worked from a fresh install.

Those venvs were clean. The machine was not. `bandit` was present at
`~/Library/Python/3.13/bin/bandit` and on the developer's PATH, so the bare
command resolved every time. **A clean environment inside a dirty one does not
test what it looks like it tests**, and nothing in the acceptance runs sanitised
PATH.

Reproducing it needed `env -i PATH=/usr/bin:/bin`. That is now how the crash is
pinned.

## The fix

`[sys.executable, "-m", "bandit", ...]`, which the reporter proposed and which
is right: it runs bandit from the interpreter the auditor is already running
under, so an unactivated environment resolves correctly.

Two further repairs, because an invocation fix alone still leaves a tool that
dies when a dependency is missing:

- **`FileNotFoundError` and a silent non-zero exit are both caught.** Either
  means bandit could not be run.
- **The scan degrades instead of stopping.** Every Python file is reported as
  unread, the coverage falls and says so, the JavaScript and TypeScript reading
  is still produced, and the report prints *"Python was not analysed: bandit
  could not be run in this environment"*.

That last part matters more than the crash. A security density of 0.00 over
code nothing read is the precise failure this instrument was built to detect in
other tools, and silently skipping Python would have produced exactly that.
