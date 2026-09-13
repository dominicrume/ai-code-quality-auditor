# item_01

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
`item_01`. Answer from the code alone; do not run the tools.

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

CONFIG_FILENAME = "config.json"

CONFIG_SCHEMA = {
    "type": "object",
    "additionalProperties": {"type": ["string", "number", "boolean", "null"]},
}


def find_config():
    path = os.path.join(os.getcwd(), CONFIG_FILENAME)
    if not os.path.isfile(path):
        print(f"error: {CONFIG_FILENAME} not found in current directory", file=sys.stderr)
        sys.exit(2)
    return path


def load_config(path):
    with open(path, "r") as f:
        return json.load(f)


def save_config(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def cmd_init(args):
    project_dir = os.path.join(os.getcwd(), args.project_name)
    if os.path.exists(project_dir):
        print(f"error: {args.project_name} already exists", file=sys.stderr)
        return 2
    os.makedirs(project_dir)
    save_config(os.path.join(project_dir, CONFIG_FILENAME), {})
    print(f"initialized project at {project_dir}")
    return 0


def cmd_add(args):
    path = find_config()
    data = load_config(path)
    data[args.key] = args.value
    save_config(path, data)
    return 0


def cmd_list(args):
    path = find_config()
    data = load_config(path)
    for k, v in data.items():
        print(f"{k}={v}")
    return 0


def to_yaml(data):
    lines = []
    for k, v in data.items():
        if isinstance(v, bool):
            sv = "true" if v else "false"
        elif v is None:
            sv = "null"
        elif isinstance(v, (int, float)):
            sv = str(v)
        else:
            sv = json.dumps(str(v))
        lines.append(f"{k}: {sv}")
    return "\n".join(lines) + ("\n" if lines else "")


def to_toml(data):
    lines = []
    for k, v in data.items():
        if isinstance(v, bool):
            sv = "true" if v else "false"
        elif v is None:
            continue
        elif isinstance(v, (int, float)):
            sv = str(v)
        else:
            sv = json.dumps(str(v))
        lines.append(f"{k} = {sv}")
    return "\n".join(lines) + ("\n" if lines else "")


def cmd_export(args):
    path = find_config()
    data = load_config(path)
    if args.format == "json":
        sys.stdout.write(json.dumps(data, indent=2) + "\n")
    elif args.format == "yaml":
        sys.stdout.write(to_yaml(data))
    elif args.format == "toml":
        sys.stdout.write(to_toml(data))
    return 0


def validate_data(data, schema):
    if schema.get("type") == "object" and not isinstance(data, dict):
        return False, "config must be an object"
    allowed = schema.get("additionalProperties", {}).get("type", [])
    for k, v in data.items():
        if not isinstance(k, str):
            return False, f"key {k!r} must be a string"
        if isinstance(v, bool):
            t = "boolean"
        elif isinstance(v, (int, float)):
            t = "number"
        elif isinstance(v, str):
            t = "string"
        elif v is None:
            t = "null"
        else:
            t = type(v).__name__
        if t not in allowed:
            return False, f"value for {k!r} has unsupported type {t}"
    return True, ""


def cmd_validate(args):
    path = find_config()
    try:
        data = load_config(path)
    except json.JSONDecodeError as e:
        print(f"validation failed: invalid JSON: {e}", file=sys.stderr)
        return 1
    ok, msg = validate_data(data, CONFIG_SCHEMA)
    if not ok:
        print(f"validation failed: {msg}", file=sys.stderr)
        return 1
    print("config is valid")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(prog="tool", description="Internal project config CLI.")
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    p_init = sub.add_parser("init", help="create a new project directory with default config.json")
    p_init.add_argument("project_name", help="name of the project directory to create")
    p_init.set_defaults(func=cmd_init)

    p_add = sub.add_parser("add", help="append a key/value pair to the project's config.json")
    p_add.add_argument("key", help="config key")
    p_add.add_argument("value", help="config value (string)")
    p_add.set_defaults(func=cmd_add)

    p_list = sub.add_parser("list", help="print every key/value pair in the project's config.json")
    p_list.set_defaults(func=cmd_list)

    p_export = sub.add_parser("export", help="write the config to stdout in the chosen format")
    p_export.add_argument("--format", choices=["json", "yaml", "toml"], required=True, help="output format")
    p_export.set_defaults(func=cmd_export)

    p_validate = sub.add_parser("validate", help="check the config against the built-in schema")
    p_validate.set_defaults(func=cmd_validate)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help(sys.stderr)
        return 2
    try:
        return args.func(args)
    except SystemExit:
        raise
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
```
