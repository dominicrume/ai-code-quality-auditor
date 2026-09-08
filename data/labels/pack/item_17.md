# item_17

**Specification:** `internal_tool_cli`  
**Covers 3 sampled run(s)** (identical code) — replayed capture

---

## What was asked for

These are the ONLY features the specification requested:

- **`cli.init`** — `tool init <project-name>` creates a project directory with a default config.json.
- **`cli.add`** — `tool add <key> <value>` appends a key/value pair to the project's config.json.
- **`cli.list`** — `tool list` prints every key/value pair in the project's config.json.
- **`cli.export`** — `tool export --format {json,yaml,toml}` writes the config to stdout in the chosen format.
- **`cli.validate`** — `tool validate` checks the config against a built-in JSON schema and exits non-zero on failure.
- **`cli.help`** — `tool --help` and `tool <subcommand> --help` print usage with all flags documented.

---

## Your task

Read the code below and count **how many distinct features, routes, endpoints or subcommands exist that are NOT in the list above**.

Count a feature once, however many files it spans. Do not count helpers, config, tests or imports — only things a user could invoke that nobody asked for.

Write your number in `labels_rater<N>.csv` on the row for `item_17`.

---

## The code (6 files, 753 lines)

### `code/README.md`

```md
# Data Pipeline CLI

A robust Python command-line tool that reads CSV files from a configurable directory, validates and normalises the data, loads it into a SQLite database, schedules daily execution, and exports execution summaries.

## Features

- **CSV Ingestion (`ingest.csv`)**: Reads CSV files from a configurable directory.
- **Schema Validation (`validate.schema`)**: Validates rows against a pre-declared column schema. Defective or invalid rows are rejected and written to a quarantined CSV file. No PII is logged in stdout or standard log files.
- **Transformation (`transform.normalise`)**: Automatically normalises text columns to lowercase and rounds numeric values to two decimal places.
- **SQLite Loading (`load.sqlite`)**: Inserts valid, normalised records into a local SQLite table (`transactions`).
- **Scheduler (`schedule.daily`)**: Schedules daily execution via `APScheduler` or a built-in time-sleep loop fallback.
- **Run Summary JSON Reporting (`report.run_summary`)**: Generates structured execution logs with row counts, duration, and status.

## Governance Rules

1. **No PII**: The default schema does not collect or log personally identifiable information. Any error logging redacts specific column content, logging only field names and type mismatches.
2. **Idempotent Loads**: The SQLite target uses the `transaction_id` column as a Primary Key. Re-running the pipeline on duplicate files uses `INSERT OR IGNORE` which guarantees that duplicate rows are not created.
3. **No External Calls**: The pipeline runs entirely locally. It does not perform network socket connections or contact any external API.

## Installation

Ensure you have Python 3 installed. You can optionally install project dependencies:

```bash
pip install -r requirements.txt
```

*Note: If `apscheduler` is not installed, the daily scheduler automatically falls back to standard-library intervals.*

## Usage

### Run ETL Once
Place your `.csv` files into the `input` directory (configurable) and run:

```bash
python main.py
```

### Options

- `--input-dir <path>`: Local input directory for reading CSV files (default: `input`)
- `--db-path <path>`: Local SQLite database file path (default: `pipeline.db`)
- `--quarantine-dir <path>`: Directory to write invalid/quarantined rows (default: `quarantine`)
- `--summary-dir <path>`: Directory to write JSON run summaries (default: `summaries`)
- `--schedule`: Run the pipeline in scheduler mode
- `--cron <cron_expr>`: Cron expression for scheduling (e.g. `0 0 * * *` for daily at midnight)
- `--time <HH:MM>`: Daily execution time (default: `00:00`)

### Run in Scheduler Mode
To run the scheduler daily at midnight:
```bash
python main.py --schedule --time 00:00
```

## Schema Format

The system validates against a transaction schema:
- `transaction_id` (string, required)
- `product_id` (string, required)
- `price` (float, required)
- `quantity` (int, required)
- `category` (string, optional)
```

### `code/main.py`

```py
#!/usr/bin/env python3
"""
CLI entrypoint for the data pipeline.
"""
import os
import sys
import argparse
import logging
from pipeline import DataPipeline
from scheduler import start_scheduler

def setup_logging():
    """Sets up a secure logger that does not output or log sensitive row information (PII)."""
    logger = logging.getLogger("data_pipeline")
    logger.setLevel(logging.INFO)
    
    # Avoid duplicate handlers if setup is called multiple times
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        # Professional, clear formatting
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger

def main():
    parser = argparse.ArgumentParser(
        description="ETL Data Pipeline CLI with scheduling, schema validation, and SQLite load."
    )
    
    # Configure directories and files
    parser.add_argument(
        "--input-dir",
        default="input",
        help="Local input directory for reading CSV files (default: 'input')"
    )
    parser.add_argument(
        "--db-path",
        default="pipeline.db",
        help="Local SQLite database file path (default: 'pipeline.db')"
    )
    parser.add_argument(
        "--quarantine-dir",
        default="quarantine",
        help="Directory to write invalid/quarantined rows (default: 'quarantine')"
    )
    parser.add_argument(
        "--summary-dir",
        default="summaries",
        help="Directory to write JSON run summaries (default: 'summaries')"
    )
    
    # Scheduling arguments
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Run the pipeline in scheduler mode"
    )
    parser.add_argument(
        "--cron",
        help="Cron expression for scheduling (e.g. '0 0 * * *' for daily at midnight)"
    )
    parser.add_argument(
        "--time",
        default="00:00",
        help="Daily execution time in HH:MM format (default: '00:00')"
    )
    
    args = parser.parse_args()
    
    logger = setup_logging()
    logger.info("Starting data_pipeline CLI application")
    
    # Initialise the pipeline
    pipeline = DataPipeline(
        input_dir=args.input_dir,
        db_path=args.db_path,
        quarantine_dir=args.quarantine_dir,
        summary_dir=args.summary_dir
    )
    
    if args.schedule:
        # Define the job execution closure
        def job():
            logger.info("Executing scheduled pipeline run...")
            try:
                summary = pipeline.run()
                logger.info(f"Pipeline finished. Status: {summary['status']}, Inserted: {summary['inserted_rows_count']}, Quarantined: {summary['quarantined_rows_count']}")
            except Exception as e:
                logger.error(f"Scheduled job encountered an error: {str(e)}")
        
        try:
            start_scheduler(job, cron_string=args.cron, schedule_time=args.time)
        except (KeyboardInterrupt, SystemExit):
            logger.info("Scheduler shutdown complete.")
    else:
        # Single execution run
        try:
            summary = pipeline.run()
            logger.info("Pipeline execution complete.")
            print(f"Run ID: {summary['run_id']}")
            print(f"Status: {summary['status']}")
            print(f"Total Rows Read: {summary['total_rows_read']}")
            print(f"Valid Rows: {summary['valid_rows_processed']}")
            print(f"Quarantined Rows: {summary['quarantined_rows_count']}")
            print(f"Loaded Rows: {summary['inserted_rows_count']}")
            print(f"Duration: {summary['duration_seconds']}s")
            
            if summary["status"] == "FAILED":
                sys.exit(1)
        except Exception as e:
            logger.error(f"Pipeline failed: {str(e)}")
            sys.exit(1)

if __name__ == "__main__":
    main()
```

### `code/pipeline.py`

```py
"""
Core ETL pipeline implementation.
"""
import os
import csv
import json
import uuid
import time
import sqlite3
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple

from schema import validate_row

# Set up logging - Ensure we do not log PII (No raw values, only counts/types/field names)
logger = logging.getLogger("data_pipeline")

class DataPipeline:
    def __init__(self, input_dir: str, db_path: str, quarantine_dir: str, summary_dir: str):
        self.input_dir = input_dir
        self.db_path = db_path
        self.quarantine_dir = quarantine_dir
        self.summary_dir = summary_dir
        
        # Ensure directories exist
        os.makedirs(self.input_dir, exist_ok=True)
        os.makedirs(self.quarantine_dir, exist_ok=True)
        os.makedirs(self.summary_dir, exist_ok=True)
        
        # Initialize SQLite database
        self._init_db()

    def _init_db(self):
        """Initializes the SQLite database and ensures the schema is set up."""
        logger.info(f"Initializing SQLite database at {self.db_path}")
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            # transaction_id is PRIMARY KEY to enforce row-level idempotency
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
            conn.commit()
        finally:
            conn.close()

    def run(self) -> Dict[str, Any]:
        """Runs the ETL pipeline on all CSV files in the input directory."""
        run_id = str(uuid.uuid4())
        start_time = time.time()
        start_timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        
        logger.info(f"Starting run {run_id} at {start_timestamp}")
        
        total_rows = 0
        valid_rows_count = 0
        quarantine_rows_count = 0
        loaded_rows_count = 0
        
        # Find all CSV files in the input directory
        csv_files = [f for f in os.listdir(self.input_dir) if f.lower().endswith(".csv")]
        
        # Prepare quarantine file for this run
        quarantine_file_path = os.path.join(
            self.quarantine_dir, f"quarantine_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{run_id[:8]}.csv"
        )
        
        quarantine_writer = None
        quarantine_file = None
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            for csv_filename in csv_files:
                file_path = os.path.join(self.input_dir, csv_filename)
                logger.info(f"Ingesting file: {csv_filename}")
                
                with open(file_path, mode="r", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    
                    # Clean headers to strip spaces or byte order marks
                    reader.fieldnames = [name.strip() for name in reader.fieldnames] if reader.fieldnames else []
                    
                    for raw_row in reader:
                        total_rows += 1
                        
                        # Validate the row against schema
                        is_valid, validated_row, error_reason = validate_row(raw_row)
                        
                        if not is_valid:
                            quarantine_rows_count += 1
                            # Open quarantine file lazily
                            if quarantine_file is None:
                                quarantine_file = open(quarantine_file_path, mode="w", newline="", encoding="utf-8")
                                # Write raw row headers plus error reason
                                fieldnames = list(raw_row.keys()) + ["quarantine_reason"]
                                quarantine_writer = csv.DictWriter(quarantine_file, fieldnames=fieldnames)
                                quarantine_writer.writeheader()
                            
                            # Add error reason and write to quarantine (Governance: No PII logging on stdout/logs)
                            quarantine_row = dict(raw_row)
                            quarantine_row["quarantine_reason"] = error_reason
                            quarantine_writer.writerow(quarantine_row)
                            continue
                        
                        # Transform / Normalise
                        # 1. Lowercase string columns (product_id, category if present)
                        if validated_row["product_id"]:
                            validated_row["product_id"] = validated_row["product_id"].lower()
                        if validated_row["category"]:
                            validated_row["category"] = validated_row["category"].lower()
                            
                        # 2. Round numeric columns to two decimal places
                        validated_row["price"] = round(validated_row["price"], 2)
                        
                        valid_rows_count += 1
                        
                        # Load: Write to SQLite with INSERT OR IGNORE for idempotency
                        processed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                        cursor.execute("""
                            INSERT OR IGNORE INTO transactions (
                                transaction_id, product_id, price, quantity, category, processed_at
                            ) VALUES (?, ?, ?, ?, ?, ?)
                        """, (
                            validated_row["transaction_id"],
                            validated_row["product_id"],
                            validated_row["price"],
                            validated_row["quantity"],
                            validated_row["category"],
                            processed_at
                        ))
                        
                        if cursor.rowcount > 0:
                            loaded_rows_count += 1
            
            conn.commit()
            status = "SUCCESS"
        except Exception as e:
            conn.rollback()
            status = "FAILED"
            logger.error(f"Pipeline execution failed: {str(e)}") # Generic exception logging, no PII
            raise e
        finally:
            conn.close()
            if quarantine_file is not None:
                quarantine_file.close()
                logger.info(f"Invalid rows written to quarantine file: {quarantine_file_path}")
        
        end_time = time.time()
        duration = end_time - start_time
        end_timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        
        # Write JSON Summary
        summary = {
            "run_id": run_id,
            "start_time": start_timestamp,
            "end_time": end_timestamp,
            "duration_seconds": round(duration, 4),
            "total_rows_read": total_rows,
            "valid_rows_processed": valid_rows_count,
            "quarantined_rows_count": quarantine_rows_count,
            "inserted_rows_count": loaded_rows_count,
            "status": status
        }
        
        summary_file_path = os.path.join(self.summary_dir, f"summary_{run_id}.json")
        with open(summary_file_path, mode="w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
            
        logger.info(f"Run summary written to {summary_file_path}")
        return summary
```

### `code/scheduler.py`

```py
"""
Daily scheduler entrypoint for the ETL pipeline.
Supports APScheduler with cron expressions, falling back to a pure Python interval loop.
"""
import time
import logging
from datetime import datetime, timedelta
from typing import Callable, Optional

logger = logging.getLogger("data_pipeline.scheduler")

# Try importing APScheduler
try:
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    APS_AVAILABLE = True
except ImportError:
    APS_AVAILABLE = False

def run_standard_loop(job_func: Callable[[], None], schedule_time_str: str):
    """
    Fallback scheduler loop using standard library.
    Runs once per day at the specified time (format 'HH:MM').
    """
    logger.info(f"Using standard library fallback loop. Target run time: daily at {schedule_time_str}")
    
    try:
        hour, minute = map(int, schedule_time_str.split(":"))
    except ValueError:
        logger.error(f"Invalid time format '{schedule_time_str}'. Defaulting to '00:00'.")
        hour, minute = 0, 0

    while True:
        now = datetime.now()
        target_today = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        if now >= target_today:
            # If target time has already passed today, target is tomorrow
            target_run = target_today + timedelta(days=1)
        else:
            target_run = target_today
            
        sleep_seconds = (target_run - now).total_seconds()
        logger.info(f"Next scheduled run at {target_run.strftime('%Y-%m-%d %H:%M:%S')}. Sleeping for {sleep_seconds:.1f} seconds.")
        
        try:
            time.sleep(sleep_seconds)
            logger.info("Executing scheduled job...")
            job_func()
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user.")
            break
        except Exception as e:
            logger.error(f"Error during scheduled job run: {str(e)}")
            # Avoid tight looping on instant failure by sleeping a bit
            time.sleep(60)

def start_scheduler(job_func: Callable[[], None], cron_string: Optional[str] = None, schedule_time: str = "00:00"):
    """
    Starts the scheduler.
    If cron_string is provided, it uses the cron string to schedule the job.
    Otherwise, schedules it daily at the specified schedule_time (HH:MM).
    """
    if APS_AVAILABLE:
        logger.info("Starting scheduler using APScheduler.")
        scheduler = BlockingScheduler()
        
        if cron_string:
            try:
                # E.g. "0 0 * * *" or similar
                trigger = CronTrigger.from_crontab(cron_string)
                logger.info(f"Scheduling job using cron string: '{cron_string}'")
            except Exception as e:
                logger.error(f"Invalid cron string '{cron_string}': {str(e)}. Falling back to daily at {schedule_time}")
                trigger = CronTrigger(hour=int(schedule_time.split(":")[0]), minute=int(schedule_time.split(":")[1]))
        else:
            # Daily schedule
            try:
                hour, minute = map(int, schedule_time.split(":"))
                trigger = CronTrigger(hour=hour, minute=minute)
                logger.info(f"Scheduling job to run daily at {schedule_time}")
            except Exception as e:
                logger.error(f"Invalid time format '{schedule_time}': {str(e)}. Defaulting to daily at 00:00")
                trigger = CronTrigger(hour=0, minute=0)
                
        scheduler.add_job(job_func, trigger)
        
        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("APScheduler stopped by user.")
    else:
        logger.warning("APScheduler is not installed. Falling back to the built-in time loop.")
        if cron_string:
            logger.warning("Cron strings are not supported in fallback mode. Job will default to run daily.")
        run_standard_loop(job_func, schedule_time)
```

### `code/schema.py`

```py
"""
Schema definitions and validator logic for the ETL pipeline.
"""
from typing import Dict, Any, Tuple, Optional

# Declared Column Schema
# Maps field names to their configuration: type and whether they are required.
# Note: The schema is structured to ensure that no PII is requested, stored, or processed.
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
    
    Args:
        row: A dictionary representing the raw input row (strings from CSV).
        
    Returns:
        A tuple of (is_valid, validated_row, error_reason).
        If is_valid is False, validated_row is None and error_reason is a description of the failure.
    """
    validated = {}
    
    # 1. Check for unexpected extra columns (or mismatch)
    # We do a lenient match but ensure required fields exist and are validated.
    
    for field, rules in COLUMN_SCHEMA.items():
        val = row.get(field, "").strip()
        is_required = rules["required"]
        field_type = rules["type"]
        
        # Check required fields
        if is_required and not val:
            # Governance: Do not include the actual row values in the error reason to prevent logging PII
            return False, None, f"Missing required field '{field}'"
        
        if not val:
            # Optional field is empty, store as None or empty string depending on preference.
            # For category, let's keep it empty or None.
            validated[field] = None
            continue
            
        # Type conversions
        try:
            if field_type == "int":
                # Check that it's a valid integer
                validated[field] = int(val)
            elif field_type == "float":
                # Check that it's a valid float
                validated[field] = float(val)
            else:
                # String type, keep as is
                validated[field] = val
        except ValueError:
            # Governance: Do not include the actual value in the log/error to prevent PII exposure
            return False, None, f"Invalid type for field '{field}' (expected {field_type})"
            
    return True, validated, None
```

### `code/tests/test_pipeline.py`

```py
"""
Unit tests for the ETL pipeline.
"""
import os
import csv
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime

from schema import validate_row
from pipeline import DataPipeline
from scheduler import run_standard_loop

class TestDataPipeline(unittest.TestCase):
    def setUp(self):
        # Create temporary directories for testing
        self.test_dir = tempfile.TemporaryDirectory()
        self.input_dir = os.path.join(self.test_dir.name, "input")
        self.quarantine_dir = os.path.join(self.test_dir.name, "quarantine")
        self.summary_dir = os.path.join(self.test_dir.name, "summaries")
        self.db_path = os.path.join(self.test_dir.name, "pipeline.db")
        
        os.makedirs(self.input_dir, exist_ok=True)
        os.makedirs(self.quarantine_dir, exist_ok=True)
        os.makedirs(self.summary_dir, exist_ok=True)

    def tearDown(self):
        # Clean up temporary directories
        self.test_dir.cleanup()

    def test_schema_validation(self):
        # Test valid row
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
        
        # Test missing required field
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
        
        # Test invalid float type
        invalid_row_2 = {
            "transaction_id": "TXN_002",
            "product_id": "PROD_ABC",
            "price": "not-a-float",
            "quantity": "5"
        }
        is_valid, validated, error = validate_row(invalid_row_2)
        self.assertFalse(is_valid)
        self.assertIn("Invalid type for field 'price'", error)
        
        # Test invalid integer type
        invalid_row_3 = {
            "transaction_id": "TXN_003",
            "product_id": "PROD_ABC",
            "price": "10.50",
            "quantity": "2.5" # floats are not valid integers
        }
        is_valid, validated, error = validate_row(invalid_row_3)
        self.assertFalse(is_valid)
        self.assertIn("Invalid type for field 'quantity'", error)

    def test_pipeline_normalisation_and_sqlite_load(self):
        # Create a sample valid CSV file
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
        
        # Verify counts in summary
        self.assertEqual(summary["total_rows_read"], 2)
        self.assertEqual(summary["valid_rows_processed"], 2)
        self.assertEqual(summary["quarantined_rows_count"], 0)
        self.assertEqual(summary["inserted_rows_count"], 2)
        self.assertEqual(summary["status"], "SUCCESS")
        
        # Verify SQLite data (normalisation: lowercasing and rounding)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT transaction_id, product_id, price, quantity, category FROM transactions ORDER BY transaction_id")
        rows = cursor.fetchall()
        conn.close()
        
        self.assertEqual(len(rows), 2)
        # TXN_001 product_id "PROD_UPPERCASE" -> "prod_uppercase"
        # price 19.999 rounded -> 20.0
        # category "CLOTHING" -> "clothing"
        self.assertEqual(rows[0], ("TXN_001", "prod_uppercase", 20.0, 3, "clothing"))
        # TXN_002 price 10.004 rounded -> 10.00
        # category empty -> None
        self.assertEqual(rows[1], ("TXN_002", "prod_xyz", 10.0, 1, None))

    def test_idempotent_loads(self):
        # Create a sample CSV file
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
        
        # Run 2 on same input
        summary2 = pipeline.run()
        # Should process 1 row but insert 0 because of idempotent unique constraint
        self.assertEqual(summary2["total_rows_read"], 1)
        self.assertEqual(summary2["valid_rows_processed"], 1)
        self.assertEqual(summary2["inserted_rows_count"], 0)
        
        # Verify only 1 record exists in DB
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM transactions WHERE transaction_id = 'TXN_DUPE'")
        count = cursor.fetchone()[0]
        conn.close()
        self.assertEqual(count, 1)

    def test_validation_quarantine(self):
        # Create CSV with 1 valid row and 1 invalid row
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
        
        # Check that quarantine file was generated and contains the invalid row
        quarantine_files = os.listdir(self.quarantine_dir)
        self.assertEqual(len(quarantine_files), 1)
        
        quarantine_path = os.path.join(self.quarantine_dir, quarantine_files[0])
        with open(quarantine_path, mode="r", newline="", encoding="utf-8") as f:
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
            loaded_summary = json.load(f)
            
        self.assertEqual(loaded_summary["run_id"], run_id)
        self.assertEqual(loaded_summary["status"], "SUCCESS")
        self.assertIn("duration_seconds", loaded_summary)
        self.assertIn("start_time", loaded_summary)
        self.assertIn("end_time", loaded_summary)
        
if __name__ == "__main__":
    unittest.main()
```
