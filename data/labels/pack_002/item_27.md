# item_27

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
`item_27`. Answer from the code alone; do not run the tools.

---

## The code

### `README.md`

```
# Internal Tool CLI

Command-line utility for managing project configuration in `config.json`.

## Install

```bash
pip install -e ".[dev]"
```

## Usage

```bash
tool init my-project
cd my-project
tool add env staging
tool list
tool export --format yaml
tool validate
tool --help
tool export --help
```

## Exit Codes

- `0` success
- `1` validation failure
- `2` user error
```

### `pyproject.toml`

```
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "internal_tool_cli"
version = "1.0.0"
description = "Internal CLI for project configuration management"
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
```

### `tests/test_cli.py`

```
"""Tests for the internal tool CLI."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from tool.cli import run
from tool.config import CONFIG_FILENAME, config_path, validate_config


@pytest.fixture
def project_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_init_creates_project_with_default_config(project_dir: Path) -> None:
    assert run(["init", "demo"]) == 0
    created = project_dir / "demo"
    assert created.is_dir()
    assert json.loads((created / CONFIG_FILENAME).read_text(encoding="utf-8")) == {}


def test_add_and_list(project_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert run(["init", "demo"]) == 0
    monkeypatch.chdir(project_dir / "demo")
    assert run(["add", "env", "staging"]) == 0
    assert run(["add", "region", "us-east"]) == 0
    completed = subprocess.run(
        [sys.executable, "-m", "tool", "list"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    assert completed.stdout.splitlines() == ["env=staging", "region=us-east"]


def test_export_formats(project_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert run(["init", "demo"]) == 0
    demo = project_dir / "demo"
    monkeypatch.chdir(demo)
    assert run(["add", "mode", "active"]) == 0

    json_out = subprocess.run(
        [sys.executable, "-m", "tool", "export", "--format", "json"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert json_out.returncode == 0
    assert json.loads(json_out.stdout) == {"mode": "active"}

    yaml_out = subprocess.run(
        [sys.executable, "-m", "tool", "export", "--format", "yaml"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert yaml_out.returncode == 0
    assert yaml.safe_load(yaml_out.stdout) == {"mode": "active"}

    toml_out = subprocess.run(
        [sys.executable, "-m", "tool", "export", "--format", "toml"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert toml_out.returncode == 0
    assert 'mode = "active"' in toml_out.stdout


def test_validate_success_and_failure(project_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert run(["init", "demo"]) == 0
    demo = project_dir / "demo"
    monkeypatch.chdir(demo)

    assert run(["validate"]) == 0

    config_file = config_path()
    config_file.write_text('{"count": 1}', encoding="utf-8")
    assert run(["validate"]) == 1
    errors = validate_config()
    assert errors


def test_help_and_user_errors(project_dir: Path) -> None:
    help_out = subprocess.run(
        [sys.executable, "-m", "tool", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert help_out.returncode == 0
    assert "init" in help_out.stdout
    assert "export" in help_out.stdout
    assert "Exit codes:" in help_out.stdout

    sub_help = subprocess.run(
        [sys.executable, "-m", "tool", "export", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert sub_help.returncode == 0
    assert "--format" in sub_help.stdout

    assert run([]) == 2
    assert run(["unknown"]) == 2
    assert run(["add", "only-key"]) == 2
```

### `tool/__init__.py`

```
"""Internal tool CLI for project configuration management."""

__version__ = "1.0.0"
```

### `tool/__main__.py`

```
"""Module entry point for python -m tool."""

from tool.cli import main

if __name__ == "__main__":
    main()
```

### `tool/cli.py`

```
"""Command-line interface for the internal tool."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tool import __version__
from tool.config import add_entry, export_config, init_project, load_config, validate_config

EXIT_SUCCESS = 0
EXIT_VALIDATION_FAILURE = 1
EXIT_USER_ERROR = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tool",
        description="Manage project configuration stored in config.json.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exit codes:\n"
            "  0  success\n"
            "  1  validation failure\n"
            "  2  user error (unknown subcommand, missing arguments)"
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", metavar="subcommand")

    init_parser = subparsers.add_parser(
        "init",
        help="Create a project directory with a default config.json.",
        description="Create a new project directory containing a default config.json file.",
    )
    init_parser.add_argument(
        "project_name",
        help="Name of the project directory to create.",
    )

    add_parser = subparsers.add_parser(
        "add",
        help="Append a key/value pair to the project's config.json.",
        description="Add or update a key/value pair in the current project's config.json.",
    )
    add_parser.add_argument("key", help="Configuration key to set.")
    add_parser.add_argument("value", help="Configuration value to store.")

    subparsers.add_parser(
        "list",
        help="Print every key/value pair in the project's config.json.",
        description="List all key/value pairs from the current project's config.json.",
    )

    export_parser = subparsers.add_parser(
        "export",
        help="Write the config to stdout in the chosen format.",
        description="Export the current project's config.json to stdout.",
    )
    export_parser.add_argument(
        "--format",
        choices=["json", "yaml", "toml"],
        default="json",
        help="Output format (default: json).",
    )

    subparsers.add_parser(
        "validate",
        help="Validate config.json against the built-in JSON schema.",
        description="Validate the current project's config.json against the built-in schema.",
    )

    return parser


def run(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code
        if isinstance(code, int):
            return code
        return EXIT_USER_ERROR

    if args.command is None:
        parser.print_help()
        return EXIT_USER_ERROR

    try:
        if args.command == "init":
            project_dir = init_project(args.project_name)
            print(f"Created project at {project_dir}")
            return EXIT_SUCCESS

        if args.command == "add":
            add_entry(args.key, args.value)
            return EXIT_SUCCESS

        if args.command == "list":
            config = load_config()
            if not config:
                return EXIT_SUCCESS
            for key in sorted(config):
                print(f"{key}={config[key]}")
            return EXIT_SUCCESS

        if args.command == "export":
            sys.stdout.write(export_config(args.format))
            return EXIT_SUCCESS

        if args.command == "validate":
            errors = validate_config()
            if errors:
                for message in errors:
                    print(message, file=sys.stderr)
                return EXIT_VALIDATION_FAILURE
            print("Config is valid.")
            return EXIT_SUCCESS

    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USER_ERROR
    except FileExistsError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USER_ERROR
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USER_ERROR

    parser.print_help()
    return EXIT_USER_ERROR


def main() -> None:
    raise SystemExit(run())
```

### `tool/config.py`

```
"""Configuration file helpers."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any

import jsonschema
import tomli_w
import yaml

CONFIG_FILENAME = "config.json"
DEFAULT_CONFIG: dict[str, str] = {}


def config_path(project_dir: Path | None = None) -> Path:
    base = project_dir if project_dir is not None else Path.cwd()
    return base / CONFIG_FILENAME


def load_config(project_dir: Path | None = None) -> dict[str, str]:
    path = config_path(project_dir)
    if not path.is_file():
        raise FileNotFoundError(f"Config not found: {path}")
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("Config must be a JSON object")
    return {str(key): str(value) for key, value in data.items()}


def save_config(config: dict[str, str], project_dir: Path | None = None) -> None:
    path = config_path(project_dir)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2, sort_keys=True)
        handle.write("\n")


def init_project(project_name: str, base_dir: Path | None = None) -> Path:
    root = (base_dir if base_dir is not None else Path.cwd()) / project_name
    if root.exists():
        raise FileExistsError(f"Project directory already exists: {root}")
    root.mkdir(parents=False)
    save_config(dict(DEFAULT_CONFIG), root)
    return root


def add_entry(key: str, value: str, project_dir: Path | None = None) -> dict[str, str]:
    config = load_config(project_dir)
    config[key] = value
    save_config(config, project_dir)
    return config


def load_schema() -> dict[str, Any]:
    schema_text = resources.files("tool").joinpath("schema.json").read_text(encoding="utf-8")
    return json.loads(schema_text)


def validate_config(project_dir: Path | None = None) -> list[str]:
    path = config_path(project_dir)
    if not path.is_file():
        return [f"Config not found: {path}"]

    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:
        return [f"Invalid JSON in {path}: {exc}"]

    schema = load_schema()
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda err: list(err.path))
    if errors:
        return [error.message for error in errors]
    return []


def export_config(fmt: str, project_dir: Path | None = None) -> str:
    config = load_config(project_dir)
    if fmt == "json":
        return json.dumps(config, indent=2, sort_keys=True) + "\n"
    if fmt == "yaml":
        return yaml.safe_dump(config, sort_keys=True)
    if fmt == "toml":
        return tomli_w.dumps(config)
    raise ValueError(f"Unsupported format: {fmt}")
```
