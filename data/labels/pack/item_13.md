# item_13

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

Write your number in `labels_rater<N>.csv` on the row for `item_13`.

---

## The code (4 files, 235 lines)

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
```

### `pipeline.py`

```py
import csv
import json
import sqlite3
import time
import hashlib
from pathlib import Path
from datetime import datetime

from config import (
    INPUT_DIR,
    QUARANTINE_DIR,
    REPORT_DIR,
    DB_PATH,
    TABLE_NAME,
    SCHEMA,
)

TYPE_CASTERS = {
    "int": int,
    "float": float,
    "str": str,
}


def ingest_csv(input_dir: Path):
    rows = []
    for csv_path in sorted(Path(input_dir).glob("*.csv")):
        with open(csv_path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
    return rows


def validate_row(row, schema):
    cleaned = {}
    for col, type_name in schema.items():
        if col not in row or row[col] is None or row[col] == "":
            return None
        try:
            cleaned[col] = TYPE_CASTERS[type_name](row[col])
        except (ValueError, TypeError):
            return None
    return cleaned


def validate(rows, schema):
    valid, invalid = [], []
    for row in rows:
        cleaned = validate_row(row, schema)
        (valid if cleaned is not None else invalid).append(cleaned if cleaned else row)
    return valid, invalid


def normalise(rows, schema):
    out = []
    for row in rows:
        new_row = {}
        for col, type_name in schema.items():
            v = row[col]
            if type_name == "str":
                new_row[col] = v.lower()
            elif type_name == "float":
                new_row[col] = round(float(v), 2)
            else:
                new_row[col] = v
        out.append(new_row)
    return out


def _row_hash(row, schema):
    payload = "|".join(f"{c}={row[c]}" for c in schema)
    return hashlib.sha256(payload.encode()).hexdigest()


def load_sqlite(rows, db_path: Path, table: str, schema):
    sql_types = {"int": "INTEGER", "float": "REAL", "str": "TEXT"}
    cols_sql = ", ".join(f"{c} {sql_types[t]}" for c, t in schema.items())
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            f"CREATE TABLE IF NOT EXISTS {table} "
            f"(row_hash TEXT PRIMARY KEY, {cols_sql})"
        )
        inserted = 0
        for row in rows:
            h = _row_hash(row, schema)
            placeholders = ", ".join(["?"] * (len(schema) + 1))
            cols = "row_hash, " + ", ".join(schema)
            cur = conn.execute(
                f"INSERT OR IGNORE INTO {table} ({cols}) VALUES ({placeholders})",
                [h] + [row[c] for c in schema],
            )
            inserted += cur.rowcount
        conn.commit()
        return inserted
    finally:
        conn.close()


def write_quarantine(invalid_rows, quarantine_dir: Path):
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    if not invalid_rows:
        return None
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    path = quarantine_dir / f"quarantine_{ts}.csv"
    fieldnames = sorted({k for r in invalid_rows for k in r.keys()})
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in invalid_rows:
            writer.writerow(r)
    return str(path)


def write_report(summary, report_dir: Path):
    report_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    path = report_dir / f"run_{ts}.json"
    with open(path, "w") as f:
        json.dump(summary, f, indent=2)
    return str(path)


def run_pipeline():
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    start = time.time()
    raw = ingest_csv(INPUT_DIR)
    valid, invalid = validate(raw, SCHEMA)
    normalised = normalise(valid, SCHEMA)
    inserted = load_sqlite(normalised, DB_PATH, TABLE_NAME, SCHEMA)
    quarantine_path = write_quarantine(invalid, QUARANTINE_DIR)
    duration = time.time() - start
    summary = {
        "started_at": datetime.utcnow().isoformat(),
        "duration_seconds": round(duration, 3),
        "rows_ingested": len(raw),
        "rows_valid": len(valid),
        "rows_inserted": inserted,
        "rows_quarantined": len(invalid),
        "quarantine_file": quarantine_path,
    }
    report_path = write_report(summary, REPORT_DIR)
    summary["report_file"] = report_path
    return summary


if __name__ == "__main__":
    print(json.dumps(run_pipeline(), indent=2))
```

### `scheduler.py`

```py
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

### `test_pipeline.py`

```py
import csv
import json
import sqlite3
from pathlib import Path

import pipeline
from config import SCHEMA, TABLE_NAME


def _write_csv(path, rows, fieldnames):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def test_end_to_end(tmp_path, monkeypatch):
    input_dir = tmp_path / "input"
    quarantine_dir = tmp_path / "q"
    report_dir = tmp_path / "r"
    db_path = tmp_path / "db.sqlite"
    input_dir.mkdir()

    _write_csv(
        input_dir / "a.csv",
        [
            {"id": "1", "name": "Alice", "category": "FOO", "amount": "10.123"},
            {"id": "2", "name": "Bob", "category": "Bar", "amount": "5.5"},
            {"id": "x", "name": "Bad", "category": "X", "amount": "n/a"},
        ],
        ["id", "name", "category", "amount"],
    )

    monkeypatch.setattr(pipeline, "INPUT_DIR", input_dir)
    monkeypatch.setattr(pipeline, "QUARANTINE_DIR", quarantine_dir)
    monkeypatch.setattr(pipeline, "REPORT_DIR", report_dir)
    monkeypatch.setattr(pipeline, "DB_PATH", db_path)

    s1 = pipeline.run_pipeline()
    assert s1["rows_ingested"] == 3
    assert s1["rows_valid"] == 2
    assert s1["rows_inserted"] == 2
    assert s1["rows_quarantined"] == 1

    # idempotency
    s2 = pipeline.run_pipeline()
    assert s2["rows_inserted"] == 0

    conn = sqlite3.connect(db_path)
    rows = conn.execute(f"SELECT name, category, amount FROM {TABLE_NAME} ORDER BY name").fetchall()
    conn.close()
    assert rows == [("alice", "foo", 10.12), ("bob", "bar", 5.5)]

    assert Path(s1["report_file"]).exists()
    assert Path(s1["quarantine_file"]).exists()
```
