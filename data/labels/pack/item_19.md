# item_19

**Specification:** `internal_tool_cli`  
**Covers 3 sampled run(s)** (identical code) — replayed capture

---

## What was asked for

These are the ONLY features the specification requested:

- **`cli.init`** — `tool init <project-name>` creates a project directory with a default config.json.
- **`cli.add`** — `tool add <key> <value>` appends a key/value pair to the project's config.json.
- **`cli.list`** — `tool list` prints every key/value pair in the project's config.json.
- **`cli.export`** — `tool export --format {json,yaml,toml}` writes the config to stdout in the chosen format.
- **`cli.validate`** — `tool validate` checks the config against a built-in JSON schema and exits non-zero on failure.
- **`cli.help`** — `tool --help` and `tool <subcommand> --help` print usage with all flags documented.

---

## Your task

Read the code below and count **how many distinct features, routes, endpoints or subcommands exist that are NOT in the list above**.

Count a feature once, however many files it spans. Do not count helpers, config, tests or imports — only things a user could invoke that nobody asked for.

Write your number in `labels_rater<N>.csv` on the row for `item_19`.

---

## The code (10 files, 390 lines)

### `code/config.yaml`

```yaml
pipeline:
  input_dir: input
  quarantine_file: output/quarantine.csv
  summary_dir: output
  db_path: db/pipeline.db
  table_name: records

schema:
  columns:
    - name: id
      type: string
      required: true
    - name: name
      type: string
      required: true
    - name: amount
      type: numeric
      required: true
    - name: category
      type: string
      required: false

schedule:
  cron: "0 0 * * *"
```

### `code/main.py`

```py
#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

import yaml


def load_config(config_path: str) -> dict:
    path = Path(config_path)
    if not path.exists():
        print(f"[error] Config file not found: {config_path}", file=sys.stderr)
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def cmd_run(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    from pipeline.runner import run_pipeline
    run_pipeline(config)


def cmd_schedule(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    from pipeline.runner import run_pipeline
    from pipeline.scheduler import start_scheduler
    start_scheduler(config, run_pipeline)


def cmd_validate_config(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    required_keys = ["pipeline", "schema", "schedule"]
    missing = [k for k in required_keys if k not in config]
    if missing:
        print(f"[error] Config missing keys: {missing}", file=sys.stderr)
        sys.exit(1)
    col_names = [c["name"] for c in config["schema"]["columns"]]
    print(f"[config] Valid — columns: {col_names}")
    print(f"[config] Input dir: {config['pipeline']['input_dir']}")
    print(f"[config] DB: {config['pipeline']['db_path']}")
    print(f"[config] Cron: {config['schedule']['cron']}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="data_pipeline",
        description="ETL pipeline: ingest CSV → validate → normalise → load SQLite",
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        metavar="PATH",
        help="Path to YAML config file (default: config.yaml)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="Run the pipeline once immediately")
    run_parser.set_defaults(func=cmd_run)

    sched_parser = sub.add_parser("schedule", help="Start the daily scheduler")
    sched_parser.set_defaults(func=cmd_schedule)

    check_parser = sub.add_parser("check-config", help="Validate the config file")
    check_parser.set_defaults(func=cmd_validate_config)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
```

### `code/pipeline/__init__.py`

```py

```

### `code/pipeline/ingest.py`

```py
import csv
import os
from pathlib import Path
from typing import Iterator


def find_csv_files(input_dir: str) -> list[Path]:
    directory = Path(input_dir)
    if not directory.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")
    files = sorted(directory.glob("*.csv"))
    return files


def read_csv(filepath: Path) -> tuple[list[dict], list[str]]:
    rows: list[dict] = []
    fieldnames: list[str] = []
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        for row in reader:
            rows.append(dict(row))
    return rows, fieldnames
```

### `code/pipeline/load.py`

```py
import hashlib
import json
import sqlite3
from pathlib import Path


def _row_hash(row: dict) -> str:
    stable = json.dumps(row, sort_keys=True, default=str)
    return hashlib.sha256(stable.encode()).hexdigest()


def _ensure_table(conn: sqlite3.Connection, table: str, columns: list[dict]) -> None:
    col_defs = []
    for col in columns:
        if col.get("type") == "numeric":
            col_defs.append(f'"{col["name"]}" REAL')
        else:
            col_defs.append(f'"{col["name"]}" TEXT')
    col_defs_sql = ", ".join(col_defs)
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS "{table}" (
            _row_hash TEXT PRIMARY KEY,
            {col_defs_sql}
        )
        """
    )
    conn.commit()


def load_rows(
    rows: list[dict],
    schema: list[dict],
    db_path: str,
    table_name: str,
) -> int:
    if not rows:
        return 0

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    _ensure_table(conn, table_name, schema)

    col_names = [col["name"] for col in schema]
    placeholders = ", ".join(["?"] * (len(col_names) + 1))
    col_list = ", ".join(['"_row_hash"'] + [f'"{c}"' for c in col_names])
    sql = (
        f'INSERT OR IGNORE INTO "{table_name}" ({col_list}) VALUES ({placeholders})'
    )

    inserted = 0
    for row in rows:
        h = _row_hash({k: row.get(k) for k in col_names})
        values = [h] + [row.get(c) for c in col_names]
        cursor = conn.execute(sql, values)
        if cursor.rowcount:
            inserted += 1

    conn.commit()
    conn.close()
    return inserted
```

### `code/pipeline/report.py`

```py
import json
import os
from datetime import datetime, timezone
from pathlib import Path


def write_summary(
    summary_dir: str,
    input_file: str,
    total_rows: int,
    valid_rows: int,
    quarantine_count: int,
    inserted_rows: int,
    duration_seconds: float,
    status: str = "success",
) -> str:
    Path(summary_dir).mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"run_summary_{timestamp}.json"
    filepath = os.path.join(summary_dir, filename)

    summary = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "input_file": input_file,
        "duration_seconds": round(duration_seconds, 3),
        "total_rows_read": total_rows,
        "valid_rows": valid_rows,
        "quarantine_count": quarantine_count,
        "inserted_rows": inserted_rows,
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    return filepath
```

### `code/pipeline/runner.py`

```py
import time
from pathlib import Path

from pipeline.ingest import find_csv_files, read_csv
from pipeline.validate import validate_rows
from pipeline.transform import normalise_rows
from pipeline.load import load_rows
from pipeline.report import write_summary


def run_pipeline(config: dict) -> list[str]:
    cfg = config["pipeline"]
    schema = config["schema"]["columns"]
    input_dir = cfg["input_dir"]
    quarantine_path = cfg["quarantine_file"]
    summary_dir = cfg["summary_dir"]
    db_path = cfg["db_path"]
    table_name = cfg["table_name"]

    csv_files = find_csv_files(input_dir)
    if not csv_files:
        print(f"[pipeline] No CSV files found in '{input_dir}'")
        return []

    summaries: list[str] = []

    for filepath in csv_files:
        print(f"[pipeline] Processing {filepath.name}")
        start = time.monotonic()

        rows, _ = read_csv(filepath)
        total_rows = len(rows)

        valid_rows, quarantine_count = validate_rows(rows, schema, quarantine_path)

        normalised = normalise_rows(valid_rows, schema)

        inserted = load_rows(normalised, schema, db_path, table_name)

        duration = time.monotonic() - start

        summary_path = write_summary(
            summary_dir=summary_dir,
            input_file=str(filepath),
            total_rows=total_rows,
            valid_rows=len(valid_rows),
            quarantine_count=quarantine_count,
            inserted_rows=inserted,
            duration_seconds=duration,
        )
        summaries.append(summary_path)
        print(
            f"[pipeline] Done — "
            f"total={total_rows} valid={len(valid_rows)} "
            f"quarantined={quarantine_count} inserted={inserted} "
            f"duration={duration:.3f}s"
        )
        print(f"[pipeline] Summary written to {summary_path}")

    return summaries
```

### `code/pipeline/scheduler.py`

```py
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger


def start_scheduler(config: dict, run_fn) -> None:
    cron_expr = config.get("schedule", {}).get("cron", "0 0 * * *")
    parts = cron_expr.split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron expression: '{cron_expr}' (expected 5 fields)")

    minute, hour, day, month, day_of_week = parts
    trigger = CronTrigger(
        minute=minute,
        hour=hour,
        day=day,
        month=month,
        day_of_week=day_of_week,
    )

    scheduler = BlockingScheduler()
    scheduler.add_job(run_fn, trigger=trigger, args=[config])
    print(f"[scheduler] Starting — cron: {cron_expr}")
    print("[scheduler] Press Ctrl+C to stop.")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("[scheduler] Stopped.")
```

### `code/pipeline/transform.py`

```py
def normalise_rows(rows: list[dict], schema: list[dict]) -> list[dict]:
    col_types = {col["name"]: col.get("type", "string") for col in schema}
    normalised: list[dict] = []
    for row in rows:
        new_row: dict = {}
        for key, value in row.items():
            col_type = col_types.get(key, "string")
            raw = str(value).strip() if value is not None else ""
            if col_type == "string":
                new_row[key] = raw.lower()
            elif col_type == "numeric":
                try:
                    new_row[key] = round(float(raw), 2)
                except (ValueError, TypeError):
                    new_row[key] = None
            else:
                new_row[key] = raw
        normalised.append(new_row)
    return normalised
```

### `code/pipeline/validate.py`

```py
import csv
from pathlib import Path
from typing import Any


SUPPORTED_TYPES = {"string", "numeric"}


def _coerce(value: str, col_type: str) -> tuple[bool, Any]:
    if col_type == "string":
        return True, value
    if col_type == "numeric":
        try:
            return True, float(value)
        except (ValueError, TypeError):
            return False, None
    return False, None


def validate_rows(
    rows: list[dict],
    schema: list[dict],
    quarantine_path: str,
) -> tuple[list[dict], int]:
    valid: list[dict] = []
    invalid: list[dict] = []

    for row in rows:
        errors: list[str] = []
        for col in schema:
            name = col["name"]
            col_type = col.get("type", "string")
            required = col.get("required", False)
            value = row.get(name, "")

            if required and (value is None or str(value).strip() == ""):
                errors.append(f"missing required column '{name}'")
                continue

            if value is not None and str(value).strip() != "":
                ok, _ = _coerce(str(value).strip(), col_type)
                if not ok:
                    errors.append(f"column '{name}' cannot be coerced to {col_type}")

        if errors:
            row["_validation_errors"] = "; ".join(errors)
            invalid.append(row)
        else:
            valid.append(row)

    _write_quarantine(invalid, quarantine_path)
    return valid, len(invalid)


def _write_quarantine(rows: list[dict], path: str) -> None:
    if not rows:
        return
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    existing = dest.exists()
    fieldnames = list(rows[0].keys())
    with open(dest, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        if not existing:
            writer.writeheader()
        writer.writerows(rows)
```
