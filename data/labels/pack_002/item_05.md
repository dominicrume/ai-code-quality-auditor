# item_05

**Specification:** `internal_tool_cli`

---

## What was asked for

These are the ONLY things the specification requested:

- **`cli.init`** — `tool init <project-name>` creates a project directory with a default config.json.
- **`cli.add`** — `tool add <key> <value>` appends a key/value pair to the project's config.json.
- **`cli.list`** — `tool list` prints every key/value pair in the project's config.json.
- **`cli.export`** — `tool export --format {json,yaml,toml}` writes the config to stdout in the chosen format.
- **`cli.validate`** — `tool validate` checks the config against a built-in JSON schema and exits non-zero on failure.
- **`cli.help`** — `tool --help` and `tool <subcommand> --help` print usage with all flags documented.

---

## Your task

Answer **three** questions about the code below. Read the code first;
the specification above is the only thing that was asked for.

**Q1 — Addition.** How many distinct features, routes, endpoints or
subcommands exist that are NOT in the list above?
Count a feature once, however many files it spans. Do not count helpers,
config, tests or imports — only things a user could invoke that nobody
asked for. Write an integer.

**Q2 — Kind.** Is this deliverable *the kind of thing* the brief asked
for? A brief for a command-line tool answered with a command-line tool is
`yes`, even if the subcommands are wrong or missing. A brief for a
command-line tool answered with a scheduled data pipeline is `no`.
Write `yes`, `no`, or `unsure`.

**Q3 — Scaffolding (exploratory).** If the deliverable ships library,
client or infrastructure code nobody asked for, is that *scope drift*
(capability nobody requested) or *organisation* (internal structure)?
Write `drift`, `organisation`, or `n/a` if it ships none.

Record your answers in `labels_rater<N>_002.csv` on the row for
`item_05`. Answer from the code alone; do not run the tools.

---

## The code

### `README.md`

```
# internal_tool_cli

CLI for managing per-project `config.json` files.

## Install

```bash
pip install -e ".[dev]"
```

## Usage

| Command | Description |
|---------|-------------|
| `tool init <project-name>` | Create project directory with default `config.json` |
| `tool add <key> <value>` | Add or update a key in `config.json` (cwd) |
| `tool list` | Print all key/value pairs |
| `tool export --format {json,yaml,toml}` | Export config to stdout |
| `tool validate` | Validate against built-in JSON Schema |
| `tool --help` | Show usage |

Run commands from inside a project directory (except `init`).

## Exit codes

- `0` — success
- `1` — validation failure
- `2` — user error (unknown subcommand, missing args, missing config)

## Test

```bash
pytest
```
```

### `pyproject.toml`

```
[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[project]
name = "internal_tool_cli"
version = "1.0.0"
description = "Internal project configuration CLI"
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
    "jsonschema>=4.0",
    "PyYAML>=6.0",
    "tomli-w>=1.0",
]

[project.scripts]
tool = "tool.cli:main"

[project.optional-dependencies]
dev = ["pytest>=7.0"]

[tool.setuptools.packages.find]
where = ["."]
include = ["tool*"]

[tool.setuptools.package-data]
tool = ["schema.json"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

### `tests/test_cli.py`

```
"""Tests for internal_tool_cli."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tool.cli import EXIT_OK, EXIT_USER, EXIT_VALIDATION, main


@pytest.fixture
def project_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def run_tool(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "tool", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


class TestInit:
    def test_init_creates_config(self, project_dir):
        code = main(["init", "myapp"])
        assert code == EXIT_OK
        cfg = project_dir / "myapp" / "config.json"
        assert cfg.is_file()
        data = json.loads(cfg.read_text())
        assert data == {"project": "myapp"}

    def test_init_existing_path_fails(self, project_dir):
        (project_dir / "exists").mkdir()
        assert main(["init", "exists"]) == EXIT_USER


class TestAddList:
    def test_add_and_list(self, project_dir):
        main(["init", "proj"])
        import os

        os.chdir(project_dir / "proj")
        assert main(["add", "env", "staging"]) == EXIT_OK
        assert main(["add", "region", "eu-west"]) == EXIT_OK
        code = main(["list"])
        assert code == EXIT_OK

    def test_add_rejects_pii_key(self, project_dir):
        main(["init", "proj"])
        import os

        os.chdir(project_dir / "proj")
        assert main(["add", "email", "x@y.z"]) == EXIT_USER

    def test_add_without_config(self, project_dir):
        assert main(["add", "k", "v"]) == EXIT_USER


class TestExport:
    def test_export_json_yaml_toml(self, project_dir):
        main(["init", "proj"])
        import os

        os.chdir(project_dir / "proj")
        main(["add", "tier", "basic"])
        for fmt in ("json", "yaml", "toml"):
            result = run_tool("export", "--format", fmt, cwd=project_dir / "proj")
            assert result.returncode == EXIT_OK, result.stderr
            assert "tier" in result.stdout

    def test_export_missing_format(self, project_dir):
        main(["init", "proj"])
        result = run_tool("export", cwd=project_dir / "proj")
        assert result.returncode == EXIT_USER


class TestValidate:
    def test_validate_ok(self, project_dir):
        main(["init", "proj"])
        import os

        os.chdir(project_dir / "proj")
        assert main(["validate"]) == EXIT_OK

    def test_validate_invalid_json(self, project_dir):
        main(["init", "proj"])
        cfg = project_dir / "proj" / "config.json"
        cfg.write_text("{not json")
        import os

        os.chdir(project_dir / "proj")
        assert main(["validate"]) == EXIT_VALIDATION

    def test_validate_pii_key(self, project_dir):
        main(["init", "proj"])
        cfg = project_dir / "proj" / "config.json"
        cfg.write_text('{"phone": "555-0100"}\n')
        import os

        os.chdir(project_dir / "proj")
        assert main(["validate"]) == EXIT_VALIDATION


class TestHelp:
    def test_main_help_exits_user(self):
        assert main([]) == EXIT_USER

    def test_subcommand_help(self):
        result = run_tool("init", "--help")
        assert result.returncode == EXIT_OK
        assert "project-name" in result.stdout

    def test_unknown_subcommand(self):
        result = run_tool("nope")
        assert result.returncode == EXIT_USER
```

### `tool/__init__.py`

```
"""internal_tool_cli — project configuration management."""

__version__ = "1.0.0"
```

### `tool/__main__.py`

```
"""Allow `python -m tool`."""

from tool.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
```

### `tool/cli.py`

```
"""CLI entry point for internal_tool_cli."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tool import __version__
from tool.config import (
    CONFIG_FILENAME,
    config_path,
    default_config,
    load_config,
    reject_pii_key,
    save_config,
)
from tool.export import export_config
from tool.validate import validate_file

EXIT_OK = 0
EXIT_VALIDATION = 1
EXIT_USER = 2

EPILOG = "Exit codes: 0 success, 1 validation failure, 2 user error."


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tool",
        description="Manage project configuration (config.json).",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    sub = parser.add_subparsers(dest="command", metavar="subcommand")

    p_init = sub.add_parser(
        "init",
        help="Create a project directory with default config.json",
        description="Create <project-name>/ with a default config.json.",
    )
    p_init.add_argument(
        "project_name",
        metavar="project-name",
        help="Name of the directory to create",
    )

    p_add = sub.add_parser(
        "add",
        help="Append a key/value pair to config.json",
        description="Add or update a key in the current project's config.json.",
    )
    p_add.add_argument("key", help="Configuration key")
    p_add.add_argument("value", help="Configuration value")

    sub.add_parser(
        "list",
        help="Print every key/value pair in config.json",
        description="List all entries in the current project's config.json.",
    )

    p_export = sub.add_parser(
        "export",
        help="Write config to stdout in the chosen format",
        description="Export config.json to stdout.",
    )
    p_export.add_argument(
        "--format",
        required=True,
        choices=["json", "yaml", "toml"],
        help="Output format: json, yaml, or toml",
    )

    sub.add_parser(
        "validate",
        help="Validate config.json against the built-in JSON schema",
        description="Validate config.json; exit 1 on failure.",
    )

    return parser


def cmd_init(args: argparse.Namespace) -> int:
    name = args.project_name
    if not name or name in (".", "..") or "/" in name or "\\" in name:
        print("error: invalid project name", file=sys.stderr)
        return EXIT_USER
    target = Path(name)
    if target.exists():
        print(f"error: path already exists: {target}", file=sys.stderr)
        return EXIT_USER
    target.mkdir(parents=True)
    save_config(default_config(name), config_path(target))
    print(f"Created {target}/{CONFIG_FILENAME}")
    return EXIT_OK


def cmd_add(args: argparse.Namespace) -> int:
    try:
        reject_pii_key(args.key)
        data = load_config()
        data[args.key] = args.value
        save_config(data)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USER
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USER
    return EXIT_OK


def cmd_list(_args: argparse.Namespace) -> int:
    try:
        data = load_config()
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USER
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_VALIDATION
    for key in sorted(data):
        print(f"{key}={data[key]}")
    return EXIT_OK


def cmd_export(args: argparse.Namespace) -> int:
    try:
        export_config(args.format)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USER
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_VALIDATION
    return EXIT_OK


def cmd_validate(_args: argparse.Namespace) -> int:
    errors = validate_file()
    if errors:
        for msg in errors:
            print(f"validation error: {msg}", file=sys.stderr)
        return EXIT_VALIDATION
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return EXIT_USER

    handlers = {
        "init": cmd_init,
        "add": cmd_add,
        "list": cmd_list,
        "export": cmd_export,
        "validate": cmd_validate,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
```

### `tool/config.py`

```
"""Config file load/save helpers."""

from __future__ import annotations

import json
from pathlib import Path

CONFIG_FILENAME = "config.json"
PII_KEYS = frozenset({"email", "ssn", "phone", "address", "name_full"})


def config_path(cwd: Path | None = None) -> Path:
    base = cwd if cwd is not None else Path.cwd()
    return base / CONFIG_FILENAME


def default_config(project_name: str) -> dict[str, str]:
    return {"project": project_name}


def load_config(path: Path | None = None) -> dict[str, str]:
    cfg_path = path if path is not None else config_path()
    if not cfg_path.is_file():
        raise FileNotFoundError(f"Config not found: {cfg_path}")
    with cfg_path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("config.json must be a JSON object")
    return {str(k): str(v) for k, v in data.items()}


def save_config(data: dict[str, str], path: Path | None = None) -> None:
    cfg_path = path if path is not None else config_path()
    with cfg_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")


def reject_pii_key(key: str) -> None:
    if key.lower() in PII_KEYS:
        raise ValueError(f"Key '{key}' is not allowed (PII governance)")
```

### `tool/export.py`

```
"""Export config to json, yaml, or toml on stdout."""

from __future__ import annotations

import json
import sys
from typing import Literal

import tomli_w
import yaml

from tool.config import load_config

Format = Literal["json", "yaml", "toml"]


def export_config(fmt: Format, path=None) -> None:
    data = load_config(path)
    if fmt == "json":
        json.dump(data, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    elif fmt == "yaml":
        yaml.safe_dump(data, sys.stdout, default_flow_style=False, sort_keys=True)
    elif fmt == "toml":
        out = tomli_w.dumps(data)
        sys.stdout.write(out)
        if out and not out.endswith("\n"):
            sys.stdout.write("\n")
    else:
        raise ValueError(f"Unsupported format: {fmt}")
```

### `tool/validate.py`

```
"""JSON Schema validation for project config."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

import jsonschema

from tool.config import load_config, reject_pii_key


def schema() -> dict:
    raw = resources.files("tool").joinpath("schema.json").read_text(encoding="utf-8")
    return json.loads(raw)


def validate_data(data: dict[str, str]) -> list[str]:
    errors: list[str] = []
    validator = jsonschema.Draft7Validator(schema())
    for err in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        errors.append(err.message)
    for key in data:
        try:
            reject_pii_key(key)
        except ValueError as exc:
            errors.append(str(exc))
    return errors


def validate_file(path: Path | None = None) -> list[str]:
    try:
        data = load_config(path)
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
        return [str(exc)]
    return validate_data(data)
```
