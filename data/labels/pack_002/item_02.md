# item_02

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
`item_02`. Answer from the code alone; do not run the tools.

---

## The code

### `README.md`

```
# internal_tool_cli

CLI for managing project configuration files.

## Usage

```bash
pip install -e .
tool init my-project
cd my-project
tool add environment staging
tool list
tool export --format yaml
tool validate
```

## Exit Codes

- `0` — success
- `1` — validation failure
- `2` — user error (unknown subcommand, missing args)
```

### `pyproject.toml`

```
[build-system]
requires = ["setuptools>=68.0"]
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
tool = "internal_tool_cli.cli:main"

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
]

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-data]
internal_tool_cli = ["schema.json"]
```

### `src/internal_tool_cli/__init__.py`

```
"""Internal tool CLI package."""

__version__ = "1.0.0"
```

### `src/internal_tool_cli/__main__.py`

```
from internal_tool_cli.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
```

### `src/internal_tool_cli/cli.py`

```
"""CLI entry point for the internal tool."""

from __future__ import annotations

import argparse
import sys

import jsonschema

from internal_tool_cli.commands.add import run_add
from internal_tool_cli.commands.export import run_export
from internal_tool_cli.commands.init import run_init
from internal_tool_cli.commands.list import run_list
from internal_tool_cli.commands.validate import run_validate

EXIT_SUCCESS = 0
EXIT_VALIDATION_FAILURE = 1
EXIT_USER_ERROR = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tool",
        description="Manage project configuration files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exit codes:\n"
            "  0  success\n"
            "  1  validation failure\n"
            "  2  user error (unknown subcommand, missing args)"
        ),
    )
    subparsers = parser.add_subparsers(dest="command", metavar="subcommand")

    init_parser = subparsers.add_parser(
        "init",
        help="Create a project directory with a default config.json.",
        description="Create a new project directory containing a default config.json.",
    )
    init_parser.add_argument(
        "project_name",
        metavar="project-name",
        help="Name of the project directory to create.",
    )

    add_parser = subparsers.add_parser(
        "add",
        help="Append a key/value pair to the project's config.json.",
        description="Add or update a key/value pair in the current project's config.json.",
    )
    add_parser.add_argument("key", help="Configuration key to add.")
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
        help="Check the config against the built-in JSON schema.",
        description="Validate the current project's config.json against the built-in schema.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return EXIT_USER_ERROR

    try:
        if args.command == "init":
            run_init(args.project_name)
        elif args.command == "add":
            run_add(args.key, args.value)
        elif args.command == "list":
            run_list()
        elif args.command == "export":
            run_export(args.format)
        elif args.command == "validate":
            run_validate()
        else:
            parser.print_help()
            return EXIT_USER_ERROR
    except jsonschema.ValidationError as exc:
        print(f"Validation failed: {exc.message}", file=sys.stderr)
        return EXIT_VALIDATION_FAILURE
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USER_ERROR
    except FileExistsError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USER_ERROR
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USER_ERROR

    return EXIT_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())
```

### `src/internal_tool_cli/commands/__init__.py`

```
"""CLI subcommand implementations."""
```

### `src/internal_tool_cli/commands/add.py`

```
"""Add command implementation."""

from __future__ import annotations

from pathlib import Path

from internal_tool_cli.config import load_config, save_config


def run_add(key: str, value: str, cwd: Path | None = None) -> None:
    base = cwd or Path.cwd()
    config_file = base / "config.json"
    config = load_config(config_file)
    config[key] = value
    save_config(config, config_file)
```

### `src/internal_tool_cli/commands/export.py`

```
"""Export command implementation."""

from __future__ import annotations

import json
import sys
from io import BytesIO
from pathlib import Path
from typing import BinaryIO, TextIO

import yaml

from internal_tool_cli.config import load_config

try:
    import tomli_w
except ImportError:  # pragma: no cover
    tomli_w = None


def run_export(
    fmt: str,
    cwd: Path | None = None,
    output: TextIO | BinaryIO | None = None,
) -> None:
    config = load_config((cwd or Path.cwd()) / "config.json")

    if fmt == "json":
        stream: TextIO = output if output is not None else sys.stdout  # type: ignore[assignment]
        json.dump(config, stream, indent=2)
        stream.write("\n")
        return

    if fmt == "yaml":
        stream = output if output is not None else sys.stdout  # type: ignore[assignment]
        yaml.dump(config, stream, default_flow_style=False, sort_keys=True)
        return

    if fmt == "toml":
        if tomli_w is None:
            raise RuntimeError("tomli-w is required for TOML export")
        if output is None:
            tomli_w.dump(config, sys.stdout.buffer)
            sys.stdout.buffer.write(b"\n")
            sys.stdout.buffer.flush()
            return
        if isinstance(output, BytesIO):
            tomli_w.dump(config, output)
            output.write(b"\n")
            return
        raise TypeError("TOML export requires stdout or a BytesIO buffer")

    raise ValueError(f"Unsupported export format: {fmt}")
```

### `src/internal_tool_cli/commands/init.py`

```
"""Init command implementation."""

from __future__ import annotations

from pathlib import Path

from internal_tool_cli.config import default_config, save_config


def run_init(project_name: str, cwd: Path | None = None) -> None:
    base = cwd or Path.cwd()
    project_dir = base / project_name

    if project_dir.exists():
        raise FileExistsError(f"Project directory already exists: {project_dir}")

    project_dir.mkdir(parents=True)
    save_config(default_config(project_name), project_dir / "config.json")
```

### `src/internal_tool_cli/commands/list.py`

```
"""List command implementation."""

from __future__ import annotations

from pathlib import Path

from internal_tool_cli.config import load_config


def run_list(cwd: Path | None = None) -> None:
    config = load_config((cwd or Path.cwd()) / "config.json")
    for key in sorted(config):
        print(f"{key}={config[key]}")
```

### `src/internal_tool_cli/commands/validate.py`

```
"""Validate command implementation."""

from __future__ import annotations

from pathlib import Path

import jsonschema

from internal_tool_cli.config import load_config, load_schema


def run_validate(cwd: Path | None = None) -> None:
    config = load_config((cwd or Path.cwd()) / "config.json")
    schema = load_schema()
    jsonschema.validate(instance=config, schema=schema)
```

### `src/internal_tool_cli/config.py`

```
"""Shared configuration helpers."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any

CONFIG_FILENAME = "config.json"
DEFAULT_VERSION = "1.0.0"


def default_config(project_name: str) -> dict[str, str]:
    return {
        "project": project_name,
        "version": DEFAULT_VERSION,
    }


def config_path(cwd: Path | None = None) -> Path:
    return (cwd or Path.cwd()) / CONFIG_FILENAME


def load_config(path: Path | None = None) -> dict[str, Any]:
    config_file = path or config_path()
    if not config_file.is_file():
        raise FileNotFoundError(f"Config file not found: {config_file}")
    with config_file.open(encoding="utf-8") as handle:
        return json.load(handle)


def save_config(config: dict[str, Any], path: Path | None = None) -> None:
    config_file = path or config_path()
    with config_file.open("w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2)
        handle.write("\n")


def load_schema() -> dict[str, Any]:
    schema_text = resources.files("internal_tool_cli").joinpath("schema.json").read_text(
        encoding="utf-8"
    )
    return json.loads(schema_text)
```

### `tests/test_cli.py`

```
"""Tests for the internal tool CLI."""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

import jsonschema
import pytest
import yaml

from internal_tool_cli.cli import EXIT_SUCCESS, EXIT_USER_ERROR, EXIT_VALIDATION_FAILURE, main
from internal_tool_cli.commands.export import run_export
from internal_tool_cli.config import default_config, load_schema, save_config


@pytest.fixture
def project_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    project = tmp_path / "demo"
    project.mkdir()
    save_config(default_config("demo"), project / "config.json")
    monkeypatch.chdir(project)
    return project


def test_init_creates_project_with_default_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "my-app"]) == EXIT_SUCCESS

    project = tmp_path / "my-app"
    assert project.is_dir()
    config = json.loads((project / "config.json").read_text(encoding="utf-8"))
    assert config == {"project": "my-app", "version": "1.0.0"}


def test_add_appends_key_value(project_dir: Path) -> None:
    assert main(["add", "region", "us-east"]) == EXIT_SUCCESS
    config = json.loads((project_dir / "config.json").read_text(encoding="utf-8"))
    assert config["region"] == "us-east"


def test_list_prints_sorted_pairs(project_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main(["add", "region", "us-east"])
    main(["list"])
    captured = capsys.readouterr()
    lines = captured.out.strip().splitlines()
    assert lines == ["project=demo", "region=us-east", "version=1.0.0"]


def test_export_json_yaml_toml(project_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main(["add", "mode", "active"])

    main(["export", "--format", "json"])
    exported_json = json.loads(capsys.readouterr().out)
    assert exported_json["mode"] == "active"

    main(["export", "--format", "yaml"])
    exported_yaml = yaml.safe_load(capsys.readouterr().out)
    assert exported_yaml["mode"] == "active"

    buffer = BytesIO()
    run_export("toml", cwd=project_dir, output=buffer)
    assert b'mode = "active"' in buffer.getvalue()


def test_validate_success_and_failure(project_dir: Path) -> None:
    assert main(["validate"]) == EXIT_SUCCESS

    config = json.loads((project_dir / "config.json").read_text(encoding="utf-8"))
    config["version"] = "not-semver"
    save_config(config, project_dir / "config.json")
    assert main(["validate"]) == EXIT_VALIDATION_FAILURE


def test_validate_against_schema_directly() -> None:
    schema = load_schema()
    jsonschema.validate(instance={"project": "demo", "version": "1.0.0"}, schema=schema)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance={"project": "demo"}, schema=schema)


def test_no_command_prints_help_and_exits_user_error(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == EXIT_USER_ERROR
    help_text = capsys.readouterr().out
    assert "usage: tool" in help_text
    assert "init" in help_text
    assert "add" in help_text
    assert "list" in help_text
    assert "export" in help_text
    assert "validate" in help_text


def test_root_help_documents_commands(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    help_text = capsys.readouterr().out
    assert "init" in help_text
    assert "export" in help_text


def test_subcommand_help_documents_flags(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["init", "--help"])
    assert exc.value.code == 0
    assert "project-name" in capsys.readouterr().out

    with pytest.raises(SystemExit) as exc:
        main(["export", "--help"])
    assert exc.value.code == 0
    assert "--format" in capsys.readouterr().out


def test_unknown_command_is_user_error() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["missing-command"])
    assert exc.value.code == EXIT_USER_ERROR


def test_missing_config_is_user_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["list"]) == EXIT_USER_ERROR


def test_init_existing_directory_is_user_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "exists"
    project.mkdir()
    monkeypatch.chdir(tmp_path)
    assert main(["init", "exists"]) == EXIT_USER_ERROR
```
