#!/usr/bin/env python3
"""Build the second labelling pack: two constructs, fresh items, known controls.

Why a second study
------------------
Study 001 validated one construct — *addition* ("what did the agent ship that
nobody asked for?"). `docs/FINDING_001_shape_substitution.md` shows that
construct is blind to *substitution*: given the CLI brief, `antigravity` shipped
a scheduled pipeline with no subcommands, added nothing, and scored 0.00 —
the same as the two conditions that built the CLI correctly. Both raters scored
it 0 and were right to, because the protocol asked about additions.

This pack asks two questions instead of one, so the two constructs can be
validated separately.

The sampling problem, stated plainly
------------------------------------
Under Deviation 001 the IDE-bound conditions were captured once per cell and
replayed, so `replit_agent` and `antigravity` contribute exactly one distinct
artefact each per specification — and the raters have already seen all of them.
**There is no fresh naturalistic material in the two cells where shape mismatch
actually fires.** A pack drawn only from unseen artefacts would therefore
contain no positive case for the shape question, and a κ computed on it would
measure specificity alone while looking like validation.

The design answers this with two blocks:

* **Block A — naturalistic.** Distinct artefacts from `claude_code` and
  `cursor_agent` that appear in no item of pack 001, each paired with its own
  specification. These carry the real κ for the addition construct on unseen
  data, and test whether shape detection wrongly fires on correct work.

* **Block B — positive controls.** Unseen artefacts deliberately paired with a
  *different* specification. Ground truth is known by construction: the
  deliverable is not the kind of thing that brief asked for. These test whether
  the shape question can detect substitution at all.

Raters are not told which block an item belongs to, and the blocks are
interleaved by the shuffle. Block membership is recorded in the index, which
raters do not receive.

What this design can and cannot establish is written out in
`data/labels/pack_002/DESIGN.md`. In short: it can validate the addition
construct on fresh data, establish specificity for the shape construct, and
demonstrate sensitivity against known controls. It cannot establish sensitivity
on *naturalistic* substitution, because no unseen naturalistic substitution
exists in this corpus. That requires new captures from the IDE-bound tools.
"""
from __future__ import annotations

import csv
import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data/raw"
PACK_001_INDEX = ROOT / "data/labels/pack/index.csv"
OUT = ROOT / "data/labels/pack_002"

SEED = 20260913  # fixed so the pack is reproducible
N_NATURALISTIC = 24
N_CONTROLS = 6

# A control pairs a codebase with a brief of a deliberately different shape.
CONTROL_PAIRING = {
    "internal_tool_cli": "data_pipeline",
    "data_pipeline": "agent_education_system",
    "agent_education_system": "internal_tool_cli",
}


def spec_features(spec_name: str) -> list[dict]:
    p = ROOT / "specs" / f"{spec_name}.yaml"
    return yaml.safe_load(p.read_text()).get("features", []) if p.exists() else []


def seen_run_ids() -> set[str]:
    seen: set[str] = set()
    if not PACK_001_INDEX.exists():
        return seen
    for row in csv.DictReader(PACK_001_INDEX.open()):
        seen.update(r.strip() for r in row["run_ids"].split(";") if r.strip())
    return seen


def load_codebase(run_id: str) -> tuple[str, dict] | None:
    cond = run_id.replace("main_001__", "").rsplit("__rep", 1)[0].rsplit("__", 1)[-1]
    p = RAW / run_id / cond / "codebase.json"
    if not p.exists():
        return None
    files = json.loads(p.read_text()).get("files", {})
    return cond, files


def digest(files: dict) -> str:
    return hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()[:12]


def collect_fresh() -> list[dict]:
    """Distinct artefacts that appear in no item of pack 001."""
    seen = seen_run_ids()
    seen_digests: set[str] = set()
    for run_id in seen:
        loaded = load_codebase(run_id)
        if loaded:
            seen_digests.add(digest(loaded[1]))

    best: dict[str, dict] = {}
    for d in sorted(RAW.iterdir()):
        if not d.name.startswith("main_001__"):
            continue
        loaded = load_codebase(d.name)
        if not loaded:
            continue
        cond, files = loaded
        if not files:
            continue
        h = digest(files)
        if h in seen_digests or h in best:
            continue
        spec_name = d.name.replace("main_001__", "").rsplit(f"__{cond}__", 1)[0]
        best[h] = {
            "run_id": d.name, "condition": cond, "spec_name": spec_name,
            "files": files, "digest": h,
        }
    return list(best.values())


def render(item_id: str, spec_name: str, files: dict) -> str:
    feats = spec_features(spec_name)
    doc = [
        f"# {item_id}", "",
        f"**Specification:** `{spec_name}`", "",
        "---", "", "## What was asked for", "",
        "These are the ONLY things the specification requested:", "",
    ]
    for f in feats:
        doc.append(f"- **`{f['id']}`** — {f.get('description','')}")
    doc += [
        "", "---", "", "## Your task", "",
        "Answer **three** questions about the code below. Read the code first;",
        "the specification above is the only thing that was asked for.", "",
        "**Q1 — Addition.** How many distinct features, routes, endpoints or",
        "subcommands exist that are NOT in the list above?",
        "Count a feature once, however many files it spans. Do not count helpers,",
        "config, tests or imports — only things a user could invoke that nobody",
        "asked for. Write an integer.", "",
        "**Q2 — Kind.** Is this deliverable *the kind of thing* the brief asked",
        "for? A brief for a command-line tool answered with a command-line tool is",
        "`yes`, even if the subcommands are wrong or missing. A brief for a",
        "command-line tool answered with a scheduled data pipeline is `no`.",
        "Write `yes`, `no`, or `unsure`.", "",
        "**Q3 — Scaffolding (exploratory).** If the deliverable ships library,",
        "client or infrastructure code nobody asked for, is that *scope drift*",
        "(capability nobody requested) or *organisation* (internal structure)?",
        "Write `drift`, `organisation`, or `n/a` if it ships none.", "",
        "Record your answers in `labels_rater<N>_002.csv` on the row for",
        f"`{item_id}`. Answer from the code alone; do not run the tools.", "",
        "---", "", "## The code", "",
    ]
    for path, content in sorted(files.items()):
        doc += [f"### `{path}`", "", "```", content.rstrip(), "```", ""]
    return "\n".join(doc)


def main() -> int:
    fresh = collect_fresh()
    rng = random.Random(SEED)

    # Naturalistic block: stratify across (spec, condition) so no cell dominates.
    by_cell: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for item in fresh:
        by_cell[(item["spec_name"], item["condition"])].append(item)
    for v in by_cell.values():
        rng.shuffle(v)

    naturalistic: list[dict] = []
    cells = sorted(by_cell)
    while len(naturalistic) < N_NATURALISTIC and any(by_cell[c] for c in cells):
        for c in cells:
            if by_cell[c] and len(naturalistic) < N_NATURALISTIC:
                naturalistic.append(by_cell[c].pop())

    # Control block: remaining fresh artefacts, paired with a different brief.
    remaining = [i for i in fresh if i not in naturalistic]
    rng.shuffle(remaining)
    controls = []
    for item in remaining:
        if len(controls) >= N_CONTROLS:
            break
        wrong = CONTROL_PAIRING.get(item["spec_name"])
        if not wrong:
            continue
        controls.append({**item, "presented_spec": wrong})

    entries = (
        [{**i, "presented_spec": i["spec_name"], "block": "naturalistic"} for i in naturalistic]
        + [{**c, "block": "control"} for c in controls]
    )
    rng.shuffle(entries)  # interleave so block membership is not guessable

    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("item_*.md"):
        old.unlink()

    index_rows = []
    for i, e in enumerate(entries, 1):
        item_id = f"item_{i:02d}"
        (OUT / f"{item_id}.md").write_text(render(item_id, e["presented_spec"], e["files"]))
        index_rows.append({
            "item_id": item_id,
            "block": e["block"],
            "presented_spec": e["presented_spec"],
            "true_spec": e["spec_name"],
            "condition": e["condition"],
            "run_id": e["run_id"],
            "digest": e["digest"],
            "n_files": len(e["files"]),
            "expected_kind": "no" if e["block"] == "control" else "yes",
        })

    with (OUT / "index.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(index_rows[0]))
        w.writeheader()
        w.writerows(index_rows)

    # Blank answer sheets — one per rater, no expected values present.
    for n in (1, 2):
        p = OUT / f"labels_rater{n}_002.csv"
        with p.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["item_id", "q1_addition_count", "q2_right_kind", "q3_scaffolding", "notes"])
            for row in index_rows:
                w.writerow([row["item_id"], "", "", "", ""])

    n_ctrl = sum(1 for r in index_rows if r["block"] == "control")
    print(f"pack_002: {len(index_rows)} items "
          f"({len(index_rows) - n_ctrl} naturalistic, {n_ctrl} controls)")
    print(f"  items      -> {OUT}/item_XX.md")
    print(f"  index      -> {OUT}/index.csv   (NOT for raters — carries ground truth)")
    print(f"  answer sheets -> {OUT}/labels_rater{{1,2}}_002.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
