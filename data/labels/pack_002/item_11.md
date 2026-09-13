# item_11

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
`item_11`. Answer from the code alone; do not run the tools.

---

## The code

### `pyproject.toml`

```
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "internal_tool_cli"
version = "1.0.0"
description = "Internal CLI for project configuration management"
requires-python = ">=3.9"
dependencies = [
    "jsonschema>=4.0.0",
    "PyYAML>=6.0",
    "tomli-w>=1.0.0",
]

[project.scripts]
tool = "internal_tool_cli.cli:main"

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
from __future__ import annotations

import argparse
import sys

from internal_tool_cli import __version__
from internal_tool_cli.commands import cmd_add, cmd_export, cmd_init, cmd_list, cmd_validate
from internal_tool_cli.config import EXIT_USER_ERROR


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tool",
        description="Manage project configuration files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exit codes:\n"
            "  0  success\n"
            "  1  validation failure\n"
            "  2  user error (unknown subcommand, missing args, missing config)"
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show program version and exit.",
    )

    subparsers = parser.add_subparsers(dest="command", metavar="subcommand")

    init_parser = subparsers.add_parser(
        "init",
        help="Create a project directory with a default config.json.",
        description="Create a new project directory containing a default config.json.",
    )
    init_parser.add_argument(
        "project_name",
        help="Name of the project directory to create.",
    )
    init_parser.set_defaults(func=cmd_init)

    add_parser = subparsers.add_parser(
        "add",
        help="Append a key/value pair to the project's config.json.",
        description="Add or update a key/value pair in the current project's config.json.",
    )
    add_parser.add_argument("key", help="Configuration key to add or update.")
    add_parser.add_argument("value", help="Configuration value to store.")
    add_parser.set_defaults(func=cmd_add)

    list_parser = subparsers.add_parser(
        "list",
        help="Print every key/value pair in the project's config.json.",
        description="Print all key/value pairs from the current project's config.json.",
    )
    list_parser.set_defaults(func=cmd_list)

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
    export_parser.set_defaults(func=cmd_export)

    validate_parser = subparsers.add_parser(
        "validate",
        help="Check the config against the built-in JSON schema.",
        description="Validate the current project's config.json against the built-in schema.",
    )
    validate_parser.set_defaults(func=cmd_validate)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return EXIT_USER_ERROR

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
```

### `src/internal_tool_cli/commands.py`

```
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import jsonschema
import yaml

from internal_tool_cli.config import (
    EXIT_USER_ERROR,
    EXIT_VALIDATION_FAILURE,
    default_config,
    load_config,
    load_schema,
    save_config,
)


def cmd_init(args: argparse.Namespace) -> int:
    project_dir = Path(args.project_name)
    if project_dir.exists():
        print(f"error: project directory already exists: {project_dir}", file=sys.stderr)
        return EXIT_USER_ERROR

    project_dir.mkdir(parents=True)
    save_config(default_config(args.project_name), project_dir)
    print(f"Initialized project at {project_dir}/config.json")
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    try:
        config = load_config()
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USER_ERROR

    config[args.key] = args.value
    save_config(config)
    print(f"Added {args.key}={args.value}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    try:
        config = load_config()
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USER_ERROR

    for key in sorted(config):
        print(f"{key}={config[key]}")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    try:
        config = load_config()
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USER_ERROR

    fmt = args.format
    if fmt == "json":
        print(json.dumps(config, indent=2))
    elif fmt == "yaml":
        print(yaml.dump(config, default_flow_style=False, sort_keys=True).rstrip())
    elif fmt == "toml":
        try:
            import tomli_w
        except ImportError as exc:
            print(f"error: TOML export unavailable: {exc}", file=sys.stderr)
            return EXIT_USER_ERROR
        print(tomli_w.dumps(config).rstrip())
    else:
        print(f"error: unsupported format: {fmt}", file=sys.stderr)
        return EXIT_USER_ERROR

    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    try:
        config = load_config()
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USER_ERROR

    schema = load_schema()
    validator = jsonschema.Draft7Validator(schema)
    errors = sorted(validator.iter_errors(config), key=lambda err: list(err.path))

    if errors:
        print("Validation failed:", file=sys.stderr)
        for error in errors:
            location = ".".join(str(part) for part in error.path) or "(root)"
            print(f"  - {location}: {error.message}", file=sys.stderr)
        return EXIT_VALIDATION_FAILURE

    print("Config is valid.")
    return 0
```

### `src/internal_tool_cli/config.py`

```
from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any

CONFIG_FILENAME = "config.json"

EXIT_SUCCESS = 0
EXIT_VALIDATION_FAILURE = 1
EXIT_USER_ERROR = 2


def config_path(project_dir: Path | None = None) -> Path:
    base = project_dir if project_dir is not None else Path.cwd()
    return base / CONFIG_FILENAME


def load_config(project_dir: Path | None = None) -> dict[str, Any]:
    path = config_path(project_dir)
    if not path.is_file():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def save_config(config: dict[str, Any], project_dir: Path | None = None) -> None:
    path = config_path(project_dir)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2)
        handle.write("\n")


def default_config(project_name: str) -> dict[str, str]:
    return {
        "name": project_name,
        "version": "1.0.0",
    }


def load_schema() -> dict[str, Any]:
    schema_text = resources.files("internal_tool_cli").joinpath("schema.json").read_text(
        encoding="utf-8"
    )
    return json.loads(schema_text)
```
