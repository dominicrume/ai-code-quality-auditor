"""Guards on the second labelling pack.

These check the properties the design depends on. If any fails, the pack is
not a valid instrument for the study it claims to run.
"""
import csv
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PACK = ROOT / "data/labels/pack_002"

pytestmark = pytest.mark.skipif(
    not (PACK / "index.csv").exists(),
    reason="pack_002 not built (run scripts/make_labelling_pack_002.py)",
)


@pytest.fixture(scope="module")
def index():
    return list(csv.DictReader((PACK / "index.csv").open()))


def test_every_item_has_a_file(index):
    for row in index:
        assert (PACK / f"{row['item_id']}.md").exists()


def test_no_item_reuses_a_codebase_labelled_in_pack_001(index):
    """The whole point of a fresh sample."""
    import hashlib

    seen_digests = set()
    for row in csv.DictReader((ROOT / "data/labels/pack/index.csv").open()):
        for rid in row["run_ids"].split(";"):
            rid = rid.strip()
            if not rid:
                continue
            cond = rid.replace("main_001__", "").rsplit("__rep", 1)[0].rsplit("__", 1)[-1]
            cb = ROOT / "data/raw" / rid / cond / "codebase.json"
            if cb.exists():
                files = json.loads(cb.read_text()).get("files", {})
                seen_digests.add(
                    hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()[:12]
                )
    for row in index:
        assert row["digest"] not in seen_digests, f"{row['item_id']} was labelled in pack 001"


def test_all_digests_are_distinct(index):
    digests = [r["digest"] for r in index]
    assert len(digests) == len(set(digests))


def test_controls_are_presented_against_a_different_spec(index):
    controls = [r for r in index if r["block"] == "control"]
    assert controls, "a pack with no controls cannot test sensitivity"
    for r in controls:
        assert r["presented_spec"] != r["true_spec"]
        assert r["expected_kind"] == "no"


def test_naturalistic_items_are_presented_against_their_own_spec(index):
    for r in index:
        if r["block"] == "naturalistic":
            assert r["presented_spec"] == r["true_spec"]
            assert r["expected_kind"] == "yes"


def test_item_files_do_not_leak_ground_truth(index):
    """A rater who can see the answer is measuring their agreement with it."""
    for row in index:
        text = (PACK / f"{row['item_id']}.md").read_text().lower()
        assert "control" not in text.split("## the code")[0]
        assert row["condition"] not in text, "condition name leaks the vendor"
        assert "expected" not in text.split("## the code")[0]


def test_answer_sheets_are_blank_and_cover_every_item(index):
    for n in (1, 2):
        rows = list(csv.DictReader((PACK / f"labels_rater{n}_002.csv").open()))
        assert [r["item_id"] for r in rows] == [r["item_id"] for r in index]
        for r in rows:
            assert r["q1_addition_count"] == ""
            assert r["q2_right_kind"] == ""
