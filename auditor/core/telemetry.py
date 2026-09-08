import os
import threading
import urllib.request
import urllib.error
import json
import uuid
from typing import Any

from auditor.core.scan import ScanResult

TELEMETRY_URL = os.environ.get("AUDITOR_TELEMETRY_URL", "https://api.veritaport.co.uk/telemetry")

def ping_telemetry(result: ScanResult) -> None:
    """Send anonymised telemetry data about the scan in the background."""
    # Don't block the CLI/scan process waiting for network requests.
    t = threading.Thread(target=_send, args=(result,), daemon=True)
    t.start()

def _send(result: ScanResult) -> None:
    payload = {
        "event": "scan_completed",
        "project_name": result.path.name,
        "files": result.file_count,
        "total_loc": result.total_loc,
        "python_files": result.python_files,
        "spec_name": result.spec_name,
        "metrics": {
            o.name: ({"value": o.value, "unit": o.unit, "band": o.band}
                     if o.applicable else {"skipped": o.skipped_reason})
            for o in result.outcomes
        }
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            TELEMETRY_URL,
            data=data,
            headers={"Content-Type": "application/json", "User-Agent": "Auditor-CLI/0.4.1"}
        )
        # Timeout quickly to avoid hanging if the telemetry endpoint is down
        with urllib.request.urlopen(req, timeout=2.0) as f:
            pass
    except Exception:
        pass  # Telemetry failures must never break the main app workflow
