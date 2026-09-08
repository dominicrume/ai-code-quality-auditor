# item_12

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

Write your number in `labels_rater<N>.csv` on the row for `item_12`.

---

## The code (3 files, 172 lines)

### `config.py`

```py
from pathlib import Path

BASE_DIR = Path(__file__).parent
INPUT_DIR = BASE_DIR / "input"
QUARANTINE_DIR = BASE_DIR / "quarantine"
REPORT_DIR = BASE_DIR / "reports"
DB_PATH = BASE_DIR / "data.sqlite"
TABLE_NAME = "records"

SCHEMA = {
    "id": "int",
    "name": "str",
    "category": "str",
    "amount": "float",
}

CRON_DAILY = "0 2 * * *"
```

### `pipeline.py`

```py
import csv
import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path

from config import (
    INPUT_DIR,
    QUARANTINE_DIR,
    REPORT_DIR,
    DB_PATH,
    TABLE_NAME,
    SCHEMA,
)


def _coerce(value, kind):
    if kind == "int":
        return int(value)
    if kind == "float":
        return float(value)
    if kind == "str":
        if value is None:
            raise ValueError("missing")
        s = str(value)
        if s == "":
            raise ValueError("empty")
        return s
    raise ValueError(f"unknown kind {kind}")


def validate_row(row):
    cleaned = {}
    for col, kind in SCHEMA.items():
        if col not in row:
            raise ValueError(f"missing column {col}")
        cleaned[col] = _coerce(row[col], kind)
    return cleaned


def normalise_row(row):
    out = {}
    for col, kind in SCHEMA.items():
        v = row[col]
        if kind == "str":
            out[col] = v.lower()
        elif kind == "float":
            out[col] = round(float(v), 2)
        else:
            out[col] = v
    return out


def ensure_table(conn):
    cols = []
    for col, kind in SCHEMA.items():
        sql_type = {"int": "INTEGER", "float": "REAL", "str": "TEXT"}[kind]
        pk = " PRIMARY KEY" if col == "id" else ""
        cols.append(f"{col} {sql_type}{pk}")
    conn.execute(f"CREATE TABLE IF NOT EXISTS {TABLE_NAME} ({', '.join(cols)})")
    conn.commit()


def load_rows(conn, rows):
    if not rows:
        return 0
    cols = list(SCHEMA.keys())
    placeholders = ",".join(["?"] * len(cols))
    sql = f"INSERT OR REPLACE INTO {TABLE_NAME} ({','.join(cols)}) VALUES ({placeholders})"
    conn.executemany(sql, [[r[c] for c in cols] for r in rows])
    conn.commit()
    return len(rows)


def run_pipeline(input_filename):
    INPUT_DIR.mkdir(exist_ok=True)
    QUARANTINE_DIR.mkdir(exist_ok=True)
    REPORT_DIR.mkdir(exist_ok=True)

    start = time.time()
    input_path = INPUT_DIR / input_filename

    valid_rows = []
    quarantined = []

    with open(input_path, newline="") as f:
        reader = csv.DictReader(f)
        total = 0
        for raw in reader:
            total += 1
            try:
                cleaned = validate_row(raw)
                valid_rows.append(normalise_row(cleaned))
            except (ValueError, KeyError, TypeError) as e:
                quarantined.append({**raw, "_error": str(e)})

    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    if quarantined:
        qpath = QUARANTINE_DIR / f"{Path(input_filename).stem}_{ts}.csv"
        fieldnames = list(quarantined[0].keys())
        with open(qpath, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(quarantined)

    conn = sqlite3.connect(DB_PATH)
    try:
        ensure_table(conn)
        loaded = load_rows(conn, valid_rows)
    finally:
        conn.close()

    duration = round(time.time() - start, 3)
    summary = {
        "input_file": str(input_path),
        "timestamp_utc": ts,
        "rows_read": total,
        "rows_loaded": loaded,
        "rows_quarantined": len(quarantined),
        "duration_seconds": duration,
    }
    report_path = REPORT_DIR / f"run_{ts}.json"
    with open(report_path, "w") as f:
        json.dump(summary, f, indent=2)
    return summary


if __name__ == "__main__":
    import sys
    fn = sys.argv[1] if len(sys.argv) > 1 else "input.csv"
    print(json.dumps(run_pipeline(fn), indent=2))
```

### `scheduler.py`

```py
import sys

from config import CRON_DAILY
from pipeline import run_pipeline


def start(input_filename="input.csv", cron=CRON_DAILY):
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger

    sched = BlockingScheduler()
    sched.add_job(
        run_pipeline,
        CronTrigger.from_crontab(cron),
        args=[input_filename],
        id="daily_pipeline",
    )
    sched.start()


if __name__ == "__main__":
    fn = sys.argv[1] if len(sys.argv) > 1 else "input.csv"
    start(fn)
```
