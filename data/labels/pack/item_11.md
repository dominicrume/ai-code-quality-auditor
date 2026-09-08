# item_11

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

Write your number in `labels_rater<N>.csv` on the row for `item_11`.

---

## The code (4 files, 234 lines)

### `config.py`

```py
from pathlib import Path

BASE_DIR = Path(__file__).parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
QUARANTINE_DIR = OUTPUT_DIR / "quarantine"
REPORT_DIR = OUTPUT_DIR / "reports"
DB_PATH = OUTPUT_DIR / "pipeline.db"
TABLE_NAME = "records"

SCHEMA = {
    "id": int,
    "name": str,
    "category": str,
    "amount": float,
}

PRIMARY_KEY = "id"

for d in (INPUT_DIR, OUTPUT_DIR, QUARANTINE_DIR, REPORT_DIR):
    d.mkdir(parents=True, exist_ok=True)
```

### `pipeline.py`

```py
import csv
import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

from config import (
    DB_PATH,
    INPUT_DIR,
    PRIMARY_KEY,
    QUARANTINE_DIR,
    REPORT_DIR,
    SCHEMA,
    TABLE_NAME,
)


def read_csv(path: Path):
    with path.open(newline="", encoding="utf-8") as f:
        yield from csv.DictReader(f)


def validate_row(row: dict):
    if set(row.keys()) != set(SCHEMA.keys()):
        return None, "column_mismatch"
    coerced = {}
    for col, typ in SCHEMA.items():
        val = row.get(col)
        if val is None or val == "":
            return None, f"missing:{col}"
        try:
            coerced[col] = typ(val)
        except (ValueError, TypeError):
            return None, f"type:{col}"
    return coerced, None


def normalise(row: dict):
    out = {}
    for col, typ in SCHEMA.items():
        v = row[col]
        if typ is str:
            out[col] = v.lower()
        elif typ is float:
            out[col] = round(float(v), 2)
        else:
            out[col] = v
    return out


def ensure_table(conn: sqlite3.Connection):
    cols = []
    sql_types = {int: "INTEGER", float: "REAL", str: "TEXT"}
    for col, typ in SCHEMA.items():
        decl = f"{col} {sql_types[typ]}"
        if col == PRIMARY_KEY:
            decl += " PRIMARY KEY"
        cols.append(decl)
    conn.execute(f"CREATE TABLE IF NOT EXISTS {TABLE_NAME} ({', '.join(cols)})")


def load_rows(conn: sqlite3.Connection, rows: list):
    if not rows:
        return 0
    cols = list(SCHEMA.keys())
    placeholders = ", ".join(["?"] * len(cols))
    sql = (
        f"INSERT OR REPLACE INTO {TABLE_NAME} ({', '.join(cols)}) "
        f"VALUES ({placeholders})"
    )
    conn.executemany(sql, [[r[c] for c in cols] for r in rows])
    conn.commit()
    return len(rows)


def write_quarantine(path: Path, bad_rows: list):
    if not bad_rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["reason", "raw"])
        for reason, raw in bad_rows:
            writer.writerow([reason, json.dumps(raw)])


def run_pipeline(input_file: str | None = None) -> dict:
    start = time.time()
    if input_file:
        input_path = Path(input_file)
    else:
        csvs = sorted(INPUT_DIR.glob("*.csv"))
        if not csvs:
            raise FileNotFoundError(f"No CSVs in {INPUT_DIR}")
        input_path = csvs[0]

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    valid, bad = [], []
    total = 0
    for row in read_csv(input_path):
        total += 1
        coerced, err = validate_row(row)
        if err:
            bad.append((err, row))
        else:
            valid.append(normalise(coerced))

    quarantine_path = QUARANTINE_DIR / f"{input_path.stem}_{ts}.csv"
    write_quarantine(quarantine_path, bad)

    with sqlite3.connect(DB_PATH) as conn:
        ensure_table(conn)
        loaded = load_rows(conn, valid)

    duration = round(time.time() - start, 3)
    summary = {
        "input_file": str(input_path),
        "started_at": ts,
        "duration_seconds": duration,
        "rows_read": total,
        "rows_loaded": loaded,
        "rows_quarantined": len(bad),
        "quarantine_file": str(quarantine_path) if bad else None,
    }
    report_path = REPORT_DIR / f"run_{ts}.json"
    report_path.write_text(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    import sys

    arg = sys.argv[1] if len(sys.argv) > 1 else None
    print(json.dumps(run_pipeline(arg), indent=2))
```

### `scheduler.py`

```py
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from pipeline import run_pipeline

DAILY_CRON = "0 2 * * *"


def main():
    scheduler = BlockingScheduler()
    scheduler.add_job(
        run_pipeline,
        trigger=CronTrigger.from_crontab(DAILY_CRON),
        id="daily_pipeline",
        replace_existing=True,
    )
    scheduler.start()


if __name__ == "__main__":
    main()
```

### `test_pipeline.py`

```py
import sqlite3
from pathlib import Path

import config
from pipeline import normalise, run_pipeline, validate_row


def write_csv(path: Path, rows: list[str]):
    path.write_text("\n".join(rows) + "\n")


def test_validate_and_normalise():
    row, err = validate_row({"id": "1", "name": "Foo", "category": "A", "amount": "1.234"})
    assert err is None
    norm = normalise(row)
    assert norm == {"id": 1, "name": "foo", "category": "a", "amount": 1.23}


def test_validate_rejects_bad():
    _, err = validate_row({"id": "x", "name": "n", "category": "c", "amount": "1"})
    assert err is not None


def test_pipeline_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "INPUT_DIR", tmp_path / "in")
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr(config, "QUARANTINE_DIR", tmp_path / "out" / "q")
    monkeypatch.setattr(config, "REPORT_DIR", tmp_path / "out" / "r")
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "out" / "p.db")
    import pipeline
    monkeypatch.setattr(pipeline, "INPUT_DIR", config.INPUT_DIR)
    monkeypatch.setattr(pipeline, "QUARANTINE_DIR", config.QUARANTINE_DIR)
    monkeypatch.setattr(pipeline, "REPORT_DIR", config.REPORT_DIR)
    monkeypatch.setattr(pipeline, "DB_PATH", config.DB_PATH)
    for d in (config.INPUT_DIR, config.QUARANTINE_DIR, config.REPORT_DIR):
        d.mkdir(parents=True, exist_ok=True)

    csv_path = config.INPUT_DIR / "data.csv"
    write_csv(csv_path, [
        "id,name,category,amount",
        "1,Alpha,X,10.005",
        "2,Beta,Y,20.5",
        "bad,row,Z,nope",
    ])

    s1 = run_pipeline(str(csv_path))
    assert s1["rows_read"] == 3
    assert s1["rows_loaded"] == 2
    assert s1["rows_quarantined"] == 1

    s2 = run_pipeline(str(csv_path))
    assert s2["rows_loaded"] == 2

    with sqlite3.connect(config.DB_PATH) as conn:
        count = conn.execute(f"SELECT COUNT(*) FROM {config.TABLE_NAME}").fetchone()[0]
        assert count == 2
        amt = conn.execute("SELECT amount FROM records WHERE id=1").fetchone()[0]
        assert amt == 10.01
```
