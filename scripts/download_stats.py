"""Append today's PyPI download stats to evidence/download_stats.csv.

Run monthly (or from CI on a schedule). Uses pypistats.org — mirror-filtered
counts, so the numbers are conservative and defensible. One row per
(date, package): date, package, last_day, last_week, last_month.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

PACKAGES = ["ai-code-quality-auditor", "knowyouragenticai-receipts"]
OUT = Path(__file__).resolve().parent.parent / "evidence" / "download_stats.csv"


def fetch(package: str, retries: int = 3) -> dict:
    url = f"https://pypistats.org/api/packages/{package}/recent"
    req = urllib.request.Request(url, headers={"User-Agent": "kya-evidence-logger/1.0"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)["data"]
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                time.sleep(70)
                continue
            raise


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    new_file = not OUT.exists()
    today = dt.date.today().isoformat()
    have = set()
    if OUT.exists():
        with OUT.open() as f:
            have = {(row["date"], row["package"]) for row in csv.DictReader(f)}
    with OUT.open("a", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["date", "package", "last_day", "last_week", "last_month"])
        for i, pkg in enumerate(PACKAGES):
            if (today, pkg) in have:
                print(f"{today} {pkg}: already logged, skipping")
                continue
            if i:
                time.sleep(5)
            d = fetch(pkg)
            w.writerow([today, pkg, d["last_day"], d["last_week"], d["last_month"]])
            print(f"{today} {pkg}: day={d['last_day']} week={d['last_week']} month={d['last_month']}")
    print(f"appended to {OUT}")


if __name__ == "__main__":
    main()
