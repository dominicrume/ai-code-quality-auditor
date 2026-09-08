# item_14

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

Write your number in `labels_rater<N>.csv` on the row for `item_14`.

---

## The code (3 files, 243 lines)

### `config.py`

```py
"""Centralised configuration for the data pipeline."""

from pathlib import Path

BASE_DIR = Path(__file__).parent

INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
QUARANTINE_FILE = OUTPUT_DIR / "quarantine.csv"
SUMMARY_FILE = OUTPUT_DIR / "run_summary.json"
DB_PATH = OUTPUT_DIR / "pipeline.db"
TABLE_NAME = "records"

# Declared column schema: name -> expected Python type
SCHEMA = {
    "id": int,
    "name": str,
    "category": str,
    "amount": float,
}
```

### `pipeline.py`

```py
"""CSV-to-SQLite ETL pipeline."""

from __future__ import annotations

import csv
import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from config import (
    DB_PATH,
    INPUT_DIR,
    OUTPUT_DIR,
    QUARANTINE_FILE,
    SCHEMA,
    SUMMARY_FILE,
    TABLE_NAME,
)


def _coerce(value: str, expected_type: type) -> Any:
    """Coerce a raw CSV cell to the declared schema type."""
    if value is None or (isinstance(value, str) and value.strip() == ""):
        raise ValueError("empty value")
    if expected_type is int:
        return int(value)
    if expected_type is float:
        return float(value)
    if expected_type is str:
        return str(value)
    raise ValueError(f"unsupported type: {expected_type}")


def ingest_csv(input_dir: Path | None = None) -> list[dict[str, str]]:
    """Read all CSV files from the input directory."""
    directory = input_dir or INPUT_DIR
    rows: list[dict[str, str]] = []
    for csv_path in sorted(directory.glob("*.csv")):
        with csv_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            rows.extend(reader)
    return rows


def validate_rows(raw_rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Validate rows against SCHEMA; return valid and invalid rows."""
    valid: list[dict[str, Any]] = []
    invalid: list[dict[str, str]] = []

    for row in raw_rows:
        errors: list[str] = []
        coerced: dict[str, Any] = {}

        missing = [col for col in SCHEMA if col not in row]
        if missing:
            errors.append(f"missing columns: {', '.join(missing)}")
        else:
            for column, expected_type in SCHEMA.items():
                try:
                    coerced[column] = _coerce(row[column], expected_type)
                except (ValueError, TypeError) as exc:
                    errors.append(f"{column}: {exc}")

        if errors:
            quarantine_row = dict(row)
            quarantine_row["_error"] = "; ".join(errors)
            invalid.append(quarantine_row)
        else:
            valid.append(coerced)

    return valid, invalid


def normalise(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Lowercase string columns and round numeric columns to two decimal places."""
    normalised: list[dict[str, Any]] = []
    for row in rows:
        updated = dict(row)
        for column, expected_type in SCHEMA.items():
            value = updated[column]
            if expected_type is str and isinstance(value, str):
                updated[column] = value.lower()
            elif expected_type is float and isinstance(value, (int, float)):
                updated[column] = round(float(value), 2)
        normalised.append(updated)
    return normalised


def write_quarantine(invalid_rows: list[dict[str, str]]) -> None:
    """Write rejected rows to the quarantine file."""
    if not invalid_rows:
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = list(invalid_rows[0].keys())
    with QUARANTINE_FILE.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(invalid_rows)


def _ensure_table(connection: sqlite3.Connection) -> None:
    columns_sql = ", ".join(
        f"{name} {'INTEGER PRIMARY KEY' if name == 'id' else 'REAL' if dtype is float else 'TEXT'}"
        for name, dtype in SCHEMA.items()
    )
    connection.execute(f"CREATE TABLE IF NOT EXISTS {TABLE_NAME} ({columns_sql})")


def load_sqlite(rows: list[dict[str, Any]]) -> int:
    """Write normalised rows into SQLite using idempotent upserts."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    columns = list(SCHEMA.keys())
    placeholders = ", ".join("?" for _ in columns)
    column_names = ", ".join(columns)

    with sqlite3.connect(DB_PATH) as connection:
        _ensure_table(connection)
        connection.executemany(
            f"INSERT OR REPLACE INTO {TABLE_NAME} ({column_names}) VALUES ({placeholders})",
            [tuple(row[col] for col in columns) for row in rows],
        )
        connection.commit()

    return len(rows)


def write_run_summary(
    *,
    rows_read: int,
    rows_loaded: int,
    rows_quarantined: int,
    duration_seconds: float,
) -> dict[str, Any]:
    """Write a JSON run summary with counts and duration."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "rows_read": rows_read,
        "rows_loaded": rows_loaded,
        "rows_quarantined": rows_quarantined,
        "duration_seconds": round(duration_seconds, 3),
    }
    with SUMMARY_FILE.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
        handle.write("\n")
    return summary


def run_pipeline(input_dir: Path | None = None) -> dict[str, Any]:
    """Execute the full ingest-validate-transform-load pipeline."""
    start = time.perf_counter()

    raw_rows = ingest_csv(input_dir)
    valid_rows, invalid_rows = validate_rows(raw_rows)
    write_quarantine(invalid_rows)
    normalised_rows = normalise(valid_rows)
    rows_loaded = load_sqlite(normalised_rows)

    duration = time.perf_counter() - start
    return write_run_summary(
        rows_read=len(raw_rows),
        rows_loaded=rows_loaded,
        rows_quarantined=len(invalid_rows),
        duration_seconds=duration,
    )


if __name__ == "__main__":
    summary = run_pipeline()
    print(json.dumps(summary))
```

### `scheduler.py`

```py
"""Daily scheduler entrypoint for the data pipeline."""

from __future__ import annotations

import argparse
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from pipeline import run_pipeline

DEFAULT_CRON = "0 2 * * *"


def run_once() -> None:
    """Run the pipeline a single time."""
    run_pipeline()


def start_scheduler(cron: str = DEFAULT_CRON) -> None:
    """Start a blocking APScheduler that runs the pipeline on a cron schedule."""
    scheduler = BlockingScheduler()
    scheduler.add_job(run_once, CronTrigger.from_crontab(cron), id="daily_pipeline")
    scheduler.start()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Schedule the data pipeline")
    parser.add_argument(
        "--cron",
        default=DEFAULT_CRON,
        help="Cron expression for daily runs (default: 0 2 * * *)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run the pipeline once and exit",
    )
    args = parser.parse_args(argv)

    if args.once:
        run_once()
        return 0

    start_scheduler(args.cron)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```
