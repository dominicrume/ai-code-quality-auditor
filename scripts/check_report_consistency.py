#!/usr/bin/env python3
"""Assert every report agrees with the figures the dissertation quotes.

Erratum 001 was applied to the chapter and to two derived reports but not to
main_001.csv, and later not to main_001_plus_human.csv either, which is the
report the public dashboard serves. Each time the inconsistency was invisible
because nothing compared the files to each other. This does.

Files named *_pre_erratum* are deliberate historical snapshots and are exempt.

    .venv/bin/python scripts/check_report_consistency.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "data" / "reports"

# The condition means reported in Table 4.1, after both errata.
EXPECTED = {
    ("security_density", "claude_code"): 9.65,
    ("security_density", "cursor_agent"): 5.93,
    ("security_density", "antigravity"): 1.47,
    ("security_density", "replit_agent"): 0.00,
    ("hallucinations", "claude_code"): 0.00,
    ("hallucinations", "cursor_agent"): 0.17,
    ("hallucinations", "antigravity"): 0.33,
    ("hallucinations", "replit_agent"): 1.33,
}
TOL = 0.02


def condition_column(df: pd.DataFrame):
    cols = set(df.columns)
    if {"run_id", "metric", "value"} <= cols:
        return df.run_id.str.split("__").str[2]
    if {"condition", "metric", "value"} <= cols:
        return df["condition"]
    return None


def main() -> int:
    problems = []
    for p in sorted(REPORTS.glob("*.csv")):
        if "pre_erratum" in p.name:
            continue
        df = pd.read_csv(p)
        cond = condition_column(df)
        if cond is None:
            continue
        df = df.assign(_cond=cond)
        for (metric, c), want in EXPECTED.items():
            g = df[(df.metric == metric) & (df._cond == c)]["value"]
            if not len(g):
                continue
            got = float(g.mean())
            if abs(got - want) > TOL:
                problems.append(f"{p.name}: {metric}/{c} is {got:.2f}, "
                                f"Table 4.1 reports {want:.2f}")
        print(f"  {'FAIL' if any(p.name in x for x in problems) else 'ok  '} {p.name}")

    if problems:
        print("\nreports disagree with the dissertation:")
        for x in problems:
            print(f"   {x}")
        return 1
    print("\nevery report agrees with Table 4.1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
