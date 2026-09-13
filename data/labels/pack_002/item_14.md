# item_14

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
`item_14`. Answer from the code alone; do not run the tools.

---

## The code

### `cli.py`

```
"""CLI entrypoint for running the data pipeline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from data_pipeline.pipeline import run_pipeline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the data pipeline once.")
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to pipeline configuration file (default: config.yaml)",
    )
    args = parser.parse_args(argv)

    result = run_pipeline(Path(args.config))
    print(f"Pipeline complete. Summary written to {result.summary_path}")
    print(
        f"rows_read={result.summary.rows_read} "
        f"rows_valid={result.summary.rows_valid} "
        f"rows_loaded={result.summary.rows_loaded} "
        f"quarantine_count={result.summary.quarantine_count} "
        f"duration_seconds={result.summary.duration_seconds}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### `config.yaml`

```
input_dir: data/input
quarantine_dir: data/quarantine
output_dir: data/output
sqlite_path: data/pipeline.db
table_name: records
schema_path: schema/default_schema.json
```

### `data_pipeline/__init__.py`

```
"""Data pipeline: ingest, validate, transform, load, and report."""

__version__ = "1.0.0"
```

### `data_pipeline/config.py`

```
"""Load pipeline configuration from YAML."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class PipelineConfig:
    input_dir: Path
    quarantine_dir: Path
    output_dir: Path
    sqlite_path: Path
    table_name: str
    schema_path: Path


@dataclass(frozen=True)
class ColumnSpec:
    type: str
    required: bool


@dataclass(frozen=True)
class SchemaConfig:
    columns: dict[str, ColumnSpec]
    primary_key: str


def load_config(config_path: Path | str = "config.yaml") -> PipelineConfig:
    path = Path(config_path)
    with path.open(encoding="utf-8") as f:
        raw: dict[str, Any] = yaml.safe_load(f)

    return PipelineConfig(
        input_dir=Path(raw["input_dir"]),
        quarantine_dir=Path(raw["quarantine_dir"]),
        output_dir=Path(raw["output_dir"]),
        sqlite_path=Path(raw["sqlite_path"]),
        table_name=raw["table_name"],
        schema_path=Path(raw["schema_path"]),
    )


def load_schema(schema_path: Path) -> SchemaConfig:
    with schema_path.open(encoding="utf-8") as f:
        raw = json.load(f)

    columns = {
        name: ColumnSpec(type=spec["type"], required=spec.get("required", False))
        for name, spec in raw["columns"].items()
    }
    return SchemaConfig(columns=columns, primary_key=raw["primary_key"])
```

### `data_pipeline/ingest.py`

```
"""Read CSV files from the configured input directory."""

from __future__ import annotations

import csv
from pathlib import Path


def discover_csv_files(input_dir: Path) -> list[Path]:
    if not input_dir.exists():
        return []
    return sorted(input_dir.glob("*.csv"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [dict(row) for row in reader]
```

### `data_pipeline/load.py`

```
"""Load normalised rows into SQLite with idempotent upserts."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from data_pipeline.config import SchemaConfig


def _column_sql_type(col_type: str) -> str:
    if col_type == "integer":
        return "INTEGER"
    if col_type == "number":
        return "REAL"
    return "TEXT"


def ensure_table(conn: sqlite3.Connection, schema: SchemaConfig, table_name: str) -> None:
    parts = []
    for name, spec in schema.columns.items():
        sql_type = _column_sql_type(spec.type)
        if name == schema.primary_key:
            parts.append(f'"{name}" {sql_type} PRIMARY KEY')
        else:
            parts.append(f'"{name}" {sql_type}')

    ddl = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({", ".join(parts)})'
    conn.execute(ddl)
    conn.commit()


def upsert_rows(
    db_path: Path,
    table_name: str,
    schema: SchemaConfig,
    rows: list[dict[str, object]],
) -> int:
    if not rows:
        return 0

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        ensure_table(conn, schema, table_name)
        columns = list(schema.columns.keys())
        placeholders = ", ".join("?" for _ in columns)
        col_names = ", ".join(f'"{c}"' for c in columns)
        update_cols = [c for c in columns if c != schema.primary_key]
        update_clause = ", ".join(f'"{c}" = excluded."{c}"' for c in update_cols)

        sql = (
            f'INSERT INTO "{table_name}" ({col_names}) VALUES ({placeholders}) '
            f"ON CONFLICT(\"{schema.primary_key}\") DO UPDATE SET {update_clause}"
        )

        values = [tuple(row.get(c) for c in columns) for row in rows]
        conn.executemany(sql, values)
        conn.commit()
        return len(rows)
    finally:
        conn.close()
```

### `data_pipeline/pipeline.py`

```
"""Orchestrate the full data pipeline."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from data_pipeline.config import PipelineConfig, load_config, load_schema
from data_pipeline.ingest import discover_csv_files, read_csv
from data_pipeline.load import upsert_rows
from data_pipeline.report import RunSummary, utc_now_iso, write_run_summary
from data_pipeline.transform import normalise_rows
from data_pipeline.validate import partition_rows, write_quarantine_errors


@dataclass
class PipelineResult:
    summary: RunSummary
    summary_path: Path


def run_pipeline(config_path: Path | str = "config.yaml") -> PipelineResult:
    started_at = utc_now_iso()
    start_time = time.monotonic()

    config = load_config(config_path)
    schema = load_schema(config.schema_path)

    config.input_dir.mkdir(parents=True, exist_ok=True)
    config.quarantine_dir.mkdir(parents=True, exist_ok=True)

    csv_files = discover_csv_files(config.input_dir)
    rows_read = 0
    rows_valid = 0
    rows_loaded = 0
    quarantine_count = 0
    input_files: list[str] = []

    for csv_path in csv_files:
        input_files.append(csv_path.name)
        raw_rows = read_csv(csv_path)
        rows_read += len(raw_rows)

        valid, invalid, errors_by_row = partition_rows(raw_rows, schema)
        rows_valid += len(valid)
        quarantine_count += len(invalid)

        if invalid:
            write_quarantine_errors(invalid, errors_by_row, config.quarantine_dir, csv_path.name)

        if valid:
            normalised = normalise_rows(valid, schema)
            rows_loaded += upsert_rows(
                config.sqlite_path, config.table_name, schema, normalised
            )

    duration = time.monotonic() - start_time
    finished_at = utc_now_iso()

    summary = RunSummary(
        started_at=started_at,
        finished_at=finished_at,
        duration_seconds=round(duration, 3),
        input_files=input_files,
        rows_read=rows_read,
        rows_valid=rows_valid,
        rows_loaded=rows_loaded,
        quarantine_count=quarantine_count,
    )
    summary_path = write_run_summary(summary, config.output_dir)
    return PipelineResult(summary=summary, summary_path=summary_path)
```

### `data_pipeline/report.py`

```
"""Write JSON run summaries after each pipeline execution."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class RunSummary:
    started_at: str
    finished_at: str
    duration_seconds: float
    input_files: list[str]
    rows_read: int
    rows_valid: int
    rows_loaded: int
    quarantine_count: int

    def to_dict(self) -> dict:
        return asdict(self)


def write_run_summary(summary: RunSummary, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = output_dir / f"run_summary_{timestamp}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(summary.to_dict(), f, indent=2)
    return path


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
```

### `data_pipeline/transform.py`

```
"""Normalise string and numeric columns."""

from __future__ import annotations

from data_pipeline.config import SchemaConfig


def normalise_row(row: dict[str, object], schema: SchemaConfig) -> dict[str, object]:
    result: dict[str, object] = {}
    for name, spec in schema.columns.items():
        value = row.get(name)
        if value is None:
            result[name] = None
        elif spec.type == "string" and isinstance(value, str):
            result[name] = value.lower()
        elif spec.type in ("number", "integer") and isinstance(value, (int, float)):
            result[name] = round(float(value), 2)
        else:
            result[name] = value
    return result


def normalise_rows(
    rows: list[dict[str, object]], schema: SchemaConfig
) -> list[dict[str, object]]:
    return [normalise_row(row, schema) for row in rows]
```

### `data_pipeline/validate.py`

```
"""Validate rows against a declared column schema."""

from __future__ import annotations

import json
from pathlib import Path

from data_pipeline.config import SchemaConfig


def _parse_value(raw: str, col_type: str) -> tuple[bool, object]:
    if raw == "" or raw is None:
        return True, None

    if col_type == "string":
        return True, str(raw)
    if col_type == "integer":
        try:
            return True, int(raw)
        except (TypeError, ValueError):
            return False, None
    if col_type == "number":
        try:
            return True, float(raw)
        except (TypeError, ValueError):
            return False, None
    return False, None


def validate_row(
    row: dict[str, str], schema: SchemaConfig
) -> tuple[bool, dict[str, object] | None, list[str]]:
    errors: list[str] = []
    parsed: dict[str, object] = {}

    for name, spec in schema.columns.items():
        raw = row.get(name, "")
        if spec.required and (raw is None or str(raw).strip() == ""):
            errors.append(f"missing required column: {name}")
            continue

        if raw is None or str(raw).strip() == "":
            parsed[name] = None
            continue

        ok, value = _parse_value(str(raw), spec.type)
        if not ok:
            errors.append(f"invalid type for column {name}: expected {spec.type}")
            continue
        parsed[name] = value

    extra = set(row.keys()) - set(schema.columns.keys())
    if extra:
        errors.append(f"unexpected columns: {', '.join(sorted(extra))}")

    if errors:
        return False, None, errors
    return True, parsed, []


def validate_rows(
    rows: list[dict[str, str]], schema: SchemaConfig
) -> tuple[list[dict[str, object]], list[dict[str, str]]]:
    valid: list[dict[str, object]] = []
    invalid: list[dict[str, str]] = []

    for row in rows:
        ok, parsed, _ = validate_row(row, schema)
        if ok and parsed is not None:
            valid.append(parsed)
        else:
            invalid.append(row)
    return valid, invalid


def write_quarantine_errors(
    invalid_rows: list[dict[str, str]],
    errors_by_row: list[list[str]],
    quarantine_dir: Path,
    source_name: str,
) -> Path | None:
    if not invalid_rows:
        return None

    quarantine_dir.mkdir(parents=True, exist_ok=True)
    out_path = quarantine_dir / f"{Path(source_name).stem}_quarantine.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for row, errs in zip(invalid_rows, errors_by_row, strict=True):
            record = {"row": row, "errors": errs}
            f.write(json.dumps(record) + "\n")
    return out_path


def partition_rows(
    rows: list[dict[str, str]], schema: SchemaConfig
) -> tuple[list[dict[str, object]], list[dict[str, str]], list[list[str]]]:
    valid: list[dict[str, object]] = []
    invalid: list[dict[str, str]] = []
    errors_by_row: list[list[str]] = []

    for row in rows:
        ok, parsed, errs = validate_row(row, schema)
        if ok and parsed is not None:
            valid.append(parsed)
        else:
            invalid.append(row)
            errors_by_row.append(errs)
    return valid, invalid, errors_by_row
```

### `scheduler.py`

```
"""Daily scheduler entrypoint using APScheduler."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from data_pipeline.pipeline import run_pipeline

DEFAULT_CRON = "0 2 * * *"

logger = logging.getLogger(__name__)


def _run_job(config_path: Path) -> None:
    result = run_pipeline(config_path)
    logger.info(
        "Scheduled run complete: rows_loaded=%s quarantine_count=%s duration_seconds=%s summary=%s",
        result.summary.rows_loaded,
        result.summary.quarantine_count,
        result.summary.duration_seconds,
        result.summary_path,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Schedule the data pipeline to run once per day."
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to pipeline configuration file (default: config.yaml)",
    )
    parser.add_argument(
        "--cron",
        default=DEFAULT_CRON,
        help=f'Cron expression for daily runs (default: "{DEFAULT_CRON}")',
    )
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Run the pipeline once immediately and exit (no scheduler).",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config_path = Path(args.config)

    if args.run_once:
        _run_job(config_path)
        return 0

    trigger = CronTrigger.from_crontab(args.cron)
    scheduler = BlockingScheduler()
    scheduler.add_job(
        _run_job,
        trigger=trigger,
        args=[config_path],
        id="daily_pipeline",
        replace_existing=True,
    )
    logger.info("Scheduler started with cron=%s config=%s", args.cron, config_path)
    scheduler.start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### `tests/test_pipeline.py`

```
"""Tests for the data pipeline."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
import yaml

from data_pipeline.config import load_schema
from data_pipeline.ingest import discover_csv_files, read_csv
from data_pipeline.load import upsert_rows
from data_pipeline.pipeline import run_pipeline
from data_pipeline.transform import normalise_row
from data_pipeline.validate import partition_rows, validate_row


@pytest.fixture
def schema():
    return load_schema(Path("schema/default_schema.json"))


@pytest.fixture
def tmp_config(tmp_path: Path):
    input_dir = tmp_path / "input"
    quarantine_dir = tmp_path / "quarantine"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    config = {
        "input_dir": str(input_dir),
        "quarantine_dir": str(quarantine_dir),
        "output_dir": str(output_dir),
        "sqlite_path": str(tmp_path / "test.db"),
        "table_name": "records",
        "schema_path": "schema/default_schema.json",
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(config), encoding="utf-8")
    return config_path, input_dir, quarantine_dir, output_dir, tmp_path / "test.db"


def test_discover_csv_files(tmp_path: Path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "a.csv").write_text("x\n1", encoding="utf-8")
    (input_dir / "b.txt").write_text("x", encoding="utf-8")

    files = discover_csv_files(input_dir)
    assert len(files) == 1
    assert files[0].name == "a.csv"


def test_validate_row_rejects_invalid_type(schema):
    row = {"id": "abc", "name": "Item", "category": "Cat", "amount": "1.0"}
    ok, parsed, errors = validate_row(row, schema)
    assert not ok
    assert parsed is None
    assert any("invalid type" in e for e in errors)


def test_validate_row_accepts_valid_row(schema):
    row = {"id": "1", "name": "Item", "category": "Cat", "amount": "10.5"}
    ok, parsed, errors = validate_row(row, schema)
    assert ok
    assert parsed == {"id": 1, "name": "Item", "category": "Cat", "amount": 10.5}
    assert errors == []


def test_normalise_row(schema):
    row = {"id": 1, "name": "Widget", "category": "Hardware", "amount": 10.556}
    result = normalise_row(row, schema)
    assert result["name"] == "widget"
    assert result["category"] == "hardware"
    assert result["amount"] == 10.56


def test_upsert_is_idempotent(schema, tmp_path: Path):
    db_path = tmp_path / "test.db"
    rows = [{"id": 1, "name": "widget", "category": "hardware", "amount": 10.56}]

    upsert_rows(db_path, "records", schema, rows)
    upsert_rows(db_path, "records", schema, rows)

    conn = sqlite3.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]
    conn.close()
    assert count == 1


def test_pipeline_end_to_end(tmp_config):
    config_path, input_dir, quarantine_dir, output_dir, db_path = tmp_config

    csv_content = (
        "id,name,category,amount\n"
        "1,Widget Alpha,Hardware,10.556\n"
        "2,,Software,25.999\n"
        "bad,Missing Id,Hardware,5.0\n"
    )
    (input_dir / "data.csv").write_text(csv_content, encoding="utf-8")

    result = run_pipeline(config_path)

    assert result.summary.rows_read == 3
    assert result.summary.rows_valid == 1
    assert result.summary.rows_loaded == 1
    assert result.summary.quarantine_count == 2
    assert result.summary.duration_seconds >= 0
    assert result.summary_path.exists()

    summary_data = json.loads(result.summary_path.read_text(encoding="utf-8"))
    assert summary_data["rows_read"] == 3
    assert summary_data["quarantine_count"] == 2

    quarantine_files = list(quarantine_dir.glob("*"))
    assert len(quarantine_files) == 1

    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT id, name, category, amount FROM records WHERE id = 1").fetchone()
    conn.close()
    assert row == (1, "widget alpha", "hardware", 10.56)


def test_pipeline_idempotent_on_rerun(tmp_config):
    config_path, input_dir, _, _, db_path = tmp_config
    (input_dir / "data.csv").write_text(
        "id,name,category,amount\n1,Widget,Hardware,10.0\n", encoding="utf-8"
    )

    run_pipeline(config_path)
    run_pipeline(config_path)

    conn = sqlite3.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]
    conn.close()
    assert count == 1


def test_partition_rows(schema):
    rows = [
        {"id": "1", "name": "A", "category": "X", "amount": "1.0"},
        {"id": "x", "name": "B", "category": "Y", "amount": "2.0"},
    ]
    valid, invalid, errors = partition_rows(rows, schema)
    assert len(valid) == 1
    assert len(invalid) == 1
    assert len(errors[0]) >= 1
```
