# item_12

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
`item_12`. Answer from the code alone; do not run the tools.

---

## The code

### `tool.py`

```
#!/usr/bin/env python3
"""Internal tool CLI for managing project config."""
import argparse
import json
import os
import sys

CONFIG_FILENAME = "config.json"

SCHEMA = {
    "type": "object",
    "required": ["name", "settings"],
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "settings": {"type": "object"},
    },
}

DEFAULT_CONFIG = {"name": "", "settings": {}}


def _find_config():
    if os.path.isfile(CONFIG_FILENAME):
        return CONFIG_FILENAME
    return None


def _load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_config(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def _validate(data):
    errors = []
    if not isinstance(data, dict):
        return ["config must be a JSON object"]
    for key in SCHEMA["required"]:
        if key not in data:
            errors.append(f"missing required key: {key}")
    props = SCHEMA["properties"]
    if "name" in data:
        if not isinstance(data["name"], str) or len(data["name"]) < 1:
            errors.append("'name' must be a non-empty string")
    if "settings" in data and not isinstance(data["settings"], dict):
        errors.append("'settings' must be an object")
    return errors


def cmd_init(args):
    project = args.project_name
    if os.path.exists(project):
        print(f"error: '{project}' already exists", file=sys.stderr)
        return 2
    os.makedirs(project)
    cfg = {"name": project, "settings": {}}
    _save_config(os.path.join(project, CONFIG_FILENAME), cfg)
    print(f"Initialized project '{project}'")
    return 0


def cmd_add(args):
    path = _find_config()
    if not path:
        print("error: config.json not found in current directory", file=sys.stderr)
        return 2
    cfg = _load_config(path)
    cfg.setdefault("settings", {})[args.key] = args.value
    _save_config(path, cfg)
    print(f"Added {args.key}={args.value}")
    return 0


def cmd_list(args):
    path = _find_config()
    if not path:
        print("error: config.json not found in current directory", file=sys.stderr)
        return 2
    cfg = _load_config(path)
    for k, v in cfg.get("settings", {}).items():
        print(f"{k}={v}")
    return 0


def _to_yaml(data, indent=0):
    lines = []
    pad = "  " * indent
    if isinstance(data, dict):
        if not data:
            return pad + "{}\n" if indent == 0 else "{}"
        for k, v in data.items():
            if isinstance(v, (dict, list)) and v:
                lines.append(f"{pad}{k}:")
                lines.append(_to_yaml(v, indent + 1))
            elif isinstance(v, dict):
                lines.append(f"{pad}{k}: {{}}")
            elif isinstance(v, list):
                lines.append(f"{pad}{k}: []")
            else:
                lines.append(f"{pad}{k}: {json.dumps(v)}")
        return "\n".join(lines)
    return pad + json.dumps(data)


def _to_toml(data):
    lines = []
    tables = []
    for k, v in data.items():
        if isinstance(v, dict):
            tables.append((k, v))
        else:
            lines.append(f"{k} = {json.dumps(v)}")
    for name, tbl in tables:
        lines.append("")
        lines.append(f"[{name}]")
        for k, v in tbl.items():
            lines.append(f"{k} = {json.dumps(v)}")
    return "\n".join(lines)


def cmd_export(args):
    path = _find_config()
    if not path:
        print("error: config.json not found in current directory", file=sys.stderr)
        return 2
    cfg = _load_config(path)
    if args.format == "json":
        print(json.dumps(cfg, indent=2))
    elif args.format == "yaml":
        print(_to_yaml(cfg))
    elif args.format == "toml":
        print(_to_toml(cfg))
    return 0


def cmd_validate(args):
    path = _find_config()
    if not path:
        print("error: config.json not found in current directory", file=sys.stderr)
        return 1
    try:
        cfg = _load_config(path)
    except json.JSONDecodeError as e:
        print(f"invalid JSON: {e}", file=sys.stderr)
        return 1
    errors = _validate(cfg)
    if errors:
        for e in errors:
            print(f"validation error: {e}", file=sys.stderr)
        return 1
    print("config is valid")
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="tool", description="Internal project config CLI.")
    sub = p.add_subparsers(dest="command", metavar="<subcommand>")

    p_init = sub.add_parser("init", help="Create a new project directory with default config.json.")
    p_init.add_argument("project_name", help="Name of the project directory to create.")
    p_init.set_defaults(func=cmd_init)

    p_add = sub.add_parser("add", help="Append a key/value pair to config.json.")
    p_add.add_argument("key", help="Config key.")
    p_add.add_argument("value", help="Config value.")
    p_add.set_defaults(func=cmd_add)

    p_list = sub.add_parser("list", help="Print all key/value pairs in config.json.")
    p_list.set_defaults(func=cmd_list)

    p_exp = sub.add_parser("export", help="Export config to stdout in given format.")
    p_exp.add_argument("--format", choices=["json", "yaml", "toml"], required=True, help="Output format.")
    p_exp.set_defaults(func=cmd_export)

    p_val = sub.add_parser("validate", help="Validate config.json against the built-in schema.")
    p_val.set_defaults(func=cmd_validate)

    return p


def main(argv=None):
    parser = build_parser()
    argv = sys.argv[1:] if argv is None else argv
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 2
        if code == 2:
            return 2
        return code
    if not getattr(args, "command", None):
        parser.print_help()
        return 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
```
