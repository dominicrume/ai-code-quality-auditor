#!/usr/bin/env python3
"""Build a blind labelling pack for the hallucination validation.

Two things this handles that a naive pack would not.

*Duplicates.* The 30 sampled rows contain only 19 distinct codebases: the
IDE-bound conditions were captured once per cell and replayed (Deviation 001),
so several rows are byte-identical. Labelling them separately would waste most
of the reading and, worse, inflate κ — identical items agree by construction,
which is agreement carrying no information. Each distinct codebase is presented
once; labels are propagated to its duplicate rows afterwards.

*Blinding.* The pack contains the specification and the code, and nothing else.
The heuristic's count and its derived manifest are deliberately absent: a rater
who can see the answer is measuring their agreement with a suggestion.
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "data/labels/hallucination_handlabels.csv"
OUT = ROOT / "data/labels/pack"


def spec_features(spec_name: str) -> list[dict]:
    p = ROOT / "specs" / f"{spec_name}.yaml"
    return yaml.safe_load(p.read_text()).get("features", []) if p.exists() else []


def main() -> int:
    rows = list(csv.DictReader(SAMPLE.open()))
    groups: dict[str, list[dict]] = defaultdict(list)
    contents: dict[str, dict] = {}

    for r in rows:
        cb = Path(ROOT / r["code_path"]).parent / "codebase.json"
        files = json.loads(cb.read_text()).get("files", {}) if cb.exists() else {}
        key = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()[:12]
        groups[key].append(r)
        contents[key] = files

    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("item_*.md"):
        old.unlink()

    index = []
    for i, (key, members) in enumerate(sorted(groups.items(), key=lambda kv: kv[1][0]["run_id"]), 1):
        r = members[0]
        files = contents[key]
        item_id = f"item_{i:02d}"
        feats = spec_features(r["spec_name"])

        doc = [
            f"# {item_id}",
            "",
            f"**Specification:** `{r['spec_name']}`  ",
            f"**Covers {len(members)} sampled run(s)** "
            f"(identical code){'' if len(members) == 1 else ' — replayed capture'}",
            "",
            "---",
            "",
            "## What was asked for",
            "",
            "These are the ONLY features the specification requested:",
            "",
        ]
        for f in feats:
            doc.append(f"- **`{f['id']}`** — {f.get('description','')}")
        doc += [
            "",
            "---",
            "",
            "## Your task",
            "",
            "Read the code below and count **how many distinct features, routes, "
            "endpoints or subcommands exist that are NOT in the list above**.",
            "",
            "Count a feature once, however many files it spans. Do not count "
            "helpers, config, tests or imports — only things a user could invoke "
            "that nobody asked for.",
            "",
            f"Write your number in `labels_rater<N>.csv` on the row for `{item_id}`.",
            "",
            "---",
            "",
            f"## The code ({len(files)} files, "
            f"{sum(len(c.splitlines()) for c in files.values())} lines)",
            "",
        ]
        if not files:
            doc += ["> **This capture contains no files.** Record `SKIP` for this item.", ""]
        for name, content in sorted(files.items()):
            lang = name.rsplit(".", 1)[-1] if "." in name else ""
            doc += [f"### `{name}`", "", f"```{lang}", content.rstrip(), "```", ""]

        (OUT / f"{item_id}.md").write_text("\n".join(doc))
        index.append({
            "item_id": item_id,
            "spec_name": r["spec_name"],
            "n_runs_covered": len(members),
            "run_ids": ";".join(m["run_id"] for m in members),
            "n_files": len(files),
        })

    # the sheet each rater fills in — condition deliberately omitted
    for n in (1, 2):
        p = ROOT / f"data/labels/labels_rater{n}.csv"
        with p.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["item_id", "spec_name", "n_offspec_features", "notes"])
            w.writeheader()
            for e in index:
                w.writerow({"item_id": e["item_id"], "spec_name": e["spec_name"],
                            "n_offspec_features": "", "notes": ""})
        print(f"  wrote {p.relative_to(ROOT)}")

    with (OUT / "index.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(index[0]))
        w.writeheader()
        w.writerows(index)

    print(f"  wrote {len(index)} item files to {OUT.relative_to(ROOT)}/")
    print(f"  {len(rows)} sampled runs -> {len(index)} distinct codebases to read")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
