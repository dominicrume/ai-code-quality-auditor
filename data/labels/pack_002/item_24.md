# item_24

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
`item_24`. Answer from the code alone; do not run the tools.

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

SCHEMA = {
    "type": "object",
    "required": ["name", "settings"],
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "settings": {"type": "object"},
    },
}


def find_config():
    path = os.path.join(os.getcwd(), CONFIG_FILENAME)
    if not os.path.isfile(path):
        sys.stderr.write(f"error: {CONFIG_FILENAME} not found in current directory\n")
        sys.exit(2)
    return path


def load_config(path):
    with open(path, "r") as f:
        return json.load(f)


def save_config(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def validate_against_schema(data, schema):
    errors = []
    if schema.get("type") == "object":
        if not isinstance(data, dict):
            errors.append("root must be an object")
            return errors
        for key in schema.get("required", []):
            if key not in data:
                errors.append(f"missing required key: {key}")
        for key, subschema in schema.get("properties", {}).items():
            if key in data:
                t = subschema.get("type")
                v = data[key]
                if t == "string" and not isinstance(v, str):
                    errors.append(f"{key} must be a string")
                elif t == "string" and "minLength" in subschema and len(v) < subschema["minLength"]:
                    errors.append(f"{key} too short")
                elif t == "object" and not isinstance(v, dict):
                    errors.append(f"{key} must be an object")
    return errors


def cmd_init(args):
    project_dir = os.path.join(os.getcwd(), args.project_name)
    if os.path.exists(project_dir):
        sys.stderr.write(f"error: {project_dir} already exists\n")
        sys.exit(2)
    os.makedirs(project_dir)
    default = {"name": args.project_name, "settings": {}}
    save_config(os.path.join(project_dir, CONFIG_FILENAME), default)
    print(f"Initialized project at {project_dir}")
    return 0


def cmd_add(args):
    path = find_config()
    data = load_config(path)
    data.setdefault("settings", {})[args.key] = args.value
    save_config(path, data)
    print(f"Added {args.key}={args.value}")
    return 0


def cmd_list(args):
    path = find_config()
    data = load_config(path)
    settings = data.get("settings", {})
    for k, v in settings.items():
        print(f"{k}={v}")
    return 0


def to_yaml(data, indent=0):
    lines = []
    pad = "  " * indent
    if isinstance(data, dict):
        if not data:
            return pad + "{}\n"
        for k, v in data.items():
            if isinstance(v, (dict, list)) and v:
                lines.append(f"{pad}{k}:\n{to_yaml(v, indent + 1)}")
            else:
                lines.append(f"{pad}{k}: {to_yaml_scalar(v)}\n")
    elif isinstance(data, list):
        if not data:
            return pad + "[]\n"
        for item in data:
            lines.append(f"{pad}- {to_yaml_scalar(item)}\n")
    return "".join(lines)


def to_yaml_scalar(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None:
        return "null"
    if isinstance(v, (int, float)):
        return str(v)
    return str(v)


def to_toml(data):
    lines = []
    tables = {}
    for k, v in data.items():
        if isinstance(v, dict):
            tables[k] = v
        else:
            lines.append(f"{k} = {toml_value(v)}")
    for tname, tval in tables.items():
        lines.append("")
        lines.append(f"[{tname}]")
        for k, v in tval.items():
            lines.append(f"{k} = {toml_value(v)}")
    return "\n".join(lines) + "\n"


def toml_value(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, list):
        return "[" + ", ".join(toml_value(x) for x in v) + "]"
    return json.dumps(str(v))


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


def cmd_validate(args):
    path = find_config()
    try:
        data = load_config(path)
    except json.JSONDecodeError as e:
        sys.stderr.write(f"invalid JSON: {e}\n")
        return 1
    errors = validate_against_schema(data, SCHEMA)
    if errors:
        for e in errors:
            sys.stderr.write(f"validation error: {e}\n")
        return 1
    print("config is valid")
    return 0


class ArgParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write(f"error: {message}\n")
        sys.exit(2)


def build_parser():
    p = ArgParser(prog="tool", description="Internal tool CLI for project configs.")
    sub = p.add_subparsers(dest="command", metavar="<subcommand>")

    pi = sub.add_parser("init", help="Create a new project with default config.json")
    pi.add_argument("project_name", help="Name of the project directory to create")
    pi.set_defaults(func=cmd_init)

    pa = sub.add_parser("add", help="Append a key/value pair to config.json")
    pa.add_argument("key", help="Config key")
    pa.add_argument("value", help="Config value")
    pa.set_defaults(func=cmd_add)

    pl = sub.add_parser("list", help="Print every key/value pair from config.json")
    pl.set_defaults(func=cmd_list)

    pe = sub.add_parser("export", help="Write config to stdout in the chosen format")
    pe.add_argument("--format", required=True, choices=["json", "yaml", "toml"], help="Output format")
    pe.set_defaults(func=cmd_export)

    pv = sub.add_parser("validate", help="Validate config.json against the built-in schema")
    pv.set_defaults(func=cmd_validate)

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
```
