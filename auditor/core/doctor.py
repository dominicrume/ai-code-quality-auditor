"""What this installation can and cannot actually do, right now.

Why this exists
---------------
Three field reports arrived from one event on one day. Two of them were not
about readings at all:

    env/bin/auditor scan .   -> FileNotFoundError: 'bandit'
    PS> auditor scan .       -> CommandNotFoundException

Both were correct installations that could not run, and in both cases the user
had to guess why. A tool that cannot say what is wrong with itself makes every
environment problem into a support conversation, and over MCP it makes one into
a model's guess.

So this answers one question, in one call, in a form a person and an agent can
both act on: **which parts of this work, and what exactly do I type to fix the
parts that do not.**

What it refuses to do
---------------------
Report a pass it did not establish. Each check either ran and says so, or did
not run and says that instead. There is no overall "healthy" boolean computed
from a subset, because the whole defect family this instrument exists to catch
is a green light over something nobody looked at.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import sysconfig
from dataclasses import dataclass, field

OK = "ok"
MISSING = "missing"
DEGRADED = "degraded"


@dataclass
class Check:
    """One thing that either works or does not, and what to type if it does not."""

    name: str
    state: str
    detail: str
    fix: str = ""
    affects: str = ""

    @property
    def ok(self) -> bool:
        return self.state == OK


@dataclass
class Report:
    checks: list[Check] = field(default_factory=list)

    @property
    def broken(self) -> list[Check]:
        return [c for c in self.checks if c.state == MISSING]

    @property
    def degraded(self) -> list[Check]:
        return [c for c in self.checks if c.state == DEGRADED]

    @property
    def summary(self) -> str:
        if self.broken:
            return (f"{len(self.broken)} of {len(self.checks)} checks failed; "
                    f"some readings cannot be produced")
        if self.degraded:
            return (f"all required parts work; {len(self.degraded)} optional "
                    f"feature{'s' if len(self.degraded) != 1 else ''} unavailable")
        return f"all {len(self.checks)} checks passed"

    def as_dict(self) -> dict:
        return {
            "summary": self.summary,
            "usable": not self.broken,
            "checks": [{"name": c.name, "state": c.state, "detail": c.detail,
                        "affects": c.affects, "fix": c.fix} for c in self.checks],
        }


def _runnable(module: str) -> tuple[bool, str]:
    """Can we actually run `python -m <module>` from *this* interpreter?

    Importable is not the same as runnable, and the invocation here is the one
    the analysers use, so this check fails exactly when they would.
    """
    try:
        proc = subprocess.run([sys.executable, "-m", module, "--version"],
                              capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"{type(exc).__name__}: {exc}"
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout or "exited non-zero").strip()[:200]
    return True, (proc.stdout or proc.stderr).strip().splitlines()[0][:120]


def _importable(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def run() -> Report:
    """Every check, in the order a reader needs them."""
    report = Report()
    add = report.checks.append

    add(Check("python", OK, f"{sys.version.split()[0]} at {sys.executable}",
              affects="everything"))

    # The console script, and whether the shell can see it. This is the Windows
    # report and the unactivated-venv report, answered before they are asked.
    scripts = sysconfig.get_path("scripts")
    on_path = shutil.which("auditor") is not None
    entry = os.path.join(scripts, "auditor")
    exists = os.path.exists(entry) or os.path.exists(entry + ".exe")
    if on_path:
        add(Check("auditor on PATH", OK, f"resolves to {shutil.which('auditor')}",
                  affects="the `auditor` command"))
    else:
        add(Check(
            "auditor on PATH", DEGRADED,
            f"the script is {'installed at ' + scripts if exists else 'not installed'}"
            f", which is not on PATH",
            fix=f"use `{sys.executable} -m auditor` instead, which needs no PATH",
            affects="only the bare `auditor` command; nothing else here"))

    # Bandit, through the exact invocation the analyser uses. FINDING_009.
    ok, detail = _runnable("bandit")
    add(Check("bandit (Python security)", OK if ok else MISSING, detail,
              fix="" if ok else
                  f"{sys.executable} -m pip install 'bandit>=1.8'",
              affects="" if ok else
                      "Python files are reported as unread and excluded from "
                      "the security reading. JavaScript and TypeScript are "
                      "unaffected."))

    for mod, label, affects in [
        ("radon", "radon (complexity)", "the complexity reading"),
        ("yaml", "pyyaml", "specifications and the shipped standards"),
        ("click", "click", "the command line"),
        ("rich", "rich", "formatted output"),
        ("pydantic", "pydantic", "every reading's shape"),
    ]:
        present = _importable(mod)
        add(Check(label, OK if present else MISSING,
                  "importable" if present else "not importable",
                  fix="" if present else
                      f"{sys.executable} -m pip install ai-code-quality-auditor",
                  affects="" if present else affects))

    for mod, label, extra, affects in [
        ("cryptography", "cryptography", "seal",
         "sealing and verifying a signed receipt; unsealed receipts still work"),
        ("flask", "flask", "dashboard", "`auditor live` and the dashboard"),
    ]:
        present = _importable(mod)
        add(Check(label, OK if present else DEGRADED,
                  "importable" if present else "not importable (optional)",
                  fix="" if present else
                      f"{sys.executable} -m pip install "
                      f"'ai-code-quality-auditor[{extra}]'",
                  affects="" if present else affects))

    # The standards have to be inside the wheel, or a pip-installed user cannot
    # run the conformance check at all.
    try:
        from auditor import standards
        missing = [n for n in standards.SHIPPED if not standards.path(n).is_file()]
        add(Check("packaged standards", OK if not missing else MISSING,
                  "all shipped" if not missing else f"absent: {', '.join(missing)}",
                  fix="" if not missing else
                      f"{sys.executable} -m pip install --force-reinstall "
                      f"ai-code-quality-auditor",
                  affects="" if not missing else "the KYA conformance check"))
    except Exception as exc:                       # pragma: no cover - defensive
        add(Check("packaged standards", MISSING, f"{type(exc).__name__}: {exc}",
                  affects="the KYA conformance check"))

    # Defects we already know about. An installation report that hides them is
    # the same green light over an unexamined thing that everything else here
    # exists to prevent.
    try:
        from auditor.receipts import bundle
        open_defects = bundle.open_defects()
        add(Check(
            "known open defects",
            OK if not open_defects else DEGRADED,
            "none declared" if not open_defects else
            "; ".join(f"{d['id']}: {str(d.get('affects', '')).strip()}"
                      for d in open_defects),
            affects="" if not open_defects else
                    "readings listed above may be affected; see docs/"))
    except Exception as exc:                       # pragma: no cover - defensive
        add(Check("known open defects", DEGRADED, f"could not be read: {exc}"))

    return report
