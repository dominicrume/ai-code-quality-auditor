#!/usr/bin/env python3
"""Figures 4.1 and 4.2, redrawn from the corrected report.

These two were previously exported from the analysis notebook with matplotlib
defaults, and they were still showing pre-Erratum-001 security densities, which
put them in direct contradiction with Table 4.1 on the same page. They are now
generated from data/reports/main_001.csv at build time, in the palette used by
every other figure, and they carry a colour per condition so the two can be read
together.

    .venv/bin/python scripts/make_chapter4_figures.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "dissertation" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

INK, GREY, GREY_L = "#1A1F1D", "#6B7671", "#EDEFEC"
TEAL, BLUE, AMBER, RED = "#0F766E", "#2F5D7D", "#B07D2E", "#A8443A"

COND = {                     # one colour per condition, used in both figures
    "claude_code":  TEAL,
    "cursor_agent": BLUE,
    "antigravity":  AMBER,
    "replit_agent": RED,
}
ORDER = ["claude_code", "cursor_agent", "antigravity", "replit_agent"]
# Captured once per cell and replayed (Deviation 001), so within-cell spread is
# a property of the replay, not of the tool. Marked so the reader is not invited
# to read a flat column as a stable measurement.
REPLAYED = {"antigravity", "replit_agent"}

METRICS = [
    ("hallucinations",   "Off-spec features",   "count per run"),
    ("duplication_pct",  "Duplication",         "% of source lines"),
    ("security_density", "Security density",    "CWE findings / kLOC"),
    ("complexity_mean",  "Complexity",          "mean cyclomatic"),
]

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 9,
    "axes.edgecolor": INK, "text.color": INK, "axes.labelcolor": INK,
    "xtick.color": INK, "ytick.color": INK,
    "figure.dpi": 300, "savefig.dpi": 300,
    "savefig.bbox": "tight", "savefig.pad_inches": 0.14,
})


def save(fig, stem):
    for ext in ("png", "pdf"):
        fig.savefig(OUT / f"{stem}.{ext}", facecolor="white")
    plt.close(fig)
    print(f"  wrote figures/{stem}.png + .pdf")


def load() -> pd.DataFrame:
    df = pd.read_csv(ROOT / "data/reports/main_001.csv")
    df["condition"] = df.run_id.str.split("__").str[2]
    return df[df.condition.isin(ORDER)]


def boot_ci(v, n=10000, seed=7):
    """Bootstrap 95% interval on the mean. Zero-variance cells return a point."""
    v = np.asarray(v, dtype=float)
    if np.allclose(v, v[0]):
        return v.mean(), v.mean(), v.mean()
    rng = np.random.default_rng(seed)
    means = rng.choice(v, (n, v.size), replace=True).mean(axis=1)
    return v.mean(), np.percentile(means, 2.5), np.percentile(means, 97.5)


def tidy(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GREY); ax.spines[s].set_linewidth(0.7)


def fig_means():
    df = load()
    fig, axes = plt.subplots(1, 4, figsize=(8.8, 2.9),
                             gridspec_kw={"wspace": 0.46})
    for ax, (metric, title, unit) in zip(axes, METRICS):
        ys = np.arange(len(ORDER))[::-1]
        for y, cond in zip(ys, ORDER):
            v = df[(df.metric == metric) & (df.condition == cond)]["value"].values
            if not len(v):
                continue
            m, lo, hi = boot_ci(v)
            ax.plot([lo, hi], [y, y], color=COND[cond], linewidth=2.4,
                    solid_capstyle="round", zorder=2, alpha=.55)
            ax.scatter([m], [y], s=54, color=COND[cond], zorder=3,
                       edgecolor="white", linewidth=1.1)
            ax.text(m, y + 0.30, f"{m:.2f}", ha="center", va="bottom",
                    fontsize=8, fontweight="bold", color=COND[cond])
        ax.set_yticks(ys)
        ax.set_yticklabels([c.replace("_agent", "").replace("_code", "")
                            for c in ORDER], fontsize=8.4)
        ax.set_title(title, fontsize=9.6, fontweight="bold", loc="left", pad=17)
        ax.text(0, 1.05, unit, transform=ax.transAxes, fontsize=7.6, color=GREY)
        ax.set_ylim(-0.7, len(ORDER) - 0.25)
        ax.grid(axis="x", color=GREY_L, linewidth=0.7)
        ax.set_axisbelow(True)
        ax.margins(x=0.20)
        tidy(ax)
    save(fig, "fig_4_1_condition_means")


def fig_spread():
    """Distribution per condition. The point of this figure is what is missing:
    two conditions have no spread at all, because their cells are replays."""
    df = load()
    fig, axes = plt.subplots(1, 4, figsize=(8.8, 3.1),
                             gridspec_kw={"wspace": 0.46})
    rng = np.random.default_rng(3)
    for ax, (metric, title, unit) in zip(axes, METRICS):
        for x, cond in enumerate(ORDER):
            v = df[(df.metric == metric) & (df.condition == cond)]["value"].values
            if not len(v):
                continue
            replay = cond in REPLAYED
            jitter = rng.normal(0, 0.075, v.size)
            ax.scatter(np.full(v.size, x) + jitter, v, s=17,
                       color="none" if replay else COND[cond],
                       alpha=.75 if replay else .30,
                       edgecolor=COND[cond] if replay else "none",
                       linewidth=0.8, zorder=2)
            ax.plot([x - 0.26, x + 0.26], [v.mean()] * 2, color=COND[cond],
                    linewidth=2.0, zorder=3)
        ax.set_xticks(range(len(ORDER)))
        ax.set_xticklabels([c.replace("_agent", "").replace("_code", "")
                            + ("\u2020" if c in REPLAYED else "")
                            for c in ORDER], fontsize=8, rotation=32, ha="right")
        ax.set_title(title, fontsize=9.6, fontweight="bold", loc="left", pad=17)
        ax.text(0, 1.045, unit, transform=ax.transAxes, fontsize=7.6, color=GREY)
        ax.grid(axis="y", color=GREY_L, linewidth=0.7)
        ax.set_axisbelow(True)
        ax.margins(y=0.22)
        tidy(ax)
    fig.text(0.5, -0.10,
             "\u2020 captured once per cell and replayed ten times "
             "(Deviation 001): the ten points are one measurement, drawn open. "
             "Filled points are independent captures.",
             ha="center", fontsize=7.8, color=GREY)
    save(fig, "fig_4_2_distribution")


if __name__ == "__main__":
    print("redrawing chapter 4 figures from the corrected report...")
    fig_means()
    fig_spread()
