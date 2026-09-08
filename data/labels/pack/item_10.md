# item_10

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

Write your number in `labels_rater<N>.csv` on the row for `item_10`.

---

## The code (3 files, 166 lines)

### `config.py`

```py
from pathlib import Path

BASE_DIR = Path(__file__).parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
QUARANTINE_FILE = OUTPUT_DIR / "quarantine.csv"
SUMMARY_FILE = OUTPUT_DIR / "run_summary.json"
DB_PATH = OUTPUT_DIR / "pipeline.db"
TABLE_NAME = "records"

SCHEMA = {
    "id": "int",
    "name": "str",
    "category": "str",
    "amount": "float",
}

INPUT_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
```

### `pipeline.py`

```py
import csv
import json
import sqlite3
import time
from pathlib import Path

from config import (
    INPUT_DIR,
    QUARANTINE_FILE,
    SUMMARY_FILE,
    DB_PATH,
    TABLE_NAME,
    SCHEMA,
)


def read_csv(path: Path):
    with open(path, newline="") as f:
        yield from csv.DictReader(f)


def _coerce(value: str, kind: str):
    if kind == "int":
        return int(value)
    if kind == "float":
        return float(value)
    return str(value)


def validate_row(row: dict):
    out = {}
    for col, kind in SCHEMA.items():
        if col not in row or row[col] is None or row[col] == "":
            return None
        try:
            out[col] = _coerce(row[col], kind)
        except (ValueError, TypeError):
            return None
    return out


def normalise(row: dict):
    out = {}
    for col, kind in SCHEMA.items():
        v = row[col]
        if kind == "str":
            out[col] = v.lower()
        elif kind == "float":
            out[col] = round(v, 2)
        else:
            out[col] = v
    return out


def _sqlite_type(kind: str) -> str:
    return {"int": "INTEGER", "float": "REAL", "str": "TEXT"}[kind]


def init_db(conn):
    cols = ", ".join(
        f"{c} {_sqlite_type(k)}" + (" PRIMARY KEY" if c == "id" else "")
        for c, k in SCHEMA.items()
    )
    conn.execute(f"CREATE TABLE IF NOT EXISTS {TABLE_NAME} ({cols})")
    conn.commit()


def load_rows(conn, rows):
    cols = list(SCHEMA.keys())
    placeholders = ", ".join("?" for _ in cols)
    col_list = ", ".join(cols)
    sql = f"INSERT OR REPLACE INTO {TABLE_NAME} ({col_list}) VALUES ({placeholders})"
    inserted = 0
    for r in rows:
        conn.execute(sql, [r[c] for c in cols])
        inserted += 1
    conn.commit()
    return inserted


def write_quarantine(bad_rows):
    if not bad_rows:
        return
    fieldnames = sorted({k for r in bad_rows for k in r.keys()})
    with open(QUARANTINE_FILE, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in bad_rows:
            w.writerow(r)


def write_summary(summary: dict):
    with open(SUMMARY_FILE, "w") as f:
        json.dump(summary, f, indent=2)


def run_pipeline(input_dir: Path = INPUT_DIR):
    start = time.time()
    total = 0
    valid_rows = []
    bad_rows = []

    for csv_file in sorted(Path(input_dir).glob("*.csv")):
        for row in read_csv(csv_file):
            total += 1
            v = validate_row(row)
            if v is None:
                bad_rows.append(row)
            else:
                valid_rows.append(normalise(v))

    conn = sqlite3.connect(DB_PATH)
    try:
        init_db(conn)
        loaded = load_rows(conn, valid_rows)
    finally:
        conn.close()

    write_quarantine(bad_rows)

    summary = {
        "rows_read": total,
        "rows_loaded": loaded,
        "rows_quarantined": len(bad_rows),
        "duration_seconds": round(time.time() - start, 3),
    }
    write_summary(summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(run_pipeline(), indent=2))
```

### `scheduler.py`

```py
from apscheduler.schedulers.blocking import BlockingScheduler

from pipeline import run_pipeline

DAILY_CRON = "0 2 * * *"


def main():
    scheduler = BlockingScheduler()
    scheduler.add_job(run_pipeline, "cron", hour=2, minute=0, id="daily_pipeline")
    scheduler.start()


if __name__ == "__main__":
    main()
```
