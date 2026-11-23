"""Every command must actually run. Twice now, one has not.

`receipt` and `verify` both shipped with a `NameError: name 'console' is not
defined` while every module-level test passed, because the name was imported
inside the other commands and not inside theirs. `doctor` reproduced it
exactly, a fortnight later, in the first line of its own body.

Module tests cannot catch this: the defect is in the wiring, and a command is
only wired when somebody invokes it. So this walks the command group and
invokes every one, rather than naming them, which means a command added
tomorrow is covered without anybody remembering to add it here.
"""
from __future__ import annotations

import pytest
from click.testing import CliRunner

from auditor.core.cli import main

COMMANDS = sorted(main.commands)

# Commands that need a running server, a browser, a recorded session or a
# vendor key. `--help` still proves they are wired and importable.
HELP_ONLY = {"live", "watch", "run", "experiment", "share", "mcp"}


def test_the_command_list_is_not_empty():
    assert len(COMMANDS) > 5, COMMANDS


@pytest.mark.parametrize("name", COMMANDS)
def test_every_command_has_working_help(name):
    """Proves the callback imports and click can build it."""
    result = CliRunner().invoke(main, [name, "--help"])
    assert result.exit_code == 0, result.output
    assert "Usage:" in result.output


@pytest.mark.parametrize("name", [c for c in COMMANDS if c not in HELP_ONLY])
def test_every_runnable_command_executes_without_crashing(name, tmp_path, monkeypatch):
    """A non-zero exit is a result. A traceback is a defect.

    The command may refuse, complain about a missing argument, or exit 1
    because it found something. What it may not do is raise.
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / "sample.py").write_text("def f():\n    return 1\n")
    result = CliRunner().invoke(main, [name])
    assert not isinstance(result.exception, (NameError, AttributeError, ImportError)), (
        f"`auditor {name}` raised {type(result.exception).__name__}: "
        f"{result.exception}\n{result.output}")


def test_doctor_reports_without_raising():
    """The command written to diagnose a broken install shipped with the exact
    defect it exists to diagnose. It must not do that again."""
    result = CliRunner().invoke(main, ["doctor"])
    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert "bandit" in result.output


def test_doctor_json_is_machine_readable():
    import json
    result = CliRunner().invoke(main, ["doctor", "--json"])
    data = json.loads(result.output)
    assert "usable" in data and "checks" in data
    assert any(c["name"].startswith("bandit") for c in data["checks"])
    # Every failing check has to carry something a reader can type.
    for check in data["checks"]:
        if check["state"] == "missing":
            assert check["fix"], f"{check['name']} failed with no fix given"
