# item_25

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
`item_25`. Answer from the code alone; do not run the tools.

---

## The code

### `tool.py`

```
#!/usr/bin/env python3
"""Internal tool CLI for managing project configs."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

CONFIG_FILENAME = "config.json"

SCHEMA = {
    "type": "object",
    "required": ["name", "settings"],
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "settings": {"type": "object"},
    },
}

EXIT_OK = 0
EXIT_VALIDATION_FAIL = 1
EXIT_USER_ERROR = 2


def _config_path() -> Path:
    return Path.cwd() / CONFIG_FILENAME


def _load_config(path: Path) -> dict:
    if not path.exists():
        print(f"error: {CONFIG_FILENAME} not found in current directory", file=sys.stderr)
        sys.exit(EXIT_USER_ERROR)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save_config(path: Path, data: dict) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def cmd_init(args: argparse.Namespace) -> int:
    project_dir = Path.cwd() / args.project_name
    if project_dir.exists():
        print(f"error: directory '{args.project_name}' already exists", file=sys.stderr)
        return EXIT_USER_ERROR
    project_dir.mkdir(parents=True)
    default = {"name": args.project_name, "settings": {}}
    _save_config(project_dir / CONFIG_FILENAME, default)
    print(f"Initialized project '{args.project_name}' at {project_dir}")
    return EXIT_OK


def cmd_add(args: argparse.Namespace) -> int:
    path = _config_path()
    data = _load_config(path)
    data.setdefault("settings", {})
    data["settings"][args.key] = args.value
    _save_config(path, data)
    print(f"Added {args.key}={args.value}")
    return EXIT_OK


def cmd_list(_args: argparse.Namespace) -> int:
    path = _config_path()
    data = _load_config(path)
    settings = data.get("settings", {})
    for k, v in settings.items():
        print(f"{k}={v}")
    return EXIT_OK


def _to_yaml(data, indent: int = 0) -> str:
    pad = "  " * indent
    lines = []
    if isinstance(data, dict):
        if not data:
            return pad + "{}\n"
        for k, v in data.items():
            if isinstance(v, (dict, list)) and v:
                lines.append(f"{pad}{k}:")
                lines.append(_to_yaml(v, indent + 1).rstrip("\n"))
            else:
                lines.append(f"{pad}{k}: {_yaml_scalar(v)}")
        return "\n".join(lines) + "\n"
    if isinstance(data, list):
        if not data:
            return pad + "[]\n"
        for item in data:
            if isinstance(item, (dict, list)):
                lines.append(f"{pad}-")
                lines.append(_to_yaml(item, indent + 1).rstrip("\n"))
            else:
                lines.append(f"{pad}- {_yaml_scalar(item)}")
        return "\n".join(lines) + "\n"
    return pad + _yaml_scalar(data) + "\n"


def _yaml_scalar(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    if s == "" or any(c in s for c in ":#\n") or s.strip() != s:
        return json.dumps(s)
    return s


def _to_toml(data: dict) -> str:
    lines = []
    tables = {}
    for k, v in data.items():
        if isinstance(v, dict):
            tables[k] = v
        else:
            lines.append(f"{k} = {_toml_value(v)}")
    for tname, tval in tables.items():
        lines.append("")
        lines.append(f"[{tname}]")
        for k, v in tval.items():
            lines.append(f"{k} = {_toml_value(v)}")
    return "\n".join(lines) + "\n"


def _toml_value(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, list):
        return "[" + ", ".join(_toml_value(x) for x in v) + "]"
    return json.dumps(str(v))


def cmd_export(args: argparse.Namespace) -> int:
    path = _config_path()
    data = _load_config(path)
    if args.format == "json":
        sys.stdout.write(json.dumps(data, indent=2) + "\n")
    elif args.format == "yaml":
        sys.stdout.write(_to_yaml(data))
    elif args.format == "toml":
        sys.stdout.write(_to_toml(data))
    return EXIT_OK


def _validate(data, schema) -> list[str]:
    errors = []
    t = schema.get("type")
    if t == "object":
        if not isinstance(data, dict):
            errors.append(f"expected object, got {type(data).__name__}")
            return errors
        for req in schema.get("required", []):
            if req not in data:
                errors.append(f"missing required field: {req}")
        for k, sub in schema.get("properties", {}).items():
            if k in data:
                errors.extend(_validate(data[k], sub))
    elif t == "string":
        if not isinstance(data, str):
            errors.append(f"expected string, got {type(data).__name__}")
        elif "minLength" in schema and len(data) < schema["minLength"]:
            errors.append(f"string shorter than minLength {schema['minLength']}")
    return errors


def cmd_validate(_args: argparse.Namespace) -> int:
    path = _config_path()
    data = _load_config(path)
    errors = _validate(data, SCHEMA)
    if errors:
        for e in errors:
            print(f"validation error: {e}", file=sys.stderr)
        return EXIT_VALIDATION_FAIL
    print("Config is valid.")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tool",
        description="Internal CLI for managing project configs.",
    )
    sub = parser.add_subparsers(dest="command", metavar="<subcommand>")

    p_init = sub.add_parser("init", help="Create a new project directory with default config.json")
    p_init.add_argument("project_name", help="Name of the project directory to create")
    p_init.set_defaults(func=cmd_init)

    p_add = sub.add_parser("add", help="Append a key/value pair to the project's config.json")
    p_add.add_argument("key", help="Config key")
    p_add.add_argument("value", help="Config value")
    p_add.set_defaults(func=cmd_add)

    p_list = sub.add_parser("list", help="Print all key/value pairs in the project's config.json")
    p_list.set_defaults(func=cmd_list)

    p_export = sub.add_parser("export", help="Write the config to stdout in the chosen format")
    p_export.add_argument(
        "--format",
        choices=["json", "yaml", "toml"],
        required=True,
        help="Output format",
    )
    p_export.set_defaults(func=cmd_export)

    p_validate = sub.add_parser("validate", help="Validate config against built-in JSON schema")
    p_validate.set_defaults(func=cmd_validate)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else EXIT_USER_ERROR
        if code == 2:
            return EXIT_USER_ERROR
        return code
    if not getattr(args, "command", None):
        parser.print_help()
        return EXIT_USER_ERROR
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
```
