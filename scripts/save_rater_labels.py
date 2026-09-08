#!/usr/bin/env python3
"""Write a rater's results into data/labels/labels_rater<N>.csv.

Two routes reach this script, because the two rater pages differ:

  * Rater 1's page is organisation-internal and declares the `db`
    capability, so its answers are recorded server-side and Claude reads
    them back directly -- pass them here as JSON on stdin.
  * Rater 2's page is shared publicly, which the db capability forbids,
    so it keeps answers in the browser and the rater pastes the CSV
    back -- pass that here as CSV on stdin.

Either way the file written is identical, so compute_kappa.py does not
care which route a rater used.

Usage:
    python scripts/save_rater_labels.py 1 < results.csv
    python scripts/save_rater_labels.py 2 --csv < results.csv
"""
from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LABELS = ROOT / "data" / "labels"
PACK_INDEX = LABELS / "pack" / "index.csv"

COLUMNS = ["item_id", "spec_name", "n_offspec_features", "notes"]


def from_csv(text: str) -> dict[str, str]:
    rows = list(csv.DictReader(io.StringIO(text.strip())))
    if not rows or "item_id" not in rows[0]:
        sys.exit("input does not look like the tool's CSV (no item_id column)")
    return {r["item_id"]: (r.get("n_offspec_features") or "").strip() for r in rows}


def from_json(text: str) -> dict[str, str]:
    """Accept the db documents, either bare or wrapped as {id, data}."""
    docs = json.loads(text)
    if isinstance(docs, dict):
        docs = list(docs.values())
    out = {}
    for d in docs:
        body = d.get("data", d) if isinstance(d, dict) else {}
        item = body.get("item_id")
        if not item or item.startswith("__"):
            continue
        out[item] = str(body.get("n_offspec", "")).strip()
    if not out:
        sys.exit("no usable label documents found in the JSON")
    return out


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1 or args[0] not in ("1", "2"):
        sys.exit("usage: save_rater_labels.py <1|2> [--csv] < input")
    rater = args[0]
    force_csv = "--csv" in sys.argv

    text = sys.stdin.read().strip()
    if not text:
        sys.exit("nothing on stdin")
    got = from_csv(text) if (force_csv or not text.lstrip().startswith(("[", "{"))) \
        else from_json(text)

    index = list(csv.DictReader(open(PACK_INDEX)))
    out_path = LABELS / f"labels_rater{rater}.csv"

    written, missing = 0, []
    with out_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for e in index:
            item = e["item_id"]
            val = got.get(item, "")
            if val == "":
                missing.append(item)
            else:
                written += 1
            w.writerow({"item_id": item, "spec_name": e["spec_name"],
                        "n_offspec_features": val, "notes": ""})

    print(f"wrote {out_path}  ({written}/{len(index)} items labelled)")
    if missing:
        print(f"  still empty: {', '.join(missing)}")
    else:
        print("  complete — run: python scripts/compute_kappa.py")


if __name__ == "__main__":
    main()
