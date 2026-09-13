# item_29

**Specification:** `data_pipeline`

---

## What was asked for

These are the ONLY things the specification requested:

- **`ingest.csv`** — Read a CSV file from a configurable local input directory.
- **`validate.schema`** — Validate each row against a declared column schema; reject invalid rows to a quarantine file.
- **`transform.normalise`** — Lowercase string columns and round numeric columns to two decimal places.
- **`load.sqlite`** — Write the normalised rows into a local SQLite table.
- **`schedule.daily`** — Provide a scheduler entrypoint (cron string or APScheduler) that runs the pipeline once per day.
- **`report.run_summary`** — After each run, write a JSON summary with row counts, duration, and quarantine count.

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
`item_29`. Answer from the code alone; do not run the tools.

---

## The code

### `tool.py`

```
#!/usr/bin/env python3
"""internal_tool_cli — project config management CLI."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

CONFIG_FILENAME = "config.json"

SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "settings": {"type": "object"},
    },
    "required": ["name", "settings"],
}


def config_path() -> Path:
    return Path.cwd() / CONFIG_FILENAME


def load_config() -> dict:
    p = config_path()
    if not p.exists():
        print(f"error: {CONFIG_FILENAME} not found in current directory", file=sys.stderr)
        sys.exit(2)
    try:
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"error: invalid JSON in {CONFIG_FILENAME}: {e}", file=sys.stderr)
        sys.exit(1)


def save_config(cfg: dict) -> None:
    with config_path().open("w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, sort_keys=True)
        f.write("\n")


def cmd_init(args: argparse.Namespace) -> int:
    project = args.project_name
    target = Path.cwd() / project
    if target.exists():
        print(f"error: directory '{project}' already exists", file=sys.stderr)
        return 2
    target.mkdir(parents=True)
    default = {"name": project, "settings": {}}
    with (target / CONFIG_FILENAME).open("w", encoding="utf-8") as f:
        json.dump(default, f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"initialized project '{project}' at {target}")
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    cfg = load_config()
    settings = cfg.setdefault("settings", {})
    settings[args.key] = args.value
    save_config(cfg)
    print(f"set {args.key}={args.value}")
    return 0


def cmd_list(_args: argparse.Namespace) -> int:
    cfg = load_config()
    settings = cfg.get("settings", {})
    if not settings:
        return 0
    for k in sorted(settings):
        print(f"{k}={settings[k]}")
    return 0


def _to_yaml(cfg: dict) -> str:
    def dump(value, indent: int) -> str:
        pad = "  " * indent
        if isinstance(value, dict):
            if not value:
                return "{}"
            lines = []
            for k in sorted(value):
                v = value[k]
                if isinstance(v, dict):
                    lines.append(f"{pad}{k}:")
                    if not v:
                        lines[-1] += " {}"
                    else:
                        lines.append(dump(v, indent + 1))
                else:
                    lines.append(f"{pad}{k}: {_yaml_scalar(v)}")
            return "\n".join(lines)
        return f"{pad}{_yaml_scalar(value)}"

    return dump(cfg, 0) + "\n"


def _yaml_scalar(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None:
        return "null"
    if isinstance(v, (int, float)):
        return str(v)
    return json.dumps(str(v))


def _to_toml(cfg: dict) -> str:
    lines = []
    tables = {}
    for k in sorted(cfg):
        v = cfg[k]
        if isinstance(v, dict):
            tables[k] = v
        else:
            lines.append(f"{k} = {_toml_scalar(v)}")
    for tname in sorted(tables):
        lines.append("")
        lines.append(f"[{tname}]")
        for k in sorted(tables[tname]):
            lines.append(f"{k} = {_toml_scalar(tables[tname][k])}")
    return "\n".join(lines) + "\n"


def _toml_scalar(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    return json.dumps(str(v))


def cmd_export(args: argparse.Namespace) -> int:
    cfg = load_config()
    fmt = args.format
    if fmt == "json":
        sys.stdout.write(json.dumps(cfg, indent=2, sort_keys=True) + "\n")
    elif fmt == "yaml":
        sys.stdout.write(_to_yaml(cfg))
    elif fmt == "toml":
        sys.stdout.write(_to_toml(cfg))
    return 0


def _validate(instance, schema, path: str = "") -> list[str]:
    errors: list[str] = []
    t = schema.get("type")
    type_map = {
        "object": dict,
        "string": str,
        "number": (int, float),
        "integer": int,
        "boolean": bool,
        "array": list,
    }
    if t and not isinstance(instance, type_map[t]):
        errors.append(f"{path or '<root>'}: expected {t}")
        return errors
    if t == "object":
        for req in schema.get("required", []):
            if req not in instance:
                errors.append(f"{path}: missing required key '{req}'")
        for k, sub in schema.get("properties", {}).items():
            if k in instance:
                errors.extend(_validate(instance[k], sub, f"{path}.{k}" if path else k))
    return errors


def cmd_validate(_args: argparse.Namespace) -> int:
    cfg = load_config()
    errors = _validate(cfg, SCHEMA)
    if errors:
        for e in errors:
            print(f"validation error: {e}", file=sys.stderr)
        return 1
    print("config is valid")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tool",
        description="Internal tool CLI for managing project config.",
    )
    sub = parser.add_subparsers(dest="command", metavar="<subcommand>")

    p_init = sub.add_parser("init", help="Create a new project with default config.json")
    p_init.add_argument("project_name", help="Name of the project directory to create")
    p_init.set_defaults(func=cmd_init)

    p_add = sub.add_parser("add", help="Append a key/value pair to config.json")
    p_add.add_argument("key", help="Config key")
    p_add.add_argument("value", help="Config value")
    p_add.set_defaults(func=cmd_add)

    p_list = sub.add_parser("list", help="Print all key/value pairs in config.json")
    p_list.set_defaults(func=cmd_list)

    p_export = sub.add_parser("export", help="Write config to stdout in chosen format")
    p_export.add_argument("--format", choices=["json", "yaml", "toml"], required=True,
                          help="Output format")
    p_export.set_defaults(func=cmd_export)

    p_validate = sub.add_parser("validate", help="Validate config against built-in schema")
    p_validate.set_defaults(func=cmd_validate)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 2
    try:
        return args.func(args)
    except SystemExit:
        raise
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit as e:
        # argparse exits 2 on user error already; preserve.
        raise
```
