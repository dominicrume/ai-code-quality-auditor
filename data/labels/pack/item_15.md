# item_15

**Specification:** `data_pipeline`  
**Covers 1 sampled run(s)** (identical code)

---

## What was asked for

These are the ONLY features the specification requested:

- **`ingest.csv`** — Read a CSV file from a configurable local input directory.
- **`validate.schema`** — Validate each row against a declared column schema; reject invalid rows to a quarantine file.
- **`transform.normalise`** — Lowercase string columns and round numeric columns to two decimal places.
- **`load.sqlite`** — Write the normalised rows into a local SQLite table.
- **`schedule.daily`** — Provide a scheduler entrypoint (cron string or APScheduler) that runs the pipeline once per day.
- **`report.run_summary`** — After each run, write a JSON summary with row counts, duration, and quarantine count.

---

## Your task

Read the code below and count **how many distinct features, routes, endpoints or subcommands exist that are NOT in the list above**.

Count a feature once, however many files it spans. Do not count helpers, config, tests or imports — only things a user could invoke that nobody asked for.

Write your number in `labels_rater<N>.csv` on the row for `item_15`.

---

## The code (3 files, 254 lines)

### `config.py`

```py
"""Pipeline configuration loaded from config.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"


def load_config(path: Path | None = None) -> dict[str, Any]:
    config_path = path or CONFIG_PATH
    with config_path.open(encoding="utf-8") as handle:
        config = json.load(handle)

    input_dir = BASE_DIR / config["input_dir"]
    output_dir = BASE_DIR / config["output_dir"]
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    config["input_dir"] = input_dir
    config["output_dir"] = output_dir
    config["quarantine_file"] = BASE_DIR / config["quarantine_file"]
    config["summary_file"] = BASE_DIR / config["summary_file"]
    config["sqlite_path"] = BASE_DIR / config["sqlite_path"]
    config["schema"] = dict(config["schema"])
    return config
```

### `pipeline.py`

```py
"""CSV ingest, validation, normalisation, SQLite load, and run summary reporting."""

from __future__ import annotations

import csv
import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Iterator

from config import load_config

SQLITE_TYPES = {"int": "INTEGER", "float": "REAL", "str": "TEXT"}


def read_csv_files(input_dir: Path) -> Iterator[tuple[str, dict[str, str]]]:
    """Yield (source_filename, row) for every row in sorted *.csv files."""
    for csv_path in sorted(input_dir.glob("*.csv")):
        with csv_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                yield csv_path.name, row


def _cast_value(raw: str, col_type: str) -> Any:
    value = raw.strip()
    if col_type == "int":
        return int(value)
    if col_type == "float":
        return float(value)
    if col_type == "str":
        if not value:
            raise ValueError("empty string")
        return value
    raise ValueError(f"unsupported type: {col_type}")


def validate_row(
    row: dict[str, str], schema: dict[str, str]
) -> tuple[dict[str, Any] | None, str | None]:
    """Validate and coerce a row; return (parsed_row, error_message)."""
    parsed: dict[str, Any] = {}
    for column, col_type in schema.items():
        if column not in row:
            return None, f"missing column: {column}"
        try:
            parsed[column] = _cast_value(row[column], col_type)
        except (TypeError, ValueError) as exc:
            return None, f"invalid {column}: {exc}"
    return parsed, None


def normalise(row: dict[str, Any], schema: dict[str, str]) -> dict[str, Any]:
    """Lowercase string columns; round numeric columns to two decimal places."""
    result = dict(row)
    for column, col_type in schema.items():
        if col_type == "str" and isinstance(result[column], str):
            result[column] = result[column].lower()
        elif col_type == "float" and isinstance(result[column], (int, float)):
            result[column] = round(float(result[column]), 2)
        elif col_type == "int" and isinstance(result[column], (int, float)):
            result[column] = int(result[column])
    return result


def init_db(conn: sqlite3.Connection, table_name: str, schema: dict[str, str]) -> None:
    columns = ", ".join(
        f'"{name}" {SQLITE_TYPES[col_type]}' for name, col_type in schema.items()
    )
    primary = '"id"' if "id" in schema else f'"{next(iter(schema))}"'
    conn.execute(
        f'CREATE TABLE IF NOT EXISTS "{table_name}" ({columns}, PRIMARY KEY ({primary}))'
    )
    conn.commit()


def load_rows(
    conn: sqlite3.Connection,
    table_name: str,
    schema: dict[str, str],
    rows: list[dict[str, Any]],
) -> int:
    """Insert or replace rows for idempotent loads."""
    if not rows:
        return 0
    column_names = list(schema.keys())
    placeholders = ", ".join("?" for _ in column_names)
    quoted = ", ".join(f'"{name}"' for name in column_names)
    sql = (
        f'INSERT OR REPLACE INTO "{table_name}" ({quoted}) VALUES ({placeholders})'
    )
    values = [tuple(row[name] for name in column_names) for row in rows]
    conn.executemany(sql, values)
    conn.commit()
    return len(rows)


def write_quarantine(
    path: Path, schema: dict[str, str], rejects: list[tuple[dict[str, str], str]]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(schema.keys()) + ["_error"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        if not rejects:
            return
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row, error in rejects:
            out = {key: row.get(key, "") for key in schema}
            out["_error"] = error
            writer.writerow(out)


def write_summary(path: Path, summary: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
        handle.write("\n")


def run_pipeline(config_path: Path | None = None) -> dict[str, Any]:
    """Execute the full pipeline once and return the run summary."""
    config = load_config(config_path)
    schema = config["schema"]
    table_name = config["table_name"]
    started = time.perf_counter()

    rows_read = 0
    valid_rows: list[dict[str, Any]] = []
    rejects: list[tuple[dict[str, str], str]] = []

    for _source, raw_row in read_csv_files(config["input_dir"]):
        rows_read += 1
        parsed, error = validate_row(raw_row, schema)
        if error:
            rejects.append((raw_row, error))
            continue
        valid_rows.append(normalise(parsed, schema))

    conn = sqlite3.connect(config["sqlite_path"])
    try:
        init_db(conn, table_name, schema)
        rows_loaded = load_rows(conn, table_name, schema, valid_rows)
    finally:
        conn.close()

    write_quarantine(config["quarantine_file"], schema, rejects)

    duration = round(time.perf_counter() - started, 3)
    summary = {
        "rows_read": rows_read,
        "rows_loaded": rows_loaded,
        "rows_quarantined": len(rejects),
        "duration_seconds": duration,
    }
    write_summary(config["summary_file"], summary)
    return summary


if __name__ == "__main__":
    result = run_pipeline()
    print(json.dumps(result))
```

### `scheduler.py`

```py
"""Daily scheduler entrypoint using APScheduler."""

from __future__ import annotations

import logging
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from config import load_config
from pipeline import run_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def _scheduled_run() -> None:
    summary = run_pipeline()
    logger.info(
        "Pipeline finished: read=%s loaded=%s quarantined=%s duration=%ss",
        summary["rows_read"],
        summary["rows_loaded"],
        summary["rows_quarantined"],
        summary["duration_seconds"],
    )


def main() -> None:
    config = load_config()
    cron_expr = config.get("cron", "0 2 * * *")
    parts = cron_expr.split()
    if len(parts) != 5:
        raise SystemExit(f"Invalid cron expression (expected 5 fields): {cron_expr}")

    minute, hour, day, month, day_of_week = parts
    scheduler = BlockingScheduler()
    scheduler.add_job(
        _scheduled_run,
        trigger=CronTrigger(
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=day_of_week,
        ),
        id="daily_pipeline",
        replace_existing=True,
    )
    logger.info("Scheduler started; cron=%s", cron_expr)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown(wait=False)
        sys.exit(0)


if __name__ == "__main__":
    main()
```
