# item_28

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
`item_28`. Answer from the code alone; do not run the tools.

---

## The code

### `tool.py`

```
#!/usr/bin/env python3
"""Internal tool CLI for managing project config files."""
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
EXIT_VALIDATION = 1
EXIT_USER_ERROR = 2


def _config_path() -> Path:
    return Path.cwd() / CONFIG_FILENAME


def _load_config() -> dict:
    path = _config_path()
    if not path.exists():
        print(f"error: {CONFIG_FILENAME} not found in current directory", file=sys.stderr)
        sys.exit(EXIT_USER_ERROR)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save_config(cfg: dict) -> None:
    with _config_path().open("w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
        f.write("\n")


def _validate(cfg: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(cfg, dict):
        return ["config root must be an object"]
    for key in SCHEMA["required"]:
        if key not in cfg:
            errors.append(f"missing required key: {key}")
    if "name" in cfg and (not isinstance(cfg["name"], str) or not cfg["name"]):
        errors.append("'name' must be a non-empty string")
    if "settings" in cfg and not isinstance(cfg["settings"], dict):
        errors.append("'settings' must be an object")
    return errors


def cmd_init(args: argparse.Namespace) -> int:
    project = args.project_name
    project_dir = Path.cwd() / project
    try:
        project_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        print(f"error: directory '{project}' already exists", file=sys.stderr)
        return EXIT_USER_ERROR
    default_cfg = {"name": project, "settings": {}}
    with (project_dir / CONFIG_FILENAME).open("w", encoding="utf-8") as f:
        json.dump(default_cfg, f, indent=2)
        f.write("\n")
    print(f"initialized project '{project}' at {project_dir}")
    return EXIT_OK


def cmd_add(args: argparse.Namespace) -> int:
    cfg = _load_config()
    cfg.setdefault("settings", {})[args.key] = args.value
    _save_config(cfg)
    print(f"added {args.key}={args.value}")
    return EXIT_OK


def cmd_list(args: argparse.Namespace) -> int:
    cfg = _load_config()
    settings = cfg.get("settings", {})
    if not settings:
        return EXIT_OK
    for k, v in settings.items():
        print(f"{k}={v}")
    return EXIT_OK


def _to_yaml(cfg: dict, indent: int = 0) -> str:
    lines = []
    pad = "  " * indent
    for k, v in cfg.items():
        if isinstance(v, dict):
            if v:
                lines.append(f"{pad}{k}:")
                lines.append(_to_yaml(v, indent + 1))
            else:
                lines.append(f"{pad}{k}: {{}}")
        elif isinstance(v, list):
            lines.append(f"{pad}{k}:")
            for item in v:
                lines.append(f"{pad}- {item}")
        elif isinstance(v, bool):
            lines.append(f"{pad}{k}: {'true' if v else 'false'}")
        elif v is None:
            lines.append(f"{pad}{k}: null")
        elif isinstance(v, (int, float)):
            lines.append(f"{pad}{k}: {v}")
        else:
            lines.append(f"{pad}{k}: {json.dumps(v)}")
    return "\n".join(lines)


def _toml_value(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, str):
        return json.dumps(v)
    if isinstance(v, list):
        return "[" + ", ".join(_toml_value(x) for x in v) + "]"
    raise ValueError(f"unsupported toml value: {type(v).__name__}")


def _to_toml(cfg: dict) -> str:
    top_scalars = []
    tables = {}
    for k, v in cfg.items():
        if isinstance(v, dict):
            tables[k] = v
        else:
            top_scalars.append(f"{k} = {_toml_value(v)}")
    out = list(top_scalars)
    for tname, tval in tables.items():
        if out:
            out.append("")
        out.append(f"[{tname}]")
        for k, v in tval.items():
            out.append(f"{k} = {_toml_value(v)}")
    return "\n".join(out)


def cmd_export(args: argparse.Namespace) -> int:
    cfg = _load_config()
    fmt = args.format
    if fmt == "json":
        print(json.dumps(cfg, indent=2))
    elif fmt == "yaml":
        print(_to_yaml(cfg))
    elif fmt == "toml":
        print(_to_toml(cfg))
    else:
        print(f"error: unknown format '{fmt}'", file=sys.stderr)
        return EXIT_USER_ERROR
    return EXIT_OK


def cmd_validate(args: argparse.Namespace) -> int:
    cfg = _load_config()
    errors = _validate(cfg)
    if errors:
        for e in errors:
            print(f"validation error: {e}", file=sys.stderr)
        return EXIT_VALIDATION
    print("config is valid")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tool",
        description="Internal tool for managing project config files.",
    )
    sub = parser.add_subparsers(dest="command", metavar="<subcommand>")

    p_init = sub.add_parser("init", help="Create a new project directory with default config.json")
    p_init.add_argument("project_name", help="Name of the project directory to create")
    p_init.set_defaults(func=cmd_init)

    p_add = sub.add_parser("add", help="Append a key/value pair to config.json")
    p_add.add_argument("key", help="Config key")
    p_add.add_argument("value", help="Config value")
    p_add.set_defaults(func=cmd_add)

    p_list = sub.add_parser("list", help="Print all key/value pairs in config.json")
    p_list.set_defaults(func=cmd_list)

    p_export = sub.add_parser("export", help="Export the config to stdout in a chosen format")
    p_export.add_argument(
        "--format",
        choices=["json", "yaml", "toml"],
        required=True,
        help="Output format",
    )
    p_export.set_defaults(func=cmd_export)

    p_validate = sub.add_parser("validate", help="Validate config.json against the built-in schema")
    p_validate.set_defaults(func=cmd_validate)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        parser.print_help()
        return EXIT_USER_ERROR
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else EXIT_USER_ERROR
        return EXIT_USER_ERROR if code != 0 else EXIT_OK
    if not getattr(args, "func", None):
        parser.print_help()
        return EXIT_USER_ERROR
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
```
