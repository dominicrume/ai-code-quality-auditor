#!/usr/bin/env python3
"""Score the second labelling pack: two constructs, reported separately.

Run with no rater labels present and it reports what the instrument claims,
which is useful before recruiting raters and is explicitly not a validation of
anything. Once `labels_rater1_002.csv` and `labels_rater2_002.csv` are filled
in it computes, for each construct:

* κ(rater 1, rater 2) — can humans agree on this question at all?
* κ(rater N, instrument) — does the instrument agree with each human?
* control sensitivity — on the six items whose ground truth is known by
  construction, did each judge notice?

Q1 (addition) is scored on the binary contrast (any off-specification surface
vs none) so it is comparable with study 001, and the count-level exact
agreement is reported alongside because study 001 found binary κ conceals
magnitude disagreement (item_06: 1 vs 2; item_16: 0 vs 4).

Threshold: κ ≥ 0.60 (Landis and Koch, 1977), as pre-registered for study 001.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PACK = ROOT / "data/labels/pack_002"

THRESHOLD = 0.60


def _kappa(a: list, b: list) -> tuple[float, float, int]:
    """Cohen's κ without a hard dependency, plus raw agreement and n."""
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if not pairs:
        return float("nan"), float("nan"), 0
    n = len(pairs)
    agree = sum(1 for x, y in pairs if x == y) / n
    cats = {x for x, _ in pairs} | {y for _, y in pairs}
    expected = sum(
        (sum(1 for x, _ in pairs if x == c) / n) * (sum(1 for _, y in pairs if y == c) / n)
        for c in cats
    )
    if expected >= 1.0:
        # Every judgement identical and one-sided: κ is undefined, agreement is 1.
        return float("nan"), agree, n
    return (agree - expected) / (1 - expected), agree, n


def _interpret(k: float) -> str:
    if k != k:
        return "undefined (no disagreement to model)"
    if k < 0.20: return "slight"
    if k < 0.40: return "fair"
    if k < 0.60: return "moderate"
    if k < 0.80: return "substantial"
    return "almost perfect"


def _instrument(index_rows: list[dict]) -> dict[str, dict]:
    """What the instrument says about each item, as presented to the rater."""
    from auditor.analyzers.manifest_deriver import derive

    out: dict[str, dict] = {}
    for row in index_rows:
        spec_path = ROOT / "specs" / f"{row['presented_spec']}.yaml"
        spec = yaml.safe_load(spec_path.read_text())
        cond = row["condition"]
        cb = ROOT / "data/raw" / row["run_id"] / cond / "codebase.json"
        files = json.loads(cb.read_text()).get("files", {})
        d = derive(spec, {"files": files})
        addition = len(d["hallucinated_endpoints"]) + len(d["hallucinated_commands"])
        out[row["item_id"]] = {
            "q1": addition,
            "q1_binary": 1 if addition > 0 else 0,
            # The instrument answers Q2 with shape detection: a mismatch means
            # "not the kind of thing asked for". An unresolved verdict abstains.
            "q2": ("no" if d["shape"]["mismatch"]
                   else ("yes" if d["shape"]["confident"] else "unsure")),
            "built_shape": d["shape"]["built_shape"],
            "specified_shape": d["shape"]["specified_shape"],
        }
    return out


def _read_labels(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    rows = {}
    for r in csv.DictReader(path.open()):
        q1 = (r.get("q1_addition_count") or "").strip()
        rows[r["item_id"]] = {
            "q1": int(q1) if q1.isdigit() else None,
            "q1_binary": (1 if int(q1) > 0 else 0) if q1.isdigit() else None,
            "q2": (r.get("q2_right_kind") or "").strip().lower() or None,
            "q3": (r.get("q3_scaffolding") or "").strip().lower() or None,
        }
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pack", default=str(PACK), help="pack directory")
    args = ap.parse_args()
    pack = Path(args.pack)

    index_rows = list(csv.DictReader((pack / "index.csv").open()))
    ids = [r["item_id"] for r in index_rows]
    truth = {r["item_id"]: r for r in index_rows}

    inst = _instrument(index_rows)
    r1 = _read_labels(pack / "labels_rater1_002.csv")
    r2 = _read_labels(pack / "labels_rater2_002.csv")
    have_humans = any(v["q1"] is not None or v["q2"] for v in {**r1, **r2}.values())

    print("=" * 66)
    print("  Pack 002 — two constructs, fresh items, known controls")
    print("=" * 66)
    print(f"  items: {len(ids)}  "
          f"({sum(1 for r in index_rows if r['block']=='naturalistic')} naturalistic, "
          f"{sum(1 for r in index_rows if r['block']=='control')} controls)")

    # --- controls: ground truth is known by construction ---------------------
    ctrl = [i for i in ids if truth[i]["block"] == "control"]
    print(f"\n  Controls (expected answer to Q2 is 'no' — wrong kind by construction)")
    caught = sum(1 for i in ctrl if inst[i]["q2"] == "no")
    print(f"    instrument: {caught}/{len(ctrl)} identified as the wrong kind")
    for i in ctrl:
        mark = "OK " if inst[i]["q2"] == "no" else "MISS"
        print(f"      {mark} {i}: code is {truth[i]['true_spec']}, "
              f"presented as {truth[i]['presented_spec']} -> "
              f"instrument built={inst[i]['built_shape']} says '{inst[i]['q2']}'")

    nat = [i for i in ids if truth[i]["block"] == "naturalistic"]
    false_fire = [i for i in nat if inst[i]["q2"] == "no"]
    print(f"\n  Specificity on naturalistic items: "
          f"{len(nat) - len(false_fire)}/{len(nat)} not flagged as wrong kind")
    for i in false_fire:
        print(f"      FLAGGED {i} ({truth[i]['condition']} x {truth[i]['presented_spec']}) "
              f"built={inst[i]['built_shape']}")

    if not have_humans:
        print("\n  No rater labels yet — nothing above is validation.")
        print("  Give raters the item_XX.md files and the blank answer sheets;")
        print("  withhold index.csv, which carries the ground truth.")
        print("  Re-run this script once both sheets are returned.")
        return 0

    # --- with humans: the actual validation ----------------------------------
    for label, key, binary in (("Q1 — addition", "q1_binary", True),
                               ("Q2 — right kind", "q2", False)):
        print(f"\n  {label}")
        a = [r1.get(i, {}).get(key) for i in ids]
        b = [r2.get(i, {}).get(key) for i in ids]
        m = [inst[i][key if key != "q2" else "q2"] for i in ids]
        for name, x, y in (("rater 1 x rater 2", a, b),
                           ("rater 1 x instrument", a, m),
                           ("rater 2 x instrument", b, m)):
            k, agree, n = _kappa(x, y)
            flag = "PASS" if (k == k and k >= THRESHOLD) else ("--" if k != k else "BELOW")
            print(f"    {name:22s} κ = {k:.3f}  ({_interpret(k)}), "
                  f"raw {agree:.1%}, n={n}  [{flag}]")
        if binary:
            exact = [(r1.get(i, {}).get("q1"), r2.get(i, {}).get("q1")) for i in ids]
            ok = [p for p in exact if p[0] is not None and p[1] is not None]
            if ok:
                same = sum(1 for x, y in ok if x == y) / len(ok)
                print(f"    count-level exact agreement (not κ): {same:.1%} of {len(ok)} items")

    print(f"\n  Q3 — scaffolding (exploratory, descriptive only)")
    for name, rr in (("rater 1", r1), ("rater 2", r2)):
        vals = [rr.get(i, {}).get("q3") for i in ids]
        counts = {v: vals.count(v) for v in set(vals) if v}
        print(f"    {name}: {counts or 'no answers'}")

    print("\n" + "=" * 66)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
