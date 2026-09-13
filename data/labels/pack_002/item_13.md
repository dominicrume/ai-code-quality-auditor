# item_13

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
`item_13`. Answer from the code alone; do not run the tools.

---

## The code

### `config/schema.yaml`

```
columns:
  - name: record_id
    type: string
    required: true
  - name: category
    type: string
    required: true
  - name: amount
    type: number
    required: true
  - name: status
    type: string
    required: false
```

### `config/settings.yaml`

```
input_dir: data/input
quarantine_dir: data/quarantine
sqlite_path: data/output/pipeline.db
report_dir: data/reports
schema_path: config/schema.yaml
table_name: normalised_records
```

### `pyproject.toml`

```
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[project]
name = "data_pipeline"
version = "1.0.0"
description = "Local CSV ingest, validate, transform, and load pipeline"
requires-python = ">=3.10"
dependencies = [
    "APScheduler>=3.10.0",
    "PyYAML>=6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
]

[project.scripts]
data-pipeline = "data_pipeline.__main__:main"
data-pipeline-scheduler = "data_pipeline.scheduler:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

### `src/data_pipeline/__init__.py`

```
"""Data pipeline package."""

__version__ = "1.0.0"
```

### `src/data_pipeline/__main__.py`

```
from __future__ import annotations

import sys

from data_pipeline.pipeline import run_pipeline


def main() -> int:
    result = run_pipeline()
    print(
        f"Pipeline complete: read={result.rows_read} "
        f"valid={result.rows_valid} loaded={result.rows_loaded} "
        f"quarantined={result.quarantine_count} "
        f"duration={result.duration_seconds:.3f}s "
        f"summary={result.summary_path}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### `src/data_pipeline/config.py`

```
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class ColumnSchema:
    name: str
    type: str
    required: bool = True


@dataclass(frozen=True)
class PipelineConfig:
    input_dir: Path
    quarantine_dir: Path
    sqlite_path: Path
    report_dir: Path
    schema_path: Path
    table_name: str


def _resolve_path(base: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (base / path).resolve()


def load_config(config_path: Path | None = None) -> PipelineConfig:
    base_dir = Path(__file__).resolve().parents[2]
    path = config_path or base_dir / "config" / "settings.yaml"
    with path.open(encoding="utf-8") as handle:
        raw: dict[str, Any] = yaml.safe_load(handle)

    return PipelineConfig(
        input_dir=_resolve_path(base_dir, raw["input_dir"]),
        quarantine_dir=_resolve_path(base_dir, raw["quarantine_dir"]),
        sqlite_path=_resolve_path(base_dir, raw["sqlite_path"]),
        report_dir=_resolve_path(base_dir, raw["report_dir"]),
        schema_path=_resolve_path(base_dir, raw["schema_path"]),
        table_name=raw["table_name"],
    )


def load_schema(schema_path: Path) -> list[ColumnSchema]:
    with schema_path.open(encoding="utf-8") as handle:
        raw: dict[str, Any] = yaml.safe_load(handle)

    columns: list[ColumnSchema] = []
    for entry in raw["columns"]:
        columns.append(
            ColumnSchema(
                name=entry["name"],
                type=entry["type"],
                required=entry.get("required", True),
            )
        )
    return columns
```

### `src/data_pipeline/ingest.py`

```
from __future__ import annotations

import csv
from pathlib import Path


def read_csv_files(input_dir: Path) -> list[tuple[Path, list[dict[str, str]]]]:
    """Read all CSV files from the configured input directory."""
    if not input_dir.exists():
        input_dir.mkdir(parents=True, exist_ok=True)
        return []

    results: list[tuple[Path, list[dict[str, str]]]] = []
    for csv_path in sorted(input_dir.glob("*.csv")):
        with csv_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            rows = [dict(row) for row in reader]
        results.append((csv_path, rows))
    return results
```

### `src/data_pipeline/load.py`

```
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from data_pipeline.config import ColumnSchema


def _row_hash(row: dict[str, str | float]) -> str:
    payload = json.dumps(row, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _ensure_table(
    connection: sqlite3.Connection, table_name: str, schema: list[ColumnSchema]
) -> None:
    column_defs = ["row_hash TEXT PRIMARY KEY"]
    for column in schema:
        sql_type = "REAL" if column.type == "number" else "TEXT"
        column_defs.append(f"{column.name} {sql_type} NOT NULL")
    ddl = f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(column_defs)})"
    connection.execute(ddl)
    connection.commit()


def load_rows(
    sqlite_path: Path,
    table_name: str,
    rows: list[dict[str, str | float]],
    schema: list[ColumnSchema],
) -> int:
    """Write normalised rows into SQLite using idempotent upserts."""
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(sqlite_path)
    try:
        _ensure_table(connection, table_name, schema)
        column_names = ["row_hash"] + [column.name for column in schema]
        placeholders = ", ".join("?" for _ in column_names)
        update_clause = ", ".join(
            f"{column.name}=excluded.{column.name}" for column in schema
        )
        insert_sql = (
            f"INSERT INTO {table_name} ({', '.join(column_names)}) "
            f"VALUES ({placeholders}) "
            f"ON CONFLICT(row_hash) DO UPDATE SET {update_clause}"
        )

        inserted = 0
        for row in rows:
            values = [_row_hash(row)] + [row[column.name] for column in schema]
            connection.execute(insert_sql, values)
            inserted += 1
        connection.commit()
        return inserted
    finally:
        connection.close()
```

### `src/data_pipeline/pipeline.py`

```
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from data_pipeline.config import PipelineConfig, load_config, load_schema
from data_pipeline.ingest import read_csv_files
from data_pipeline.load import load_rows
from data_pipeline.report import write_quarantine, write_run_summary
from data_pipeline.transform import normalise_rows
from data_pipeline.validate import validate_rows


@dataclass(frozen=True)
class PipelineResult:
    input_files: int
    rows_read: int
    rows_valid: int
    rows_loaded: int
    quarantine_count: int
    duration_seconds: float
    summary_path: Path


def run_pipeline(config: PipelineConfig | None = None) -> PipelineResult:
    """Execute the full ingest-validate-transform-load pipeline."""
    started = time.perf_counter()
    cfg = config or load_config()
    schema = load_schema(cfg.schema_path)

    csv_files = read_csv_files(cfg.input_dir)
    rows_read = 0
    rows_valid = 0
    rows_loaded = 0
    quarantine_count = 0

    for source_path, rows in csv_files:
        rows_read += len(rows)
        validation = validate_rows(rows, schema)
        rows_valid += len(validation.valid_rows)
        quarantine_count += len(validation.invalid_rows)

        write_quarantine(cfg.quarantine_dir, source_path.stem, validation.invalid_rows)

        if validation.valid_rows:
            normalised = normalise_rows(validation.valid_rows, schema)
            rows_loaded += load_rows(
                cfg.sqlite_path, cfg.table_name, normalised, schema
            )

    duration_seconds = time.perf_counter() - started
    summary_path = write_run_summary(
        cfg.report_dir,
        input_files=len(csv_files),
        rows_read=rows_read,
        rows_valid=rows_valid,
        rows_loaded=rows_loaded,
        quarantine_count=quarantine_count,
        duration_seconds=duration_seconds,
    )

    return PipelineResult(
        input_files=len(csv_files),
        rows_read=rows_read,
        rows_valid=rows_valid,
        rows_loaded=rows_loaded,
        quarantine_count=quarantine_count,
        duration_seconds=duration_seconds,
        summary_path=summary_path,
    )
```

### `src/data_pipeline/report.py`

```
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path


def write_quarantine(
    quarantine_dir: Path, source_name: str, invalid_rows: list[dict[str, str | None]]
) -> Path | None:
    if not invalid_rows:
        return None

    quarantine_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = quarantine_dir / f"{source_name}_{timestamp}_quarantine.csv"
    fieldnames = sorted({key for row in invalid_rows for key in row})

    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(invalid_rows)

    return output_path


def write_run_summary(
    report_dir: Path,
    *,
    input_files: int,
    rows_read: int,
    rows_valid: int,
    rows_loaded: int,
    quarantine_count: int,
    duration_seconds: float,
) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "input_files": input_files,
        "rows_read": rows_read,
        "rows_valid": rows_valid,
        "rows_loaded": rows_loaded,
        "quarantine_count": quarantine_count,
        "duration_seconds": round(duration_seconds, 3),
    }
    output_path = report_dir / f"run_summary_{timestamp}.json"
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
        handle.write("\n")
    return output_path
```

### `src/data_pipeline/scheduler.py`

```
from __future__ import annotations

import argparse
import logging
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from data_pipeline.pipeline import run_pipeline

DEFAULT_CRON = "0 2 * * *"


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def _run_scheduled_job() -> None:
    logger = logging.getLogger("data_pipeline.scheduler")
    result = run_pipeline()
    logger.info(
        "Pipeline run complete: read=%s valid=%s loaded=%s quarantined=%s duration=%.3fs",
        result.rows_read,
        result.rows_valid,
        result.rows_loaded,
        result.quarantine_count,
        result.duration_seconds,
    )


def start_scheduler(cron: str = DEFAULT_CRON) -> None:
    """Start APScheduler to run the pipeline once per day."""
    _configure_logging()
    logger = logging.getLogger("data_pipeline.scheduler")
    scheduler = BlockingScheduler()
    scheduler.add_job(
        _run_scheduled_job,
        trigger=CronTrigger.from_crontab(cron),
        id="daily_pipeline",
        replace_existing=True,
    )
    logger.info("Scheduler started with cron expression: %s", cron)
    scheduler.start()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Daily data pipeline scheduler")
    parser.add_argument(
        "--cron",
        default=DEFAULT_CRON,
        help="Cron expression for daily runs (default: 0 2 * * *)",
    )
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Run the pipeline once immediately instead of starting the scheduler",
    )
    args = parser.parse_args(argv)

    if args.run_once:
        _configure_logging()
        _run_scheduled_job()
        return 0

    start_scheduler(args.cron)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### `src/data_pipeline/transform.py`

```
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from data_pipeline.config import ColumnSchema


def normalise_rows(
    rows: list[dict[str, str]], schema: list[ColumnSchema]
) -> list[dict[str, str | float]]:
    """Lowercase string columns and round numeric columns to two decimal places."""
    schema_by_name = {column.name: column for column in schema}
    normalised: list[dict[str, str | float]] = []

    for row in rows:
        transformed: dict[str, str | float] = {}
        for column in schema:
            raw_value = row.get(column.name, "")
            if _is_blank(raw_value):
                transformed[column.name] = ""
                continue

            if column.type == "string":
                transformed[column.name] = str(raw_value).strip().lower()
            elif column.type == "number":
                rounded = Decimal(str(raw_value)).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                transformed[column.name] = float(rounded)
            else:
                transformed[column.name] = str(raw_value)
        normalised.append(transformed)

    return normalised


def _is_blank(value: str | None) -> bool:
    return value is None or str(value).strip() == ""
```

### `src/data_pipeline/validate.py`

```
from __future__ import annotations

from dataclasses import dataclass

from data_pipeline.config import ColumnSchema


@dataclass(frozen=True)
class ValidationResult:
    valid_rows: list[dict[str, str]]
    invalid_rows: list[dict[str, str | None]]


def _is_blank(value: str | None) -> bool:
    return value is None or str(value).strip() == ""


def _validate_type(value: str, column_type: str) -> bool:
    if column_type == "string":
        return True
    if column_type == "number":
        try:
            float(value)
            return True
        except (TypeError, ValueError):
            return False
    return False


def validate_rows(
    rows: list[dict[str, str]], schema: list[ColumnSchema]
) -> ValidationResult:
    """Validate rows against the declared schema."""
    valid_rows: list[dict[str, str]] = []
    invalid_rows: list[dict[str, str | None]] = []
    schema_by_name = {column.name: column for column in schema}

    for row in rows:
        errors: list[str] = []
        for column in schema:
            raw_value = row.get(column.name)
            if column.required and _is_blank(raw_value):
                errors.append(f"missing required field: {column.name}")
                continue
            if _is_blank(raw_value):
                continue
            if not _validate_type(str(raw_value), column.type):
                errors.append(f"invalid type for {column.name}: expected {column.type}")

        for field_name in row:
            if field_name not in schema_by_name:
                errors.append(f"unexpected field: {field_name}")

        if errors:
            invalid_entry = dict(row)
            invalid_entry["_validation_errors"] = "; ".join(errors)
            invalid_rows.append(invalid_entry)
        else:
            valid_rows.append(row)

    return ValidationResult(valid_rows=valid_rows, invalid_rows=invalid_rows)
```

### `tests/test_pipeline.py`

```
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
import yaml

from data_pipeline.config import ColumnSchema, PipelineConfig
from data_pipeline.ingest import read_csv_files
from data_pipeline.load import load_rows
from data_pipeline.pipeline import run_pipeline
from data_pipeline.report import write_run_summary
from data_pipeline.transform import normalise_rows
from data_pipeline.validate import validate_rows


@pytest.fixture
def schema() -> list[ColumnSchema]:
    return [
        ColumnSchema(name="record_id", type="string", required=True),
        ColumnSchema(name="category", type="string", required=True),
        ColumnSchema(name="amount", type="number", required=True),
        ColumnSchema(name="status", type="string", required=False),
    ]


@pytest.fixture
def pipeline_config(tmp_path: Path) -> PipelineConfig:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    schema_path = tmp_path / "schema.yaml"
    schema_path.write_text(
        yaml.dump(
            {
                "columns": [
                    {"name": "record_id", "type": "string", "required": True},
                    {"name": "category", "type": "string", "required": True},
                    {"name": "amount", "type": "number", "required": True},
                    {"name": "status", "type": "string", "required": False},
                ]
            }
        ),
        encoding="utf-8",
    )
    return PipelineConfig(
        input_dir=input_dir,
        quarantine_dir=tmp_path / "quarantine",
        sqlite_path=tmp_path / "output" / "pipeline.db",
        report_dir=tmp_path / "reports",
        schema_path=schema_path,
        table_name="normalised_records",
    )


def test_ingest_reads_csv(pipeline_config: PipelineConfig) -> None:
    csv_path = pipeline_config.input_dir / "sample.csv"
    csv_path.write_text(
        "record_id,category,amount,status\n"
        "R001,Widget,12.345,active\n",
        encoding="utf-8",
    )

    files = read_csv_files(pipeline_config.input_dir)
    assert len(files) == 1
    assert files[0][1][0]["record_id"] == "R001"


def test_validate_rejects_invalid_rows(schema: list[ColumnSchema]) -> None:
    rows = [
        {"record_id": "R001", "category": "Widget", "amount": "10.5", "status": "active"},
        {"record_id": "", "category": "Widget", "amount": "bad", "status": ""},
    ]
    result = validate_rows(rows, schema)
    assert len(result.valid_rows) == 1
    assert len(result.invalid_rows) == 1
    assert "_validation_errors" in result.invalid_rows[0]


def test_transform_normalises_values(schema: list[ColumnSchema]) -> None:
    rows = [
        {
            "record_id": "R001",
            "category": "WIDGET",
            "amount": "12.3456",
            "status": "ACTIVE",
        }
    ]
    normalised = normalise_rows(rows, schema)[0]
    assert normalised["category"] == "widget"
    assert normalised["amount"] == 12.35


def test_load_is_idempotent(schema: list[ColumnSchema], tmp_path: Path) -> None:
    sqlite_path = tmp_path / "pipeline.db"
    row = {
        "record_id": "R001",
        "category": "widget",
        "amount": 12.35,
        "status": "active",
    }

    load_rows(sqlite_path, "records", [row], schema)
    load_rows(sqlite_path, "records", [row], schema)

    connection = sqlite3.connect(sqlite_path)
    count = connection.execute("SELECT COUNT(*) FROM records").fetchone()[0]
    connection.close()
    assert count == 1


def test_run_summary_contains_counts(tmp_path: Path) -> None:
    summary_path = write_run_summary(
        tmp_path,
        input_files=1,
        rows_read=3,
        rows_valid=2,
        rows_loaded=2,
        quarantine_count=1,
        duration_seconds=1.25,
    )
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert payload["rows_read"] == 3
    assert payload["quarantine_count"] == 1
    assert payload["duration_seconds"] == 1.25


def test_pipeline_end_to_end(pipeline_config: PipelineConfig) -> None:
    (pipeline_config.input_dir / "sample.csv").write_text(
        "record_id,category,amount,status\n"
        "R001,Widget,12.3456,active\n",
        encoding="utf-8",
    )

    result = run_pipeline(pipeline_config)
    assert result.rows_loaded == 1
    assert result.quarantine_count == 0
    assert result.summary_path.exists()

    connection = sqlite3.connect(pipeline_config.sqlite_path)
    loaded = connection.execute(
        "SELECT category, amount, status FROM normalised_records"
    ).fetchone()
    connection.close()
    assert loaded == ("widget", 12.35, "active")
```
