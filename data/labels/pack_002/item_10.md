# item_10

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
`item_10`. Answer from the code alone; do not run the tools.

---

## The code

### `config.py`

```
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
```

### `pipeline.py`

```
import csv
import json
import sqlite3
import time
from pathlib import Path

from config import (
    INPUT_DIR,
    OUTPUT_DIR,
    QUARANTINE_FILE,
    SUMMARY_FILE,
    DB_PATH,
    TABLE_NAME,
    SCHEMA,
)


def _coerce(value, type_name):
    if type_name == "int":
        return int(value)
    if type_name == "float":
        return float(value)
    if type_name == "str":
        if value is None:
            raise ValueError("null string")
        return str(value)
    raise ValueError(f"unknown type {type_name}")


def ingest_csv(path: Path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def validate_rows(rows):
    valid, invalid = [], []
    for row in rows:
        try:
            if set(row.keys()) < set(SCHEMA.keys()):
                raise ValueError("missing columns")
            typed = {col: _coerce(row[col], t) for col, t in SCHEMA.items()}
            valid.append(typed)
        except (ValueError, TypeError, KeyError) as e:
            invalid.append({**row, "_error": str(e)})
    return valid, invalid


def normalise(rows):
    out = []
    for row in rows:
        new_row = {}
        for col, t in SCHEMA.items():
            v = row[col]
            if t == "str":
                new_row[col] = v.lower()
            elif t == "float":
                new_row[col] = round(v, 2)
            else:
                new_row[col] = v
        out.append(new_row)
    return out


def _init_db(conn):
    cols_sql = ", ".join(
        f"{c} {'INTEGER PRIMARY KEY' if c == 'id' else ('REAL' if t == 'float' else ('INTEGER' if t == 'int' else 'TEXT'))}"
        for c, t in SCHEMA.items()
    )
    conn.execute(f"CREATE TABLE IF NOT EXISTS {TABLE_NAME} ({cols_sql})")


def load_sqlite(rows, db_path: Path = DB_PATH):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        _init_db(conn)
        cols = list(SCHEMA.keys())
        placeholders = ", ".join("?" for _ in cols)
        col_list = ", ".join(cols)
        sql = f"INSERT OR REPLACE INTO {TABLE_NAME} ({col_list}) VALUES ({placeholders})"
        conn.executemany(sql, [tuple(r[c] for c in cols) for r in rows])
        conn.commit()
    finally:
        conn.close()


def write_quarantine(invalid_rows, path: Path = QUARANTINE_FILE):
    if not invalid_rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({k for r in invalid_rows for k in r.keys()})
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(invalid_rows)


def write_summary(summary, path: Path = SUMMARY_FILE):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)


def run_pipeline(input_dir: Path = INPUT_DIR):
    start = time.time()
    input_dir = Path(input_dir)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    total_in = total_valid = total_invalid = 0
    all_invalid = []
    for csv_file in sorted(input_dir.glob("*.csv")):
        rows = ingest_csv(csv_file)
        total_in += len(rows)
        valid, invalid = validate_rows(rows)
        total_invalid += len(invalid)
        all_invalid.extend(invalid)
        normalised = normalise(valid)
        load_sqlite(normalised)
        total_valid += len(normalised)

    write_quarantine(all_invalid)
    summary = {
        "rows_read": total_in,
        "rows_loaded": total_valid,
        "rows_quarantined": total_invalid,
        "duration_seconds": round(time.time() - start, 4),
    }
    write_summary(summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(run_pipeline(), indent=2))
```

### `scheduler.py`

```
from apscheduler.schedulers.blocking import BlockingScheduler

from pipeline import run_pipeline

CRON_DAILY = "0 2 * * *"


def main():
    scheduler = BlockingScheduler()
    scheduler.add_job(run_pipeline, "cron", hour=2, minute=0, id="daily_pipeline")
    scheduler.start()


if __name__ == "__main__":
    main()
```
