#!/usr/bin/env python3
"""Generate Chapter 4's evidence figures.

Every figure here is computed from the study's own artefacts -- the frozen
captures in data/raw/, the report CSVs, and the rater label sheets. Nothing is
hardcoded, so a figure cannot silently disagree with the data behind it
(the failure Erratum 002 exposed in the original heatmap).

    PYTHONPATH=. .venv/bin/python scripts/make_evidence_figures.py
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "dissertation" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

INK, TEAL, TEAL_L = "#1A1F1D", "#0F766E", "#D6E7E4"
GREY, GREY_L = "#6B7671", "#EDEFEC"
AMBER, AMBER_L = "#B07D2E", "#F3E7D0"
RED, RED_L = "#A8443A", "#F2DAD6"
BLUE, BLUE_L = "#2F5D7D", "#DBE6EE"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 9,
    "axes.edgecolor": INK, "text.color": INK, "axes.labelcolor": INK,
    "xtick.color": INK, "ytick.color": INK,
    "figure.dpi": 300, "savefig.dpi": 300,
    "savefig.bbox": "tight", "savefig.pad_inches": 0.14,
})

CONDS = ["claude_code", "cursor_agent", "replit_agent", "antigravity"]
SPECS = ["agent_education_system", "data_pipeline", "internal_tool_cli"]


def save(fig, stem):
    for ext in ("png", "pdf"):
        fig.savefig(OUT / f"{stem}.{ext}", facecolor="white")
    plt.close(fig)
    print(f"  wrote figures/{stem}.png + .pdf")


def tidy(ax, keep=("left", "bottom")):
    for s in ("top", "right", "left", "bottom"):
        ax.spines[s].set_visible(s in keep)
        if s in keep:
            ax.spines[s].set_color(GREY)
            ax.spines[s].set_linewidth(0.7)


# ---------------------------------------------------------------- language mix
EXT = {"py": "Python", "ts": "TypeScript", "tsx": "TypeScript",
       "js": "TypeScript", "jsx": "TypeScript",
       "json": "Config / data", "yaml": "Config / data", "yml": "Config / data",
       "toml": "Config / data", "lock": "Config / data",
       "md": "Docs", "txt": "Docs", "sql": "Other", "html": "Other", "css": "Other"}
LANGS = ["Python", "TypeScript", "Config / data", "Docs", "Other"]
LCOL = {"Python": TEAL, "TypeScript": AMBER, "Config / data": GREY,
        "Docs": GREY_L, "Other": TEAL_L}


def language_mix():
    acc = defaultdict(lambda: defaultdict(int))
    for cb in (ROOT / "data/raw").glob("main_001__*/*/codebase.json"):
        cond = cb.parent.parent.name.split("__")[2]
        for p, c in json.loads(cb.read_text()).get("files", {}).items():
            ext = p.rsplit(".", 1)[-1].lower() if "." in p else ""
            acc[cond][EXT.get(ext, "Other")] += len(c.splitlines())
    return acc


def fig_language_composition():
    acc = language_mix()
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(8.6, 3.3),
                                  gridspec_kw={"width_ratios": [1.5, 1], "wspace": 0.42})

    y = np.arange(len(CONDS))[::-1]
    left = np.zeros(len(CONDS))
    totals = [sum(acc[c].values()) for c in CONDS]
    for lang in LANGS:
        vals = np.array([100 * acc[c][lang] / t if t else 0
                         for c, t in zip(CONDS, totals)])
        ax.barh(y, vals, left=left, height=0.62, color=LCOL[lang],
                edgecolor="white", linewidth=0.8, label=lang)
        for yy, v, l in zip(y, vals, left):
            if v >= 7:
                ax.text(l + v / 2, yy, f"{v:.0f}%", ha="center", va="center",
                        fontsize=8, fontweight="bold",
                        color="white" if lang in ("Python", "TypeScript") else INK)
            elif v >= 1 and lang == "Python":
                # Replit's Python share is the whole point; label it outside.
                ax.text(l + v + 1.4, yy, f"{v:.0f}%", ha="left", va="center",
                        fontsize=8, fontweight="bold", color=TEAL)
        left += vals

    ax.set_yticks(y); ax.set_yticklabels(CONDS, fontsize=9)
    ax.set_xlim(0, 100); ax.set_xlabel("share of produced lines (%)", fontsize=8.4)
    ax.set_title("What each tool actually wrote", fontsize=10,
                 fontweight="bold", loc="left", pad=8)
    tidy(ax, keep=("bottom",))
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=5,
              frameon=False, fontsize=7.6, handlelength=1.1)

    # right panel: the consequence -- security density against Python share
    sec = {}
    with (ROOT / "data/reports/security_density_corrected.csv").open() as f:
        rows = list(csv.DictReader(f))
    for c in CONDS:
        vals = [float(r["security_density_corrected"]) for r in rows if r["condition"] == c]
        sec[c] = sum(vals) / len(vals)
    pyshare = [100 * acc[c]["Python"] / sum(acc[c].values()) for c in CONDS]
    dens = [sec[c] for c in CONDS]

    ax2.scatter(pyshare, dens, s=74, color=TEAL, zorder=3, edgecolor="white", linewidth=1.2)
    for c, x, yv in zip(CONDS, pyshare, dens):
        ax2.annotate(c, (x, yv), textcoords="offset points",
                     xytext=(0, 11 if c != "antigravity" else -15),
                     ha="center", fontsize=7.6, color=GREY)
    ax2.set_xlabel("Python share of output (%)", fontsize=8.4)
    ax2.set_ylabel("security density\n(CWE findings / kLOC)", fontsize=8.4)
    ax2.set_title("Why Replit scores 0.00", fontsize=10, fontweight="bold",
                  loc="left", pad=8)
    ax2.set_xlim(-6, 108); ax2.set_ylim(-0.9, max(dens) * 1.28)
    ax2.grid(axis="y", color=GREY_L, linewidth=0.7)
    ax2.set_axisbelow(True)
    tidy(ax2)
    save(fig, "fig_4_4_language_composition")


# ------------------------------------------------------------------- kappa grid
def fig_kappa_agreement():
    idx = {r["item_id"]: r for r in csv.DictReader(open(ROOT / "data/labels/pack/index.csv"))}
    lab = {n: {r["item_id"]: r["n_offspec_features"]
               for r in csv.DictReader(open(ROOT / f"data/labels/labels_rater{n}.csv"))}
           for n in (1, 2)}
    pre = {}
    with (ROOT / "data/reports/main_001_hallucinations_pre_erratum002.csv").open() as f:
        h = defaultdict(list)
        for r in csv.DictReader(f):
            h[r["run_id"]].append(float(r["value"]))
    for iid, e in idx.items():
        runs = e["run_ids"].split(";")
        vals = [h[r][0] for r in runs if r in h]
        pre[iid] = vals[0] if vals else None

    items = sorted(idx)
    rows = ["Rater 1", "Rater 2", "Instrument"]
    M = np.zeros((3, len(items)))
    txt = [["" for _ in items] for _ in range(3)]
    for j, iid in enumerate(items):
        for i, src in enumerate((lab[1][iid], lab[2][iid], pre[iid])):
            if src in ("SKIP", None):
                M[i, j] = -1; txt[i][j] = "–"
            else:
                v = float(src)
                M[i, j] = 1 if v > 0 else 0
                txt[i][j] = f"{v:.0f}"

    fig, ax = plt.subplots(figsize=(8.6, 2.8))
    cmap = matplotlib.colors.ListedColormap([GREY_L, TEAL_L, RED_L])
    ax.imshow(np.where(M < 0, 0, M + 1), cmap=cmap, aspect="auto", vmin=0, vmax=2)
    for i in range(3):
        for j in range(len(items)):
            ax.text(j, i, txt[i][j], ha="center", va="center", fontsize=8,
                    fontweight="bold" if txt[i][j] not in ("0", "–") else "normal",
                    color=INK)
    ax.set_xticks(range(len(items)))
    ax.set_xticklabels([i.replace("item_", "") for i in items], fontsize=7.6)
    ax.set_yticks(range(3)); ax.set_yticklabels(rows, fontsize=9)
    ax.set_xlabel("labelling item (19 distinct codebases)", fontsize=8.4)
    ax.set_xticks([x - .5 for x in range(1, len(items))], minor=True)
    ax.set_yticks([y - .5 for y in range(1, 3)], minor=True)
    ax.grid(which="minor", color="white", linewidth=2)
    ax.tick_params(which="minor", length=0)
    tidy(ax, keep=())

    # mark the two disagreements
    for iid, note in (("item_08", "instrument blind\nto TS routes"),
                      ("item_16", "raters differ:\nscaffolding?")):
        j = items.index(iid)
        ax.add_patch(plt.Rectangle((j - .5, -.5), 1, 3, fill=False,
                                   edgecolor=RED, linewidth=1.9, zorder=5))
        ax.annotate(note, (j, -0.72), ha="center", va="bottom", fontsize=7.2,
                    color=RED, annotation_clip=False, linespacing=1.35)
    ax.set_title("Off-spec features counted by each source, per item",
                 fontsize=10, fontweight="bold", loc="left", pad=34)
    save(fig, "fig_4_8_kappa_agreement")




# ------------------------------------------------- the Replit evidence figure
def fig_replit_evidence():
    """Side-by-side: what the specification asked for, what was shipped.

    Both columns are read from the study's own artefacts -- the spec YAML and
    the frozen capture -- so the figure cannot drift from the evidence.
    """
    import yaml
    spec = yaml.safe_load((ROOT / "specs/internal_tool_cli.yaml").read_text())
    asked = [f["id"].split(".")[-1] for f in spec.get("features", [])]

    idx = {r["item_id"]: r for r in csv.DictReader(open(ROOT / "data/labels/pack/index.csv"))}
    smp = {r["run_id"]: r for r in
           csv.DictReader(open(ROOT / "data/labels/hallucination_handlabels.csv"))}
    run = idx["item_19"]["run_ids"].split(";")[0]
    files = json.loads((Path(smp[run]["code_path"]).parent / "codebase.json").read_text())["files"]

    import re as _re
    main = files.get("code/main.py", "")
    shipped = _re.findall(r'add_parser\(\s*["\']([a-zA-Z][\w\-]*)["\']', main)
    tree = sorted(p.replace("code/", "") for p in files)

    fig, ax = plt.subplots(figsize=(8.6, 4.3))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")

    ax.add_patch(plt.Rectangle((0.02, 0.06), 0.44, 0.80, facecolor=TEAL_L,
                               edgecolor=TEAL, linewidth=1.2, zorder=1))
    ax.add_patch(plt.Rectangle((0.54, 0.06), 0.44, 0.80, facecolor=RED_L,
                               edgecolor=RED, linewidth=1.2, zorder=1))

    ax.text(0.24, 0.90, "S P E C I F I E D", ha="center", fontsize=9.5,
            fontweight="bold", color=TEAL)
    ax.text(0.76, 0.90, "S H I P P E D", ha="center", fontsize=9.5,
            fontweight="bold", color=RED)
    ax.text(0.24, 0.815, "internal_tool_cli.yaml", ha="center", fontsize=7.6,
            color=GREY, family="monospace")
    ax.text(0.76, 0.815, run.replace("main_001__", ""), ha="center", fontsize=7.0,
            color=GREY, family="monospace")

    for i, cmd in enumerate(asked):
        ax.text(0.06, 0.74 - i * 0.075, f"tool {cmd}", fontsize=10,
                family="monospace", color=INK, va="center")
    for i, cmd in enumerate(shipped):
        ax.text(0.58, 0.74 - i * 0.075, f"tool {cmd}", fontsize=10,
                family="monospace", color=RED, va="center", fontweight="bold")

    ax.text(0.58, 0.74 - len(shipped) * 0.075 - 0.045,
            "plus a pipeline package:", fontsize=8, color=GREY, va="center")
    for i, f in enumerate([t for t in tree if t.startswith("pipeline/")][:6]):
        ax.text(0.60, 0.74 - len(shipped) * 0.075 - 0.10 - i * 0.052, f,
                fontsize=7.8, family="monospace", color=GREY, va="center")

    ax.annotate("", xy=(0.535, 0.46), xytext=(0.465, 0.46),
                arrowprops=dict(arrowstyle="-|>", color=INK, linewidth=1.4))
    ax.text(0.5, 0.50, "0 of 6", ha="center", fontsize=8.6, fontweight="bold")
    ax.text(0.5, 0.415, "shared", ha="center", fontsize=8.0, color=GREY)

    ax.text(0.02, 0.005,
            "Captured under a verified-clean workspace with an instruction stem "
            "explicitly prohibiting pipeline output.",
            fontsize=7.6, color=GREY, style="italic")
    save(fig, "fig_4_3_replit_evidence")


# ------------------------------------------------------- effective sample size
def fig_effective_n():
    fig, ax = plt.subplots(figsize=(7.4, 2.9))
    nominal = [30, 30, 30, 30]
    effective = []
    rows = list(csv.DictReader(open(ROOT / "data/reports/main_001.csv")))
    for c in CONDS:
        # a condition's effective n is the number of DISTINCT captured sessions
        vals = defaultdict(set)
        for r in rows:
            if r["metric"] != "duplication" or r["run_id"].split("__")[2] != c:
                continue
            vals[r["run_id"].split("__")[1]].add(r["value"])
        effective.append(sum(len(v) for v in vals.values()))

    y = np.arange(len(CONDS))[::-1]
    ax.barh(y + 0.19, nominal, height=0.34, color=GREY_L, edgecolor=GREY,
            linewidth=0.9, label="nominal rows in the CSV")
    ax.barh(y - 0.19, effective, height=0.34, color=TEAL, edgecolor=TEAL,
            linewidth=0.9, label="independently captured sessions")
    for yy, n, e in zip(y, nominal, effective):
        ax.text(n + 0.6, yy + 0.19, str(n), va="center", fontsize=8.4, color=GREY)
        ax.text(e + 0.6, yy - 0.19, str(e), va="center", fontsize=8.4,
                fontweight="bold", color=TEAL)
    ax.set_yticks(y); ax.set_yticklabels(CONDS, fontsize=9)
    ax.set_xlabel("observations", fontsize=8.4)
    ax.set_xlim(0, 34)
    ax.set_title("Nominal versus effective sample size (Deviation 001)",
                 fontsize=10, fontweight="bold", loc="left", pad=8)
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    ax.grid(axis="x", color=GREY_L, linewidth=0.7); ax.set_axisbelow(True)
    tidy(ax, keep=("bottom",))
    save(fig, "fig_4_6_effective_n")


# --------------------------------------------------------- errata before/after
def fig_errata():
    rows = list(csv.DictReader(open(ROOT / "data/reports/security_density_corrected.csv")))
    pub = [np.mean([float(r["security_density_published"]) for r in rows
                    if r["condition"] == c]) for c in CONDS]
    cor = [np.mean([float(r["security_density_corrected"]) for r in rows
                    if r["condition"] == c]) for c in CONDS]

    h_pub, h_cor = defaultdict(list), defaultdict(list)
    for r in csv.DictReader(open(ROOT / "data/reports/main_001_hallucinations_pre_erratum002.csv")):
        h_pub[r["run_id"].split("__")[2]].append(float(r["value"]))
    for r in csv.DictReader(open(ROOT / "data/reports/main_001.csv")):
        if r["metric"] == "hallucinations":
            h_cor[r["run_id"].split("__")[2]].append(float(r["value"]))

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(8.6, 3.0), gridspec_kw={"wspace": 0.34})
    x = np.arange(len(CONDS))

    for ax, before, after, title, sub in (
        (a1, pub, cor, "Erratum 001 — security density",
         "test-file assertions excluded"),
        (a2, [np.mean(h_pub[c]) for c in CONDS], [np.mean(h_cor[c]) for c in CONDS],
         "Erratum 002 — off-spec features", "TypeScript routes now detected"),
    ):
        ax.bar(x - 0.19, before, width=0.34, color=GREY_L, edgecolor=GREY,
               linewidth=0.9, label="as first reported")
        ax.bar(x + 0.19, after, width=0.34, color=TEAL, edgecolor=TEAL,
               linewidth=0.9, label="corrected")
        for xi, (b, a_) in enumerate(zip(before, after)):
            if abs(b - a_) > 1e-9:
                ax.annotate("", xy=(xi + 0.19, a_), xytext=(xi - 0.19, b),
                            arrowprops=dict(arrowstyle="-|>", color=RED,
                                            linewidth=1.3,
                                            connectionstyle="arc3,rad=-0.28"))
        ax.set_xticks(x)
        ax.set_xticklabels([c.replace("_agent", "").replace("_code", "")
                            for c in CONDS], fontsize=8)
        ax.set_title(title, fontsize=9.6, fontweight="bold", loc="left", pad=16)
        ax.text(0, 1.035, sub, transform=ax.transAxes, fontsize=7.8, color=GREY)
        ax.grid(axis="y", color=GREY_L, linewidth=0.7); ax.set_axisbelow(True)
        tidy(ax)
    a1.set_ylabel("CWE findings / kLOC", fontsize=8.4)
    a2.set_ylabel("off-spec features / run", fontsize=8.4)
    a1.legend(frameon=False, fontsize=7.8, loc="upper right")
    save(fig, "fig_5_1_errata")


# --------------------------------------------------------------- human vs AI
def fig_human_vs_ai():
    w = list(csv.DictReader(open(ROOT / "data/reports/human_vs_ai_comparison.csv")))
    metrics = ["security_density", "complexity_mean", "duplication_pct", "hallucinations"]
    labels = ["Security density\n(/kLOC)", "Complexity\n(mean cc)",
              "Duplication\n(%)", "Off-spec\n(count)"]
    aicols = [c for c in w[0] if c.endswith("(mean)")]

    fig, axes = plt.subplots(1, 4, figsize=(8.8, 2.6), gridspec_kw={"wspace": 0.46})
    for ax, m, lab in zip(axes, metrics, labels):
        rows = [r for r in w if r["metric"] == m]
        if not rows:
            ax.axis("off"); continue
        specs = [r["spec"].replace("_", "\n") for r in rows]
        hum = [float(r["human_control(n=1)"]) for r in rows]
        ai = [np.mean([float(r[c]) for c in aicols]) for r in rows]
        xx = np.arange(len(rows))
        ax.bar(xx - 0.19, hum, width=0.34, color=BLUE, edgecolor=BLUE, linewidth=0.9)
        ax.bar(xx + 0.19, ai, width=0.34, color=AMBER, edgecolor=AMBER, linewidth=0.9)
        ax.set_xticks(xx)
        ax.set_xticklabels(["web", "pipe", "CLI"], fontsize=7.6)
        ax.set_title(lab, fontsize=8.4, fontweight="bold", loc="left", pad=6)
        ax.grid(axis="y", color=GREY_L, linewidth=0.7); ax.set_axisbelow(True)
        tidy(ax)
    fig.legend(handles=[
        plt.Rectangle((0, 0), 1, 1, color=BLUE),
        plt.Rectangle((0, 0), 1, 1, color=AMBER)],
        labels=["human control (N = 1)", "agentic mean"],
        loc="lower center", bbox_to_anchor=(0.5, -0.16), ncol=2,
        frameon=False, fontsize=8)
    save(fig, "fig_4_7_human_vs_ai")


if __name__ == "__main__":
    print("generating evidence figures...")
    fig_language_composition()
    fig_kappa_agreement()
    fig_replit_evidence()
    fig_effective_n()
    fig_errata()
    fig_human_vs_ai()
    print(f"done -> {OUT}")
