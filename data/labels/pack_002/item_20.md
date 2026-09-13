# item_20

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
`item_20`. Answer from the code alone; do not run the tools.

---

## The code

### `config.py`

```
"""Pipeline configuration."""
from pathlib import Path

BASE_DIR = Path(__file__).parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
QUARANTINE_FILE = OUTPUT_DIR / "quarantine.csv"
SUMMARY_FILE = OUTPUT_DIR / "run_summary.json"
DB_PATH = BASE_DIR / "data.db"
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

```
"""Data pipeline: ingest CSV -> validate -> normalise -> load SQLite -> summary."""
from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
import time
from pathlib import Path

from config import (
    DB_PATH,
    INPUT_DIR,
    OUTPUT_DIR,
    QUARANTINE_FILE,
    SCHEMA,
    SUMMARY_FILE,
    TABLE_NAME,
)

TYPE_CASTS = {
    "int": int,
    "float": float,
    "str": str,
}


def ingest_csv(path: Path):
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield row


def validate_row(row: dict) -> tuple[dict | None, str | None]:
    out = {}
    for col, typ in SCHEMA.items():
        if col not in row or row[col] is None or row[col] == "":
            return None, f"missing column: {col}"
        try:
            out[col] = TYPE_CASTS[typ](row[col])
        except (ValueError, TypeError):
            return None, f"invalid type for {col}: {row[col]!r}"
    return out, None


def normalise(row: dict) -> dict:
    out = {}
    for col, typ in SCHEMA.items():
        v = row[col]
        if typ == "str":
            out[col] = v.lower()
        elif typ == "float":
            out[col] = round(float(v), 2)
        else:
            out[col] = v
    return out


def row_hash(row: dict) -> str:
    payload = json.dumps(row, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def init_db(conn: sqlite3.Connection) -> None:
    cols_sql = ", ".join(
        f"{c} {'INTEGER' if t == 'int' else 'REAL' if t == 'float' else 'TEXT'}"
        for c, t in SCHEMA.items()
    )
    conn.execute(
        f"CREATE TABLE IF NOT EXISTS {TABLE_NAME} ("
        f"row_hash TEXT PRIMARY KEY, {cols_sql})"
    )
    conn.commit()


def load_rows(conn: sqlite3.Connection, rows: list[dict]) -> int:
    if not rows:
        return 0
    cols = list(SCHEMA.keys())
    placeholders = ", ".join(["?"] * (len(cols) + 1))
    col_list = ", ".join(["row_hash"] + cols)
    sql = (
        f"INSERT OR IGNORE INTO {TABLE_NAME} ({col_list}) VALUES ({placeholders})"
    )
    inserted = 0
    cur = conn.cursor()
    for r in rows:
        h = row_hash(r)
        cur.execute(sql, [h] + [r[c] for c in cols])
        inserted += cur.rowcount
    conn.commit()
    return inserted


def write_quarantine(bad: list[tuple[dict, str]]) -> None:
    if not bad:
        return
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({k for row, _ in bad for k in row.keys()} | {"_error"})
    with QUARANTINE_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row, err in bad:
            out = dict(row)
            out["_error"] = err
            writer.writerow(out)


def write_summary(summary: dict) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_FILE.write_text(json.dumps(summary, indent=2))


def run_pipeline(input_file: Path | None = None) -> dict:
    start = time.time()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    INPUT_DIR.mkdir(parents=True, exist_ok=True)

    if input_file is None:
        files = sorted(INPUT_DIR.glob("*.csv"))
        if not files:
            raise FileNotFoundError(f"no CSV files in {INPUT_DIR}")
        input_file = files[0]

    total = 0
    valid_rows: list[dict] = []
    bad: list[tuple[dict, str]] = []

    for raw in ingest_csv(input_file):
        total += 1
        validated, err = validate_row(raw)
        if validated is None:
            bad.append((raw, err or "invalid"))
        else:
            valid_rows.append(normalise(validated))

    write_quarantine(bad)

    conn = sqlite3.connect(DB_PATH)
    try:
        init_db(conn)
        inserted = load_rows(conn, valid_rows)
    finally:
        conn.close()

    summary = {
        "input_file": str(input_file),
        "rows_read": total,
        "rows_valid": len(valid_rows),
        "rows_quarantined": len(bad),
        "rows_inserted": inserted,
        "duration_seconds": round(time.time() - start, 3),
    }
    write_summary(summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(run_pipeline(), indent=2))
```

### `scheduler.py`

```
"""Daily scheduler entrypoint using APScheduler."""
from __future__ import annotations

import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from config import CRON_DAILY
from pipeline import run_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("scheduler")


def job() -> None:
    log.info("starting daily pipeline run")
    summary = run_pipeline()
    log.info("run complete: %s", summary)


def main() -> None:
    scheduler = BlockingScheduler()
    scheduler.add_job(job, CronTrigger.from_crontab(CRON_DAILY), id="daily_pipeline")
    log.info("scheduler started with cron %s", CRON_DAILY)
    scheduler.start()


if __name__ == "__main__":
    main()
```

### `test_pipeline.py`

```
"""Tests for the data pipeline."""
import csv
import json
import sqlite3
from pathlib import Path

import config
import pipeline


def _write_csv(path: Path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "name", "category", "amount"])
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _setup(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "INPUT_DIR", tmp_path / "in")
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr(config, "QUARANTINE_FILE", tmp_path / "out" / "q.csv")
    monkeypatch.setattr(config, "SUMMARY_FILE", tmp_path / "out" / "s.json")
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "data.db")
    monkeypatch.setattr(pipeline, "INPUT_DIR", tmp_path / "in")
    monkeypatch.setattr(pipeline, "OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr(pipeline, "QUARANTINE_FILE", tmp_path / "out" / "q.csv")
    monkeypatch.setattr(pipeline, "SUMMARY_FILE", tmp_path / "out" / "s.json")
    monkeypatch.setattr(pipeline, "DB_PATH", tmp_path / "data.db")
    (tmp_path / "in").mkdir()


def test_full_run(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    csv_path = tmp_path / "in" / "data.csv"
    _write_csv(csv_path, [
        {"id": "1", "name": "Alice", "category": "FOO", "amount": "1.239"},
        {"id": "2", "name": "Bob", "category": "BAR", "amount": "2.50"},
        {"id": "x", "name": "Bad", "category": "Z", "amount": "1.0"},
        {"id": "3", "name": "Carol", "category": "BAZ", "amount": "notanum"},
    ])
    summary = pipeline.run_pipeline()
    assert summary["rows_read"] == 4
    assert summary["rows_valid"] == 2
    assert summary["rows_quarantined"] == 2
    assert summary["rows_inserted"] == 2

    conn = sqlite3.connect(config.DB_PATH)
    rows = conn.execute(
        f"SELECT name, category, amount FROM {config.TABLE_NAME} ORDER BY id"
    ).fetchall()
    conn.close()
    assert rows == [("alice", "foo", 1.24), ("bob", "bar", 2.5)]

    s = json.loads(config.SUMMARY_FILE.read_text())
    assert s["rows_inserted"] == 2
    assert config.QUARANTINE_FILE.exists()


def test_idempotent(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    csv_path = tmp_path / "in" / "data.csv"
    _write_csv(csv_path, [
        {"id": "1", "name": "Alice", "category": "FOO", "amount": "1.23"},
    ])
    s1 = pipeline.run_pipeline()
    s2 = pipeline.run_pipeline()
    assert s1["rows_inserted"] == 1
    assert s2["rows_inserted"] == 0

    conn = sqlite3.connect(config.DB_PATH)
    count = conn.execute(f"SELECT COUNT(*) FROM {config.TABLE_NAME}").fetchone()[0]
    conn.close()
    assert count == 1


def test_normalise():
    out = pipeline.normalise({"id": 1, "name": "FoO", "category": "BAR", "amount": 1.239})
    assert out == {"id": 1, "name": "foo", "category": "bar", "amount": 1.24}
```
