# item_21

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
`item_21`. Answer from the code alone; do not run the tools.

---

## The code

### `config.py`

```
"""Runtime configuration for the data pipeline."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
QUARANTINE_PATH = OUTPUT_DIR / "quarantine.csv"
SUMMARY_PATH = OUTPUT_DIR / "run_summary.json"
SQLITE_PATH = OUTPUT_DIR / "pipeline.db"

TABLE_NAME = "records"

# Synthetic schema only — no real PII (governance: no_pii).
SCHEMA: dict[str, type] = {
    "id": int,
    "name": str,
    "category": str,
    "amount": float,
}

# Daily at 02:00 — used by scheduler entrypoint.
CRON_SCHEDULE = "0 2 * * *"

for directory in (INPUT_DIR, OUTPUT_DIR):
    directory.mkdir(parents=True, exist_ok=True)
```

### `pipeline.py`

```
"""CSV ingest → validate → normalise → SQLite load with run summary."""

from __future__ import annotations

import csv
import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Iterator

from config import (
    INPUT_DIR,
    QUARANTINE_PATH,
    SCHEMA,
    SQLITE_PATH,
    SUMMARY_PATH,
    TABLE_NAME,
)


def read_csv(input_dir: Path | None = None) -> Iterator[dict[str, str]]:
    """Read rows from all CSV files in the input directory."""
    directory = input_dir or INPUT_DIR
    for csv_path in sorted(directory.glob("*.csv")):
        with csv_path.open(newline="", encoding="utf-8") as handle:
            yield from csv.DictReader(handle)


def validate_row(row: dict[str, str]) -> tuple[dict[str, Any] | None, str | None]:
    """Validate and coerce a row against SCHEMA; return (row, error)."""
    coerced: dict[str, Any] = {}
    for column, expected_type in SCHEMA.items():
        raw = row.get(column)
        if raw is None or str(raw).strip() == "":
            return None, f"missing or empty column: {column}"
        try:
            if expected_type is int:
                coerced[column] = int(raw)
            elif expected_type is float:
                coerced[column] = float(raw)
            elif expected_type is str:
                coerced[column] = str(raw)
            else:
                return None, f"unsupported schema type for {column}"
        except (TypeError, ValueError):
            return None, f"invalid type for column: {column}"
    return coerced, None


def normalise(row: dict[str, Any]) -> dict[str, Any]:
    """Lowercase string columns; round float columns to two decimal places."""
    result: dict[str, Any] = {}
    for column, value in row.items():
        expected_type = SCHEMA[column]
        if expected_type is str and isinstance(value, str):
            result[column] = value.lower()
        elif expected_type is float and isinstance(value, (int, float)):
            result[column] = round(float(value), 2)
        else:
            result[column] = value
    return result


def _sqlite_type(py_type: type) -> str:
    if py_type is int:
        return "INTEGER"
    if py_type is float:
        return "REAL"
    return "TEXT"


def init_db(connection: sqlite3.Connection) -> None:
    columns = ", ".join(
        f'"{name}" {_sqlite_type(py_type)}' for name, py_type in SCHEMA.items()
    )
    connection.execute(
        f'CREATE TABLE IF NOT EXISTS "{TABLE_NAME}" ({columns}, '
        f'PRIMARY KEY ("id"))'
    )
    connection.commit()


def load_rows(connection: sqlite3.Connection, rows: list[dict[str, Any]]) -> int:
    """Insert or replace rows (idempotent by primary key id)."""
    if not rows:
        return 0
    column_names = list(SCHEMA.keys())
    placeholders = ", ".join("?" for _ in column_names)
    col_list = ", ".join(f'"{c}"' for c in column_names)
    sql = (
        f'INSERT OR REPLACE INTO "{TABLE_NAME}" ({col_list}) '
        f"VALUES ({placeholders})"
    )
    values = [tuple(row[c] for c in column_names) for row in rows]
    connection.executemany(sql, values)
    connection.commit()
    return len(rows)


def _write_quarantine(rows: list[dict[str, str]], errors: list[str]) -> int:
    if not rows:
        return 0
    fieldnames = list(SCHEMA.keys()) + ["_error"]
    with QUARANTINE_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row, error in zip(rows, errors, strict=True):
            writer.writerow({**row, "_error": error})
    return len(rows)


def run_pipeline(input_dir: Path | None = None) -> dict[str, Any]:
    """Execute the full pipeline and write a JSON run summary."""
    start = time.perf_counter()
    rows_read = 0
    valid_rows: list[dict[str, Any]] = []
    quarantine_rows: list[dict[str, str]] = []
    quarantine_errors: list[str] = []

    for raw_row in read_csv(input_dir):
        rows_read += 1
        coerced, error = validate_row(raw_row)
        if error:
            quarantine_rows.append(dict(raw_row))
            quarantine_errors.append(error)
            continue
        valid_rows.append(normalise(coerced))

    quarantined = _write_quarantine(quarantine_rows, quarantine_errors)

    with sqlite3.connect(SQLITE_PATH) as connection:
        init_db(connection)
        loaded = load_rows(connection, valid_rows)

    duration = round(time.perf_counter() - start, 3)
    summary = {
        "rows_read": rows_read,
        "rows_loaded": loaded,
        "rows_quarantined": quarantined,
        "duration_seconds": duration,
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    result = run_pipeline()
    print(json.dumps(result))
```

### `scheduler.py`

```
"""Daily scheduler entrypoint — runs the pipeline once per day via APScheduler."""

from __future__ import annotations

import logging
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from config import CRON_SCHEDULE
from pipeline import run_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def _parse_cron(cron_string: str) -> dict[str, str]:
    parts = cron_string.split()
    if len(parts) != 5:
        raise ValueError(
            f"CRON_SCHEDULE must have 5 fields (minute hour day month dow), got: {cron_string!r}"
        )
    minute, hour, day, month, day_of_week = parts
    return {
        "minute": minute,
        "hour": hour,
        "day": day,
        "month": month,
        "day_of_week": day_of_week,
    }


def main() -> None:
    cron_fields = _parse_cron(CRON_SCHEDULE)
    scheduler = BlockingScheduler()
    scheduler.add_job(
        run_pipeline,
        trigger=CronTrigger(**cron_fields),
        id="daily_pipeline",
        replace_existing=True,
    )
    logger.info("Scheduler started; cron=%s", CRON_SCHEDULE)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped")
        sys.exit(0)


if __name__ == "__main__":
    main()
```
