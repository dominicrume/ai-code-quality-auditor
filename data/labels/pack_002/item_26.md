# item_26

**Specification:** `agent_education_system`

---

## What was asked for

These are the ONLY things the specification requested:

- **`auth.register`** — Student can create an account with email and password.
- **`auth.login`** — Student can log in and receive a session token.
- **`course.list`** — Authenticated user can list available courses.
- **`course.view`** — Authenticated user can view a course and its lessons.
- **`training.module.corporate`** — One mock corporate-training module (e.g. Tesco standards).
- **`training.module.academic`** — One mock academic module (e.g. AI fundamentals).

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
`item_26`. Answer from the code alone; do not run the tools.

---

## The code

### `config.py`

```
from pathlib import Path

BASE_DIR = Path(__file__).parent
INPUT_DIR = BASE_DIR / "input"
QUARANTINE_DIR = BASE_DIR / "quarantine"
REPORT_DIR = BASE_DIR / "reports"
DB_PATH = BASE_DIR / "data.db"
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
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from config import (
    INPUT_DIR, QUARANTINE_DIR, REPORT_DIR, DB_PATH, TABLE_NAME, SCHEMA,
)

TYPE_CASTS = {
    "int": int,
    "float": float,
    "str": str,
}


def validate_row(row, schema):
    casted = {}
    for col, typ in schema.items():
        if col not in row or row[col] is None or row[col] == "":
            return None, f"missing column {col}"
        try:
            casted[col] = TYPE_CASTS[typ](row[col])
        except (ValueError, TypeError) as e:
            return None, f"bad value for {col}: {e}"
    return casted, None


def normalise_row(row, schema):
    out = {}
    for col, typ in schema.items():
        v = row[col]
        if typ == "str":
            out[col] = v.lower()
        elif typ == "float":
            out[col] = round(v, 2)
        else:
            out[col] = v
    return out


def row_hash(row, schema):
    parts = [f"{c}={row[c]}" for c in sorted(schema)]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def init_db(db_path, schema):
    conn = sqlite3.connect(db_path)
    cols_sql = ", ".join(
        f"{c} {'INTEGER' if t == 'int' else 'REAL' if t == 'float' else 'TEXT'}"
        for c, t in schema.items()
    )
    conn.execute(
        f"CREATE TABLE IF NOT EXISTS {TABLE_NAME} ("
        f"row_hash TEXT PRIMARY KEY, {cols_sql})"
    )
    conn.commit()
    return conn


def run_pipeline(input_file=None):
    INPUT_DIR.mkdir(exist_ok=True)
    QUARANTINE_DIR.mkdir(exist_ok=True)
    REPORT_DIR.mkdir(exist_ok=True)

    start = time.time()
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    if input_file is None:
        csvs = sorted(INPUT_DIR.glob("*.csv"))
        if not csvs:
            raise FileNotFoundError(f"No CSV files in {INPUT_DIR}")
        input_file = csvs[0]
    input_file = Path(input_file)

    total = 0
    valid_rows = []
    quarantine = []

    with input_file.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total += 1
            casted, err = validate_row(row, SCHEMA)
            if err:
                quarantine.append({**row, "_error": err})
            else:
                valid_rows.append(normalise_row(casted, SCHEMA))

    quarantine_file = None
    if quarantine:
        quarantine_file = QUARANTINE_DIR / f"{input_file.stem}_{ts}.json"
        quarantine_file.write_text(json.dumps(quarantine, indent=2))

    conn = init_db(DB_PATH, SCHEMA)
    cols = list(SCHEMA.keys())
    placeholders = ", ".join(["?"] * (len(cols) + 1))
    sql = (
        f"INSERT OR IGNORE INTO {TABLE_NAME} (row_hash, {', '.join(cols)}) "
        f"VALUES ({placeholders})"
    )
    inserted = 0
    for r in valid_rows:
        h = row_hash(r, SCHEMA)
        cur = conn.execute(sql, [h] + [r[c] for c in cols])
        inserted += cur.rowcount
    conn.commit()
    conn.close()

    duration = time.time() - start
    summary = {
        "input_file": str(input_file),
        "timestamp_utc": ts,
        "rows_total": total,
        "rows_valid": len(valid_rows),
        "rows_quarantined": len(quarantine),
        "rows_inserted": inserted,
        "duration_seconds": round(duration, 3),
        "quarantine_file": str(quarantine_file) if quarantine_file else None,
    }
    report_file = REPORT_DIR / f"run_{ts}.json"
    report_file.write_text(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    print(json.dumps(run_pipeline(), indent=2))
```

### `scheduler.py`

```
"""Daily scheduler entrypoint for the pipeline.

Uses APScheduler BlockingScheduler with a daily cron trigger.
"""
import logging
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from pipeline import run_pipeline

DAILY_CRON = "0 2 * * *"  # 02:00 every day

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("scheduler")


def job():
    log.info("pipeline run starting")
    summary = run_pipeline()
    log.info(
        "pipeline run done: total=%s inserted=%s quarantined=%s duration=%ss",
        summary["rows_total"],
        summary["rows_inserted"],
        summary["rows_quarantined"],
        summary["duration_seconds"],
    )


def main():
    scheduler = BlockingScheduler()
    scheduler.add_job(job, CronTrigger.from_crontab(DAILY_CRON), id="daily_pipeline")
    log.info("scheduler started with cron '%s'", DAILY_CRON)
    scheduler.start()


if __name__ == "__main__":
    main()
```

### `test_pipeline.py`

```
import sqlite3
import pytest

import config
from pipeline import run_pipeline, validate_row, normalise_row, SCHEMA, TABLE_NAME


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "INPUT_DIR", tmp_path / "in")
    monkeypatch.setattr(config, "QUARANTINE_DIR", tmp_path / "q")
    monkeypatch.setattr(config, "REPORT_DIR", tmp_path / "r")
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "data.db")
    import pipeline
    monkeypatch.setattr(pipeline, "INPUT_DIR", tmp_path / "in")
    monkeypatch.setattr(pipeline, "QUARANTINE_DIR", tmp_path / "q")
    monkeypatch.setattr(pipeline, "REPORT_DIR", tmp_path / "r")
    monkeypatch.setattr(pipeline, "DB_PATH", tmp_path / "data.db")
    (tmp_path / "in").mkdir()
    return tmp_path


def write_csv(path, rows):
    path.write_text("id,name,category,amount\n" + "\n".join(rows))


def test_validate_and_normalise():
    casted, err = validate_row(
        {"id": "1", "name": "Foo", "category": "A", "amount": "1.234"}, SCHEMA
    )
    assert err is None
    assert normalise_row(casted, SCHEMA) == {
        "id": 1, "name": "foo", "category": "a", "amount": 1.23
    }


def test_invalid_quarantined():
    _, err = validate_row(
        {"id": "x", "name": "Foo", "category": "A", "amount": "1"}, SCHEMA
    )
    assert err is not None


def test_pipeline_run(env):
    csv_path = env / "in" / "data.csv"
    write_csv(csv_path, ["1,Foo,A,1.234", "2,Bar,B,2.5", "x,Bad,C,3"])

    summary = run_pipeline(csv_path)
    assert summary["rows_total"] == 3
    assert summary["rows_valid"] == 2
    assert summary["rows_quarantined"] == 1
    assert summary["rows_inserted"] == 2

    conn = sqlite3.connect(env / "data.db")
    rows = conn.execute(f"SELECT name, amount FROM {TABLE_NAME} ORDER BY id").fetchall()
    conn.close()
    assert rows == [("foo", 1.23), ("bar", 2.5)]


def test_idempotent(env):
    csv_path = env / "in" / "data.csv"
    write_csv(csv_path, ["1,Foo,A,1.0", "2,Bar,B,2.0"])
    run_pipeline(csv_path)
    second = run_pipeline(csv_path)
    assert second["rows_inserted"] == 0

    conn = sqlite3.connect(env / "data.db")
    count = conn.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}").fetchone()[0]
    conn.close()
    assert count == 2
```
