#!/usr/bin/env python3
"""Compute Cohen's κ for the hallucination hand-labelling validation.

Three κ values are reported (two-rater + heuristic triangulation):

  1. κ(rater1, rater2)   — inter-annotator agreement (human vs human)
  2. κ(rater1, heuristic) — rater 1 vs auditor's manifest_deriver
  3. κ(rater2, heuristic) — rater 2 vs auditor's manifest_deriver

All comparisons use a binary classification:
  0  = no hallucinations (on-spec)
  1+ = one or more hallucinations (off-spec)

This is the standard approach for validating a binary heuristic against
human judgement (Cohen 1960). The threshold for treating the hallucination
metric as inferential (not merely exploratory) is κ ≥ 0.6.

Usage:
    python scripts/compute_kappa.py

Reads:
    data/labels/hallucination_handlabels.csv       (rater 1)
    data/labels/hallucination_handlabels_rater2.csv (rater 2)
    data/reports/main_001.csv                       (heuristic values)

Outputs:
    Prints the three κ values, their interpretation, and a contingency
    table. Also writes data/labels/kappa_results.json for programmatic
    consumption.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
from sklearn.metrics import cohen_kappa_score, confusion_matrix

ROOT = Path(__file__).resolve().parent.parent
LABELS = ROOT / "data" / "labels"
REPORTS = ROOT / "data" / "reports"

RATER1_PATH = LABELS / "hallucination_handlabels.csv"
RATER2_PATH = LABELS / "hallucination_handlabels_rater2.csv"
HEURISTIC_PATH = REPORTS / "main_001.csv"

KAPPA_BANDS = [
    (0.81, 1.00, "almost perfect"),
    (0.61, 0.80, "substantial / good"),
    (0.41, 0.60, "moderate"),
    (0.21, 0.40, "fair"),
    (0.00, 0.20, "slight"),
    (-1.0, 0.00, "poor (below chance)"),
]

OUTPUT_PATH = LABELS / "kappa_results.json"


def interpret(k: float) -> str:
    """Landis & Koch (1977) interpretation."""
    for lo, hi, label in KAPPA_BANDS:
        if lo <= k <= hi:
            return label
    return "undefined"


def load_rater(path: Path, label: str) -> pd.DataFrame | None:
    if not path.exists():
        print(f"  ⚠  {label}: file not found at {path}")
        return None
    df = pd.read_csv(path)
    col = "n_hallucinated_handlabel"
    if col not in df.columns:
        print(f"  ⚠  {label}: missing column '{col}'")
        return None
    filled = df[col].notna()
    n_filled = filled.sum()
    if n_filled == 0:
        print(f"  ⚠  {label}: no labels filled in yet (0 / {len(df)} rows)")
        return None
    if n_filled < len(df):
        print(f"  ℹ  {label}: {n_filled} / {len(df)} rows labelled "
              f"({len(df) - n_filled} still empty)")
    df = df[filled].copy()
    df["binary"] = (df[col].astype(float) > 0).astype(int)
    return df[["run_id", col, "binary"]]


def load_heuristic() -> pd.DataFrame | None:
    if not HEURISTIC_PATH.exists():
        print(f"  ⚠  Heuristic: file not found at {HEURISTIC_PATH}")
        return None
    df = pd.read_csv(HEURISTIC_PATH)
    h = df[df["metric"] == "hallucinations"][["run_id", "value"]].copy()
    h["binary"] = (h["value"].astype(float) > 0).astype(int)
    return h


def report_kappa(name: str, y1: pd.Series, y2: pd.Series,
                 label1: str, label2: str) -> dict:
    """Compute and print one κ comparison."""
    k = cohen_kappa_score(y1, y2)
    band = interpret(k)
    cm = confusion_matrix(y1, y2, labels=[0, 1])

    print(f"\n{'─' * 60}")
    print(f"  {name}")
    print(f"{'─' * 60}")
    print(f"  Cohen's κ = {k:.3f}   ({band})")
    print(f"  N = {len(y1)}")
    print()
    print(f"  Contingency table:")
    print(f"  {'':>20} {label2}=0  {label2}=1")
    print(f"  {label1}=0  {cm[0][0]:>10}  {cm[0][1]:>10}")
    print(f"  {label1}=1  {cm[1][0]:>10}  {cm[1][1]:>10}")

    agreement = (y1 == y2).mean()
    print(f"\n  Raw agreement: {agreement:.1%}")
    print(f"  Threshold for inferential use: κ ≥ 0.60")
    status = "✅ PASS" if k >= 0.6 else "❌ below threshold"
    print(f"  Status: {status}")

    return {
        "name": name,
        "kappa": round(k, 4),
        "interpretation": band,
        "n": int(len(y1)),
        "raw_agreement": round(float(agreement), 4),
        "pass": k >= 0.6,
        "contingency_table": cm.tolist(),
    }


def main():
    print()
    print("=" * 60)
    print("  Cohen's κ — Hallucination Heuristic Validation")
    print("  Two-rater triangulated design")
    print("=" * 60)

    # ── Load all three sources ──────────────────────────────────
    print("\nLoading data...")
    r1 = load_rater(RATER1_PATH, "Rater 1")
    r2 = load_rater(RATER2_PATH, "Rater 2")
    heuristic = load_heuristic()

    if r1 is None and r2 is None:
        print("\n  Neither rater has labelled anything yet.")
        print("  Fill in the CSV files in data/labels/ and re-run.")
        sys.exit(1)

    results = []

    # ── 1. Inter-annotator: rater1 vs rater2 ────────────────────
    if r1 is not None and r2 is not None:
        merged_12 = r1.merge(r2, on="run_id", suffixes=("_r1", "_r2"),
                             how="inner")
        if len(merged_12) >= 10:
            res = report_kappa(
                "κ(Rater 1, Rater 2) — inter-annotator agreement",
                merged_12["binary_r1"], merged_12["binary_r2"],
                "R1", "R2",
            )
            results.append(res)
        else:
            print(f"\n  ⚠  Only {len(merged_12)} overlapping rows between "
                  f"raters (need ≥ 10).")

    # ── 2. Rater 1 vs heuristic ─────────────────────────────────
    if r1 is not None and heuristic is not None:
        merged_1h = r1.merge(heuristic, on="run_id", suffixes=("_r1", "_h"),
                             how="inner")
        if len(merged_1h) >= 10:
            res = report_kappa(
                "κ(Rater 1, Heuristic) — human vs auditor",
                merged_1h["binary_r1"], merged_1h["binary_h"],
                "R1", "Heuristic",
            )
            results.append(res)
        else:
            print(f"\n  ⚠  Only {len(merged_1h)} matched rows for "
                  f"rater 1 vs heuristic (need ≥ 10).")

    # ── 3. Rater 2 vs heuristic ─────────────────────────────────
    if r2 is not None and heuristic is not None:
        merged_2h = r2.merge(heuristic, on="run_id", suffixes=("_r2", "_h"),
                             how="inner")
        if len(merged_2h) >= 10:
            res = report_kappa(
                "κ(Rater 2, Heuristic) — human vs auditor",
                merged_2h["binary_r2"], merged_2h["binary_h"],
                "R2", "Heuristic",
            )
            results.append(res)
        else:
            print(f"\n  ⚠  Only {len(merged_2h)} matched rows for "
                  f"rater 2 vs heuristic (need ≥ 10).")

    # ── Summary ─────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print("  Summary")
    print(f"{'=' * 60}")
    if not results:
        print("  No κ values computed. Label more rows and re-run.")
    else:
        for r in results:
            status = "✅" if r["pass"] else "❌"
            print(f"  {status}  {r['name']}: κ = {r['kappa']:.3f} "
                  f"({r['interpretation']})")

        all_pass = all(r["pass"] for r in results)
        print()
        if all_pass:
            print("  ✅  All κ values ≥ 0.60 — hallucination metric is")
            print("     validated for inferential use in the dissertation.")
            print("     Update Chapter 4 §4.7 from 'planned' to 'reported'.")
        else:
            failing = [r["name"] for r in results if not r["pass"]]
            print("  ⚠  The following comparisons are below threshold:")
            for f in failing:
                print(f"     — {f}")
            print("     The hallucination metric should be reported as")
            print("     'exploratory only' unless these improve.")

    # ── Write JSON ──────────────────────────────────────────────
    if results:
        OUTPUT_PATH.write_text(json.dumps(results, indent=2) + "\n")
        print(f"\n  Results written to: {OUTPUT_PATH.relative_to(ROOT)}")

    print()


if __name__ == "__main__":
    main()
