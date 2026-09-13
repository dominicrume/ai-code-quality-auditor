# item_09

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
`item_09`. Answer from the code alone; do not run the tools.

---

## The code

### `config.py`

```
from pathlib import Path

BASE_DIR = Path(__file__).parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
QUARANTINE_DIR = OUTPUT_DIR / "quarantine"
REPORTS_DIR = OUTPUT_DIR / "reports"
DB_PATH = OUTPUT_DIR / "pipeline.db"
TABLE_NAME = "records"

SCHEMA = {
    "id": "int",
    "name": "str",
    "email": "str",
    "amount": "float",
    "category": "str",
}

CRON_DAILY = "0 2 * * *"

for d in (INPUT_DIR, OUTPUT_DIR, QUARANTINE_DIR, REPORTS_DIR):
    d.mkdir(parents=True, exist_ok=True)
```

### `pipeline.py`

```
import csv
import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

from config import (
    DB_PATH,
    INPUT_DIR,
    QUARANTINE_DIR,
    REPORTS_DIR,
    SCHEMA,
    TABLE_NAME,
)


def read_csv(path: Path):
    with open(path, newline="", encoding="utf-8") as f:
        yield from csv.DictReader(f)


def _coerce(value: str, type_name: str):
    if value is None or value == "":
        raise ValueError("empty")
    if type_name == "int":
        return int(value)
    if type_name == "float":
        return float(value)
    return str(value)


def validate_row(row: dict):
    out = {}
    for col, type_name in SCHEMA.items():
        if col not in row:
            raise ValueError(f"missing column {col}")
        out[col] = _coerce(row[col], type_name)
    return out


def normalise(row: dict) -> dict:
    result = {}
    for col, type_name in SCHEMA.items():
        v = row[col]
        if type_name == "str":
            result[col] = v.lower()
        elif type_name == "float":
            result[col] = round(float(v), 2)
        else:
            result[col] = v
    return result


def _column_defs():
    type_map = {"int": "INTEGER", "float": "REAL", "str": "TEXT"}
    cols = [f"{c} {type_map[t]}" for c, t in SCHEMA.items()]
    pk = next(iter(SCHEMA))
    cols[0] = f"{pk} {type_map[SCHEMA[pk]]} PRIMARY KEY"
    return ", ".join(cols)


def init_db(conn):
    conn.execute(f"CREATE TABLE IF NOT EXISTS {TABLE_NAME} ({_column_defs()})")
    conn.commit()


def load_rows(conn, rows):
    cols = list(SCHEMA.keys())
    placeholders = ", ".join(["?"] * len(cols))
    col_list = ", ".join(cols)
    sql = f"INSERT OR REPLACE INTO {TABLE_NAME} ({col_list}) VALUES ({placeholders})"
    inserted = 0
    for r in rows:
        conn.execute(sql, [r[c] for c in cols])
        inserted += 1
    conn.commit()
    return inserted


def write_quarantine(path: Path, bad_rows):
    if not bad_rows:
        return 0
    fieldnames = sorted({k for r, _ in bad_rows for k in r.keys()} | {"_error"})
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r, err in bad_rows:
            row = dict(r)
            row["_error"] = err
            writer.writerow(row)
    return len(bad_rows)


def run(input_filename: str = "input.csv") -> dict:
    start = time.time()
    input_path = INPUT_DIR / input_filename
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    quarantine_path = QUARANTINE_DIR / f"quarantine_{ts}.csv"
    report_path = REPORTS_DIR / f"run_{ts}.json"

    total = 0
    valid_rows = []
    bad_rows = []
    for raw in read_csv(input_path):
        total += 1
        try:
            row = validate_row(raw)
            valid_rows.append(normalise(row))
        except (ValueError, KeyError) as e:
            bad_rows.append((raw, str(e)))

    conn = sqlite3.connect(DB_PATH)
    try:
        init_db(conn)
        loaded = load_rows(conn, valid_rows)
    finally:
        conn.close()

    quarantined = write_quarantine(quarantine_path, bad_rows)

    summary = {
        "input_file": str(input_path),
        "started_at": ts,
        "duration_seconds": round(time.time() - start, 3),
        "rows_read": total,
        "rows_loaded": loaded,
        "rows_quarantined": quarantined,
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    return summary


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
```

### `scheduler.py`

```
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from config import CRON_DAILY
from pipeline import run


def main():
    scheduler = BlockingScheduler()
    scheduler.add_job(run, CronTrigger.from_crontab(CRON_DAILY), id="daily_pipeline")
    scheduler.start()


if __name__ == "__main__":
    main()
```
