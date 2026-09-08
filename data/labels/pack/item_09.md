# item_09

**Specification:** `data_pipeline`  
**Covers 2 sampled run(s)** (identical code) — replayed capture

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

Write your number in `labels_rater<N>.csv` on the row for `item_09`.

---

## The code (10 files, 1004 lines)

### `code/config.yaml`

```yaml
pipeline:
  input_dir: "input"
  db_path: "pipeline.db"
  quarantine_dir: "quarantine"
  summary_dir: "summaries"

schedule:
  time: "00:00"
  cron: null
```

### `code/main.py`

```py
#!/usr/bin/env python3
"""
CLI Entrypoint for the data pipeline.
Integrates command line arguments with config.yaml, sets up logging,
and runs the pipeline in either single-run or scheduled mode.
"""

import os
import sys
import argparse
import logging
import yaml
from pathlib import Path

from pipeline import DataPipeline
from pipeline.schedule import start_scheduler

def setup_logging() -> logging.Logger:
    """
    Sets up the logging configuration.
    Governance: Employs safe logging where no raw CSV values (PII) are printed.
    """
    logger = logging.getLogger("data_pipeline")
    logger.setLevel(logging.INFO)
    
    # Avoid duplicate handlers if setup is called multiple times
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
    return logger

def load_yaml_config(config_path: str = "config.yaml") -> dict:
    """
    Loads configurations from config.yaml if it exists.
    """
    config = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f)
                if isinstance(loaded, dict):
                    config = loaded
        except Exception as e:
            # Safe generic log
            print(f"Warning: Failed to load config file: {str(e)}", file=sys.stderr)
    return config

def main():
    logger = setup_logging()
    logger.info("Initializing Data Pipeline CLI Application")
    
    # 1. Load YAML Configuration
    yaml_config = load_yaml_config()
    pipeline_cfg = yaml_config.get("pipeline", {})
    schedule_cfg = yaml_config.get("schedule", {})
    
    # 2. Setup argument parser
    parser = argparse.ArgumentParser(
        description="ETL Data Pipeline CLI with scheduling, schema validation, and SQLite loading."
    )
    
    # Directory overrides
    parser.add_argument(
        "--input-dir",
        default=pipeline_cfg.get("input_dir", "input"),
        help="Directory containing input CSV files."
    )
    parser.add_argument(
        "--db-path",
        default=pipeline_cfg.get("db_path", "pipeline.db"),
        help="SQLite database file path."
    )
    parser.add_argument(
        "--quarantine-dir",
        default=pipeline_cfg.get("quarantine_dir", "quarantine"),
        help="Directory to store quarantine CSV files."
    )
    parser.add_argument(
        "--summary-dir",
        default=pipeline_cfg.get("summary_dir", "summaries"),
        help="Directory to store run summary JSON files."
    )
    
    # Scheduling options
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Run the application in scheduled mode (infinite loop)."
    )
    parser.add_argument(
        "--cron",
        default=schedule_cfg.get("cron"),
        help="Cron expression for daily scheduling (e.g. '0 0 * * *'). Overrides --time."
    )
    parser.add_argument(
        "--time",
        default=schedule_cfg.get("time", "00:00"),
        help="Daily run time in HH:MM format (default: '00:00')."
    )
    
    args = parser.parse_args()
    
    # Resolve relative paths relative to current working directory
    input_dir = os.path.abspath(args.input_dir)
    db_path = os.path.abspath(args.db_path)
    quarantine_dir = os.path.abspath(args.quarantine_dir)
    summary_dir = os.path.abspath(args.summary_dir)
    
    # 3. Create pipeline instance
    pipeline = DataPipeline(
        input_dir=input_dir,
        db_path=db_path,
        quarantine_dir=quarantine_dir,
        summary_dir=summary_dir
    )
    
    if args.schedule:
        # Define execution closure
        def scheduled_job():
            logger.info("Executing scheduled pipeline run...")
            try:
                summary = pipeline.run()
                logger.info(
                    f"Scheduled run completed. Status: {summary['status']}, "
                    f"Processed: {summary['valid_rows_processed']}, "
                    f"Quarantined: {summary['quarantined_rows_count']}"
                )
            except Exception as e:
                logger.error(f"Scheduled pipeline run encountered an error: {str(e)}")
        
        logger.info("Starting scheduler. Press Ctrl+C to terminate.")
        try:
            start_scheduler(scheduled_job, cron_string=args.cron, schedule_time=args.time)
        except (KeyboardInterrupt, SystemExit):
            logger.info("CLI scheduler shutdown requested. Exiting.")
    else:
        # Single run execution
        try:
            summary = pipeline.run()
            logger.info("Single run pipeline execution completed successfully.")
            print("\n================ Run Summary ================")
            print(f"Run ID:                 {summary['run_id']}")
            print(f"Status:                 {summary['status']}")
            print(f"Start Time:             {summary['start_time']}")
            print(f"End Time:               {summary['end_time']}")
            print(f"Duration (seconds):     {summary['duration_seconds']}")
            print(f"Files Processed:        {', '.join(summary['files_processed'])}")
            print(f"Total Rows Read:        {summary['total_rows_read']}")
            print(f"Valid Rows Processed:   {summary['valid_rows_processed']}")
            print(f"Quarantined Rows:       {summary['quarantined_rows_count']}")
            print(f"SQLite Loaded Rows:     {summary['inserted_rows_count']}")
            print("=============================================\n")
            
            if summary["status"] == "FAILED":
                sys.exit(1)
        except Exception as e:
            logger.error(f"Data pipeline execution failed: {str(e)}")
            sys.exit(1)

if __name__ == "__main__":
    main()
```

### `code/pipeline/__init__.py`

```py
"""
Data Pipeline package initializer.
Exposes the core DataPipeline orchestrator.
"""

import os
import time
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any

from pipeline.ingest import list_csv_files, get_file_hash, read_csv_rows
from pipeline.validate import validate_row, QuarantineManager
from pipeline.transform import normalise_row
from pipeline.load import DatabaseManager
from pipeline.report import write_summary

logger = logging.getLogger("data_pipeline")

class DataPipeline:
    """
    Orchestrator class for running the ingest, validate, transform, and load data pipeline.
    """
    def __init__(self, input_dir: str, db_path: str, quarantine_dir: str, summary_dir: str):
        self.input_dir = input_dir
        self.db_path = db_path
        self.quarantine_dir = quarantine_dir
        self.summary_dir = summary_dir

        # Ensure required directories exist
        os.makedirs(self.input_dir, exist_ok=True)
        os.makedirs(self.quarantine_dir, exist_ok=True)
        os.makedirs(self.summary_dir, exist_ok=True)

        self.db_manager = DatabaseManager(self.db_path)

    def run(self) -> Dict[str, Any]:
        """
        Executes the ETL pipeline run.
        Returns:
            A dictionary containing the run execution summary.
        """
        run_id = str(uuid.uuid4())
        start_time = time.time()
        start_timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        logger.info(f"Starting pipeline run: {run_id}")

        # Initialize the database schemas
        self.db_manager.initialize_schema()

        # Ingest: list all files
        csv_files = list_csv_files(self.input_dir)
        logger.info(f"Found {len(csv_files)} CSV file(s) for ingestion.")

        total_rows_read = 0
        valid_rows_processed = 0
        quarantined_rows_count = 0
        inserted_rows_count = 0
        processed_files_list = []

        # We execute in a single db connection context for performance
        with self.db_manager.connect() as conn:
            for file_name in csv_files:
                file_path = os.path.join(self.input_dir, file_name)
                
                # Check for file-level idempotency
                try:
                    file_hash = get_file_hash(file_path)
                except Exception as e:
                    logger.error(f"Failed to calculate hash for file {file_name}. Skipping. Details: {str(e)}")
                    continue

                if self.db_manager.is_file_processed(conn, file_hash):
                    logger.info(f"File {file_name} has already been processed (hash match). Skipping.")
                    continue

                logger.info(f"Processing file: {file_name}")
                processed_files_list.append(file_name)

                # Initialize quarantine manager lazily for this run
                with QuarantineManager(self.quarantine_dir, run_id) as quarantine:
                    try:
                        rows = read_csv_rows(file_path)
                    except Exception as e:
                        logger.error(f"Error reading CSV file {file_name}: {str(e)}")
                        continue

                    for raw_row in rows:
                        total_rows_read += 1
                        
                        # Validate row
                        is_valid, validated_row, error_reason = validate_row(raw_row)
                        
                        if not is_valid:
                            quarantined_rows_count += 1
                            quarantine.quarantine_row(raw_row, error_reason)
                            continue

                        # Transform / Normalise row
                        normalised = normalise_row(validated_row)
                        valid_rows_processed += 1

                        # Load row into SQLite (row-level idempotency handled via INSERT OR IGNORE)
                        inserted = self.db_manager.insert_transaction(conn, normalised)
                        if inserted:
                            inserted_rows_count += 1

                # Record file hash to ensure file-level idempotency on next runs
                self.db_manager.record_processed_file(conn, file_hash, file_name)
            
            # Commit connection
            conn.commit()

        end_time = time.time()
        end_timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        duration = end_time - start_time

        # Generate summary report
        summary = write_summary(
            summary_dir=self.summary_dir,
            run_id=run_id,
            start_time=start_timestamp,
            end_time=end_timestamp,
            duration=duration,
            files_processed=processed_files_list,
            total_rows=total_rows_read,
            valid_rows=valid_rows_processed,
            quarantined_rows=quarantined_rows_count,
            inserted_rows=inserted_rows_count,
            status="SUCCESS"
        )

        logger.info(f"Pipeline run {run_id} completed. Status: SUCCESS, Loaded: {inserted_rows_count}, Quarantined: {quarantined_rows_count}")
        return summary
```

### `code/pipeline/ingest.py`

```py
"""
Ingestion module for the data pipeline.
Handles file scanning, file SHA-256 hashing, and CSV reading.
"""

import os
import csv
import hashlib
import logging
from typing import List, Dict

logger = logging.getLogger("data_pipeline.ingest")

def list_csv_files(input_dir: str) -> List[str]:
    """
    Scans the given directory and returns a sorted list of CSV file names.
    """
    if not os.path.exists(input_dir):
        logger.warning(f"Input directory '{input_dir}' does not exist.")
        return []
    
    files = [f for f in os.listdir(input_dir) if f.lower().endswith(".csv")]
    return sorted(files)

def get_file_hash(file_path: str) -> str:
    """
    Calculates the SHA-256 hash of a file's content.
    Used for verifying file-level idempotency.
    """
    sha256 = hashlib.sha256()
    # Read in binary chunks to prevent loading huge files into memory and handle all file encodings
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(65536) # 64kb chunks
            if not chunk:
                break
            sha256.update(chunk)
    return sha256.hexdigest()

def read_csv_rows(file_path: str) -> List[Dict[str, str]]:
    """
    Reads a CSV file and returns its rows as a list of dictionaries.
    Strips whitespace from both keys (headers) and values.
    Uses utf-8-sig to handle byte order marks gracefully.
    """
    rows = []
    with open(file_path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        
        # Strip header names
        if reader.fieldnames:
            reader.fieldnames = [name.strip() for name in reader.fieldnames if name]
        else:
            return []
            
        for row in reader:
            # Clean values: strip spaces and ignore empty/None keys
            cleaned_row = {}
            for k, v in row.items():
                if k:  # only if key is not None or empty
                    cleaned_row[k] = v.strip() if v else ""
            rows.append(cleaned_row)
            
    return rows
```

### `code/pipeline/load.py`

```py
"""
Loading module for the data pipeline.
Manages connections and idempotent operations in the SQLite database.
"""

import sqlite3
import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Dict, Any, Generator

logger = logging.getLogger("data_pipeline.load")

class DatabaseManager:
    """
    Manages SQLite database connections, schema setup, and transactions.
    """
    def __init__(self, db_path: str):
        self.db_path = db_path

    @contextmanager
    def connect(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Context manager for SQLite database connection.
        Automatically commits changes and closes the connection on exit.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def initialize_schema(self):
        """
        Creates the database tables if they do not exist.
        """
        logger.info(f"Initializing database schema at: {self.db_path}")
        with self.connect() as conn:
            cursor = conn.cursor()
            
            # transactions table. transaction_id as PRIMARY KEY enforces row-level idempotency
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    transaction_id TEXT PRIMARY KEY,
                    product_id TEXT,
                    price REAL,
                    quantity INTEGER,
                    category TEXT,
                    processed_at TEXT
                )
            """)
            
            # processed_files table. file_hash as PRIMARY KEY enforces file-level idempotency
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS processed_files (
                    file_hash TEXT PRIMARY KEY,
                    file_name TEXT,
                    processed_at TEXT
                )
            """)
            conn.commit()

    def is_file_processed(self, conn: sqlite3.Connection, file_hash: str) -> bool:
        """
        Checks if a file with the given hash has already been processed.
        """
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM processed_files WHERE file_hash = ?", (file_hash,))
        return cursor.fetchone() is not None

    def record_processed_file(self, conn: sqlite3.Connection, file_hash: str, file_name: str):
        """
        Records that a file has been successfully processed.
        """
        cursor = conn.cursor()
        processed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        cursor.execute("""
            INSERT OR IGNORE INTO processed_files (file_hash, file_name, processed_at)
            VALUES (?, ?, ?)
        """, (file_hash, file_name, processed_at))

    def insert_transaction(self, conn: sqlite3.Connection, row: Dict[str, Any]) -> bool:
        """
        Idempotently inserts a transaction row into SQLite database.
        Returns:
            True if a new row was inserted, False if ignored (duplicate transaction_id).
        """
        cursor = conn.cursor()
        processed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        
        cursor.execute("""
            INSERT OR IGNORE INTO transactions (
                transaction_id, product_id, price, quantity, category, processed_at
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            row["transaction_id"],
            row["product_id"],
            row["price"],
            row["quantity"],
            row["category"],
            processed_at
        ))
        
        return cursor.rowcount > 0
```

### `code/pipeline/report.py`

```py
"""
Reporting module for the data pipeline.
Generates and writes structured JSON summaries of each ETL execution run.
"""

import os
import json
import logging
from typing import Dict, Any, List

logger = logging.getLogger("data_pipeline.report")

def write_summary(
    summary_dir: str,
    run_id: str,
    start_time: str,
    end_time: str,
    duration: float,
    files_processed: List[str],
    total_rows: int,
    valid_rows: int,
    quarantined_rows: int,
    inserted_rows: int,
    status: str
) -> Dict[str, Any]:
    """
    Constructs a run execution summary dict, writes it to a JSON file, and returns it.
    """
    summary = {
        "run_id": run_id,
        "start_time": start_time,
        "end_time": end_time,
        "duration_seconds": round(duration, 4),
        "files_processed": files_processed,
        "total_rows_read": total_rows,
        "valid_rows_processed": valid_rows,
        "quarantined_rows_count": quarantined_rows,
        "inserted_rows_count": inserted_rows,
        "status": status
    }
    
    os.makedirs(summary_dir, exist_ok=True)
    summary_file_path = os.path.join(summary_dir, f"summary_{run_id}.json")
    
    try:
        with open(summary_file_path, mode="w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        logger.info(f"Execution run summary written to: {summary_file_path}")
    except Exception as e:
        logger.error(f"Failed to write summary file: {str(e)}")
        
    return summary
```

### `code/pipeline/schedule.py`

```py
"""
Scheduler module for the data pipeline.
Schedules execution daily at a given time or cron expression.
Falls back to a standard library sleep loop if APScheduler is not available.
"""

import time
import logging
from datetime import datetime, timedelta
from typing import Callable, Optional

logger = logging.getLogger("data_pipeline.schedule")

try:
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger
    APS_AVAILABLE = True
except ImportError:
    APS_AVAILABLE = False

def run_fallback_loop(job_func: Callable[[], None], schedule_time_str: str):
    """
    Standard library fallback sleep loop that runs daily at target 'HH:MM'.
    """
    logger.info(f"APScheduler not found. Using fallback standard library daily execution loop.")
    logger.info(f"Target run time configured: daily at {schedule_time_str}")
    
    try:
        hour, minute = map(int, schedule_time_str.split(":"))
    except ValueError:
        logger.error(f"Invalid daily time format '{schedule_time_str}'. Defaulting to '00:00'.")
        hour, minute = 0, 0

    while True:
        now = datetime.now()
        target_today = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        if now >= target_today:
            target_run = target_today + timedelta(days=1)
        else:
            target_run = target_today
            
        sleep_seconds = (target_run - now).total_seconds()
        logger.info(f"Next scheduled run target: {target_run.strftime('%Y-%m-%d %H:%M:%S')}. Sleeping for {sleep_seconds:.1f} seconds.")
        
        try:
            time.sleep(sleep_seconds)
            logger.info("Executing scheduled pipeline run...")
            job_func()
        except KeyboardInterrupt:
            logger.info("Scheduler loop interrupted. Exiting.")
            break
        except Exception as e:
            logger.error(f"Error during execution: {str(e)}")
            time.sleep(60) # Avoid rapid tight loop crash

def start_scheduler(job_func: Callable[[], None], cron_string: Optional[str] = None, schedule_time: str = "00:00"):
    """
    Starts scheduling daily pipeline execution.
    If cron_string is provided, schedules with the cron expression.
    Otherwise, schedules daily at schedule_time ('HH:MM').
    """
    if APS_AVAILABLE:
        logger.info("Initializing APScheduler blocking scheduler.")
        scheduler = BlockingScheduler()
        
        if cron_string:
            try:
                trigger = CronTrigger.from_crontab(cron_string)
                logger.info(f"Scheduling job using cron trigger: '{cron_string}'")
            except Exception as e:
                logger.error(f"Invalid cron expression '{cron_string}': {str(e)}. Falling back to time '{schedule_time}'")
                hour, minute = map(int, schedule_time.split(":"))
                trigger = CronTrigger(hour=hour, minute=minute)
        else:
            try:
                hour, minute = map(int, schedule_time.split(":"))
                trigger = CronTrigger(hour=hour, minute=minute)
                logger.info(f"Scheduling job to run daily at {schedule_time}")
            except Exception as e:
                logger.error(f"Invalid daily time format '{schedule_time}': {str(e)}. Defaulting to daily at 00:00")
                trigger = CronTrigger(hour=0, minute=0)
                
        scheduler.add_job(job_func, trigger)
        
        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Scheduler stopped.")
    else:
        run_fallback_loop(job_func, schedule_time)
```

### `code/pipeline/transform.py`

```py
"""
Transformation and normalisation module for the data pipeline.
Lowercases text fields (product_id, category) and rounds numeric values (price) to 2 decimal places.
"""

from typing import Dict, Any

def normalise_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalises the validated fields in a row.
    - Lowercases product_id and category if they are present.
    - Rounds price to 2 decimal places.
    """
    normalised = dict(row)
    
    # 1. Lowercase string fields (excluding transaction_id to preserve its unique key format)
    if normalised.get("product_id") is not None:
        normalised["product_id"] = str(normalised["product_id"]).lower()
        
    if normalised.get("category") is not None:
        normalised["category"] = str(normalised["category"]).lower()
        
    # 2. Round float fields to 2 decimal places
    if normalised.get("price") is not None:
        normalised["price"] = round(float(normalised["price"]), 2)
        
    return normalised
```

### `code/pipeline/validate.py`

```py
"""
Validation and quarantine module for the data pipeline.
Enforces the schema rules and writes invalid rows to the quarantine directory.
"""

import os
import csv
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, Optional

logger = logging.getLogger("data_pipeline.validate")

# Declared Column Schema
COLUMN_SCHEMA = {
    "transaction_id": {"type": "str", "required": True},
    "product_id": {"type": "str", "required": True},
    "price": {"type": "float", "required": True},
    "quantity": {"type": "int", "required": True},
    "category": {"type": "str", "required": False}
}

def validate_row(row: Dict[str, str]) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    Validates a raw row against the declared COLUMN_SCHEMA.
    Does not log or include raw row values in error reasons to ensure PII is not leaked.
    Returns:
        A tuple of (is_valid, validated_row_dict, error_reason_string).
    """
    validated = {}
    
    for field, rules in COLUMN_SCHEMA.items():
        val = row.get(field, "").strip()
        is_required = rules["required"]
        field_type = rules["type"]
        
        # Check required fields
        if is_required and not val:
            return False, None, f"Missing required field '{field}'"
            
        if not val:
            # Optional field is empty, save as None
            validated[field] = None
            continue
            
        # Type conversions
        try:
            if field_type == "int":
                # Ensure it's a valid integer
                validated[field] = int(val)
            elif field_type == "float":
                # Ensure it's a valid float
                validated[field] = float(val)
            else:
                # String field
                validated[field] = val
        except ValueError:
            return False, None, f"Invalid type for field '{field}' (expected {field_type})"
            
    return True, validated, None

class QuarantineManager:
    """
    Manages writing quarantined rows to a CSV file.
    Lazily creates the file only when the first invalid row is encountered.
    """
    def __init__(self, quarantine_dir: str, run_id: str):
        self.quarantine_dir = quarantine_dir
        self.run_id = run_id
        self.file_path = os.path.join(
            self.quarantine_dir, 
            f"quarantine_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{self.run_id[:8]}.csv"
        )
        self.file = None
        self.writer = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.file:
            self.file.close()
            logger.info(f"Invalid rows written to quarantine file: {self.file_path}")

    def quarantine_row(self, raw_row: Dict[str, str], reason: str):
        """
        Quarantines a row by writing it to the quarantine CSV.
        Creates the file and writes the header if it hasn't been created yet.
        """
        if not self.file:
            # Ensure parent directories exist
            os.makedirs(self.quarantine_dir, exist_ok=True)
            self.file = open(self.file_path, mode="w", newline="", encoding="utf-8")
            
            # The header includes all original keys in the row plus the quarantine reason
            headers = list(raw_row.keys())
            if "quarantine_reason" not in headers:
                headers.append("quarantine_reason")
                
            self.writer = csv.DictWriter(self.file, fieldnames=headers)
            self.writer.writeheader()

        # Prepare the quarantined row copy
        row_copy = dict(raw_row)
        row_copy["quarantine_reason"] = reason
        self.writer.writerow(row_copy)
```

### `code/tests/test_pipeline.py`

```py
"""
Unit tests for the modular ETL data pipeline.
"""

import os
import csv
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime

from pipeline import DataPipeline
from pipeline.validate import validate_row
from pipeline.ingest import get_file_hash

class TestDataPipeline(unittest.TestCase):
    def setUp(self):
        # Setup temp directories
        self.test_dir = tempfile.TemporaryDirectory()
        self.input_dir = os.path.join(self.test_dir.name, "input")
        self.quarantine_dir = os.path.join(self.test_dir.name, "quarantine")
        self.summary_dir = os.path.join(self.test_dir.name, "summaries")
        self.db_path = os.path.join(self.test_dir.name, "pipeline.db")
        
        os.makedirs(self.input_dir, exist_ok=True)
        os.makedirs(self.quarantine_dir, exist_ok=True)
        os.makedirs(self.summary_dir, exist_ok=True)

    def tearDown(self):
        self.test_dir.cleanup()

    def test_schema_validation(self):
        # Valid row
        valid_row = {
            "transaction_id": "TXN_001",
            "product_id": "PROD_ABC",
            "price": "99.954",
            "quantity": "5",
            "category": "Electronics"
        }
        is_valid, validated, error = validate_row(valid_row)
        self.assertTrue(is_valid)
        self.assertEqual(validated["transaction_id"], "TXN_001")
        self.assertEqual(validated["price"], 99.954)
        self.assertEqual(validated["quantity"], 5)
        self.assertEqual(validated["category"], "Electronics")
        self.assertIsNone(error)
        
        # Missing required field
        invalid_row_1 = {
            "transaction_id": "",
            "product_id": "PROD_ABC",
            "price": "99.954",
            "quantity": "5"
        }
        is_valid, validated, error = validate_row(invalid_row_1)
        self.assertFalse(is_valid)
        self.assertIn("Missing required field", error)
        self.assertIsNone(validated)
        
        # Invalid float
        invalid_row_2 = {
            "transaction_id": "TXN_002",
            "product_id": "PROD_ABC",
            "price": "not-a-float",
            "quantity": "5"
        }
        is_valid, validated, error = validate_row(invalid_row_2)
        self.assertFalse(is_valid)
        self.assertIn("Invalid type for field 'price'", error)
        
        # Invalid integer
        invalid_row_3 = {
            "transaction_id": "TXN_003",
            "product_id": "PROD_ABC",
            "price": "10.50",
            "quantity": "2.5"
        }
        is_valid, validated, error = validate_row(invalid_row_3)
        self.assertFalse(is_valid)
        self.assertIn("Invalid type for field 'quantity'", error)

    def test_pipeline_normalisation_and_sqlite_load(self):
        csv_data = [
            ["transaction_id", "product_id", "price", "quantity", "category"],
            ["TXN_001", "PROD_UPPERCASE", "19.999", "3", "CLOTHING"],
            ["TXN_002", "PROD_XYZ", "10.004", "1", ""]
        ]
        csv_path = os.path.join(self.input_dir, "test_data.csv")
        with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerows(csv_data)
            
        pipeline = DataPipeline(
            input_dir=self.input_dir,
            db_path=self.db_path,
            quarantine_dir=self.quarantine_dir,
            summary_dir=self.summary_dir
        )
        
        summary = pipeline.run()
        
        self.assertEqual(summary["total_rows_read"], 2)
        self.assertEqual(summary["valid_rows_processed"], 2)
        self.assertEqual(summary["quarantined_rows_count"], 0)
        self.assertEqual(summary["inserted_rows_count"], 2)
        self.assertEqual(summary["status"], "SUCCESS")
        
        # Verify normalization and DB loading
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT transaction_id, product_id, price, quantity, category FROM transactions ORDER BY transaction_id")
        rows = cursor.fetchall()
        conn.close()
        
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], ("TXN_001", "prod_uppercase", 20.0, 3, "clothing"))
        self.assertEqual(rows[1], ("TXN_002", "prod_xyz", 10.0, 1, None))

    def test_idempotent_loads_row_level(self):
        # Create transaction file
        csv_data = [
            ["transaction_id", "product_id", "price", "quantity", "category"],
            ["TXN_DUPE", "PROD_001", "15.50", "2", "Books"]
        ]
        csv_path = os.path.join(self.input_dir, "test_dupe.csv")
        with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerows(csv_data)
            
        pipeline = DataPipeline(
            input_dir=self.input_dir,
            db_path=self.db_path,
            quarantine_dir=self.quarantine_dir,
            summary_dir=self.summary_dir
        )
        
        # Run 1
        summary1 = pipeline.run()
        self.assertEqual(summary1["inserted_rows_count"], 1)
        
        # We manually clear the processed_files record to force re-reading the file,
        # but the transaction_id should still be blocked at the database row-level.
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM processed_files")
        conn.commit()
        conn.close()

        # Run 2
        summary2 = pipeline.run()
        self.assertEqual(summary2["total_rows_read"], 1)
        self.assertEqual(summary2["valid_rows_processed"], 1)
        self.assertEqual(summary2["inserted_rows_count"], 0) # 0 inserted because of row-level INSERT OR IGNORE

    def test_idempotent_loads_file_level(self):
        # Create transaction file
        csv_data = [
            ["transaction_id", "product_id", "price", "quantity", "category"],
            ["TXN_FILE_IDEM", "PROD_001", "15.50", "2", "Books"]
        ]
        csv_path = os.path.join(self.input_dir, "test_file_idem.csv")
        with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerows(csv_data)
            
        pipeline = DataPipeline(
            input_dir=self.input_dir,
            db_path=self.db_path,
            quarantine_dir=self.quarantine_dir,
            summary_dir=self.summary_dir
        )
        
        # Run 1 - processes the file
        summary1 = pipeline.run()
        self.assertEqual(summary1["files_processed"], ["test_file_idem.csv"])
        self.assertEqual(summary1["total_rows_read"], 1)
        
        # Run 2 - should skip the file because file hash matches processed_files
        summary2 = pipeline.run()
        self.assertEqual(summary2["files_processed"], [])
        self.assertEqual(summary2["total_rows_read"], 0)

    def test_validation_quarantine(self):
        csv_data = [
            ["transaction_id", "product_id", "price", "quantity", "category"],
            ["TXN_VALID", "PROD_A", "10.00", "1", "Food"],
            ["TXN_INVALID", "PROD_B", "invalid-price", "2", "Food"]
        ]
        csv_path = os.path.join(self.input_dir, "test_mixed.csv")
        with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerows(csv_data)
            
        pipeline = DataPipeline(
            input_dir=self.input_dir,
            db_path=self.db_path,
            quarantine_dir=self.quarantine_dir,
            summary_dir=self.summary_dir
        )
        
        summary = pipeline.run()
        self.assertEqual(summary["total_rows_read"], 2)
        self.assertEqual(summary["valid_rows_processed"], 1)
        self.assertEqual(summary["quarantined_rows_count"], 1)
        self.assertEqual(summary["inserted_rows_count"], 1)
        
        # Verify quarantine file
        q_files = os.listdir(self.quarantine_dir)
        self.assertEqual(len(q_files), 1)
        
        q_path = os.path.join(self.quarantine_dir, q_files[0])
        with open(q_path, mode="r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["transaction_id"], "TXN_INVALID")
        self.assertEqual(rows[0]["price"], "invalid-price")
        self.assertEqual(rows[0]["quarantine_reason"], "Invalid type for field 'price' (expected float)")

    def test_run_summary_json(self):
        pipeline = DataPipeline(
            input_dir=self.input_dir,
            db_path=self.db_path,
            quarantine_dir=self.quarantine_dir,
            summary_dir=self.summary_dir
        )
        summary = pipeline.run()
        run_id = summary["run_id"]
        
        summary_file = os.path.join(self.summary_dir, f"summary_{run_id}.json")
        self.assertTrue(os.path.exists(summary_file))
        
        with open(summary_file, mode="r", encoding="utf-8") as f:
            loaded = json.load(f)
            
        self.assertEqual(loaded["run_id"], run_id)
        self.assertEqual(loaded["status"], "SUCCESS")
        self.assertIn("duration_seconds", loaded)
        self.assertIn("files_processed", loaded)

if __name__ == "__main__":
    unittest.main()
```
