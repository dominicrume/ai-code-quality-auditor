# item_17

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
`item_17`. Answer from the code alone; do not run the tools.

---

## The code

### `config.py`

```
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

```
import csv
import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

from config import (
    INPUT_DIR,
    QUARANTINE_DIR,
    REPORT_DIR,
    DB_PATH,
    TABLE_NAME,
    SCHEMA,
)


def _coerce(value: str, type_name: str):
    if type_name == "int":
        return int(value)
    if type_name == "float":
        return float(value)
    if type_name == "str":
        if value is None:
            raise ValueError("null string")
        return str(value)
    raise ValueError(f"unknown type {type_name}")


def read_csv(path: Path):
    with open(path, newline="", encoding="utf-8") as f:
        yield from csv.DictReader(f)


def validate_row(row, schema):
    parsed = {}
    for col, type_name in schema.items():
        if col not in row or row[col] is None or row[col] == "":
            raise ValueError(f"missing column {col}")
        parsed[col] = _coerce(row[col], type_name)
    return parsed


def normalise_row(row, schema):
    out = {}
    for col, type_name in schema.items():
        v = row[col]
        if type_name == "str":
            out[col] = v.lower()
        elif type_name == "float":
            out[col] = round(float(v), 2)
        else:
            out[col] = v
    return out


def _columns_ddl(schema):
    type_map = {"int": "INTEGER", "float": "REAL", "str": "TEXT"}
    cols = []
    for col, t in schema.items():
        sql_type = type_map[t]
        if col == "id":
            cols.append(f"{col} {sql_type} PRIMARY KEY")
        else:
            cols.append(f"{col} {sql_type}")
    return ", ".join(cols)


def init_db(db_path=DB_PATH, schema=SCHEMA, table=TABLE_NAME):
    conn = sqlite3.connect(db_path)
    conn.execute(f"CREATE TABLE IF NOT EXISTS {table} ({_columns_ddl(schema)})")
    conn.commit()
    return conn


def load_rows(conn, rows, schema=SCHEMA, table=TABLE_NAME):
    cols = list(schema.keys())
    placeholders = ", ".join(["?"] * len(cols))
    col_list = ", ".join(cols)
    sql = f"INSERT OR REPLACE INTO {table} ({col_list}) VALUES ({placeholders})"
    inserted = 0
    for r in rows:
        conn.execute(sql, [r[c] for c in cols])
        inserted += 1
    conn.commit()
    return inserted


def write_quarantine(path: Path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames + ["_error"])
        writer.writeheader()
        for row, err in rows:
            out = {k: row.get(k, "") for k in fieldnames}
            out["_error"] = err
            writer.writerow(out)


def run_pipeline(input_dir=INPUT_DIR, db_path=DB_PATH, schema=SCHEMA):
    start = time.time()
    input_dir = Path(input_dir)
    QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    total = 0
    valid_rows = []
    bad_rows = []
    fieldnames = list(schema.keys())

    csv_files = sorted(input_dir.glob("*.csv"))
    for csv_file in csv_files:
        for row in read_csv(csv_file):
            total += 1
            try:
                v = validate_row(row, schema)
                valid_rows.append(normalise_row(v, schema))
            except (ValueError, KeyError) as e:
                bad_rows.append((row, str(e)))

    conn = init_db(db_path, schema)
    try:
        loaded = load_rows(conn, valid_rows, schema)
    finally:
        conn.close()

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if bad_rows:
        write_quarantine(QUARANTINE_DIR / f"quarantine_{ts}.csv", bad_rows, fieldnames)

    duration = time.time() - start
    summary = {
        "run_at": ts,
        "files": [str(p.name) for p in csv_files],
        "rows_read": total,
        "rows_loaded": loaded,
        "rows_quarantined": len(bad_rows),
        "duration_seconds": round(duration, 3),
    }
    report_path = REPORT_DIR / f"run_{ts}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    return summary


if __name__ == "__main__":
    print(json.dumps(run_pipeline(), indent=2))
```

### `scheduler.py`

```
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

### `test_pipeline.py`

```
import sqlite3
from pathlib import Path

from pipeline import run_pipeline
from config import SCHEMA, TABLE_NAME


def _write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = ["id", "name", "category", "amount"]
    with open(path, "w", encoding="utf-8") as f:
        f.write(",".join(cols) + "\n")
        for r in rows:
            f.write(",".join(str(r[c]) for c in cols) + "\n")


def test_pipeline(tmp_path):
    input_dir = tmp_path / "input"
    db_path = tmp_path / "data.sqlite"
    _write_csv(input_dir / "a.csv", [
        {"id": 1, "name": "Alice", "category": "A", "amount": "10.126"},
        {"id": 2, "name": "Bob", "category": "B", "amount": "not_a_number"},
        {"id": 3, "name": "Carol", "category": "C", "amount": "5"},
    ])

    s1 = run_pipeline(input_dir=input_dir, db_path=db_path, schema=SCHEMA)
    assert s1["rows_read"] == 3
    assert s1["rows_loaded"] == 2
    assert s1["rows_quarantined"] == 1

    conn = sqlite3.connect(db_path)
    rows = list(conn.execute(f"SELECT id, name, category, amount FROM {TABLE_NAME} ORDER BY id"))
    conn.close()
    assert rows == [(1, "alice", "a", 10.13), (3, "carol", "c", 5.0)]

    # idempotency
    s2 = run_pipeline(input_dir=input_dir, db_path=db_path, schema=SCHEMA)
    conn = sqlite3.connect(db_path)
    count = conn.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}").fetchone()[0]
    conn.close()
    assert count == 2
    assert s2["rows_loaded"] == 2
```
