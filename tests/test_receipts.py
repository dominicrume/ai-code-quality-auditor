"""Receipts: the billable artefact, and the two ways the paywall was bypassable."""
import copy
import json
import os

import pytest

from auditor.adapters._shared import load_codebase
from auditor.governance import constitution as con
from auditor.receipts import bundle, meter
from auditor.receipts import seal as S

STANDARD = "specs/kya_constitution_v1.yaml"

AGENT = (
    "import anthropic\n"
    "MAX_SPEND = 500\n"
    "def act(action, tool_calls):\n"
    "    if action.cost > MAX_SPEND:\n"
    "        return require_approval(action)\n"
    "    audit_log.write(action)\n"
    "    return run_tool(action)\n"
)


@pytest.fixture
def finding(tmp_path):
    (tmp_path / "agent.py").write_text(AGENT)
    cb = load_codebase(str(tmp_path))
    std = con.load_standard(STANDARD)
    return bundle.build(cb, std, con.evaluate(cb, std))


@pytest.fixture
def keys():
    return S.generate_keypair()


# --- the bundle -------------------------------------------------------------

def test_the_same_work_has_the_same_name(tmp_path):
    """Content addressing is where idempotent billing comes from."""
    (tmp_path / "agent.py").write_text(AGENT)
    cb = load_codebase(str(tmp_path))
    std = con.load_standard(STANDARD)
    a = bundle.build(cb, std, con.evaluate(cb, std))
    b = bundle.build(cb, std, con.evaluate(cb, std))
    assert a["finding_digest"] == b["finding_digest"]


def test_changing_one_byte_of_the_subject_changes_the_digest(tmp_path):
    (tmp_path / "agent.py").write_text(AGENT)
    cb = load_codebase(str(tmp_path))
    std = con.load_standard(STANDARD)
    first = bundle.build(cb, std, con.evaluate(cb, std))
    (tmp_path / "agent.py").write_text(AGENT + "# one comment\n")
    cb2 = load_codebase(str(tmp_path))
    second = bundle.build(cb2, std, con.evaluate(cb2, std))
    assert first["finding_digest"] != second["finding_digest"]


def test_no_source_is_carried_in_the_receipt(finding):
    """A security review asks whether code is transmitted. The answer is no."""
    blob = json.dumps(finding)
    assert "MAX_SPEND = 500" not in blob
    assert "import anthropic" not in blob
    assert finding["subject"]["file_count"] == 1
    assert finding["subject"]["tree_digest"].startswith("sha256:")


def test_the_receipt_keeps_the_grade_not_just_the_verdict(finding):
    assert {e["grade"] for e in finding["elements"]} <= {
        "measured", "provisional", "withheld"}
    assert set(finding["grades"]) == {"measured", "provisional", "withheld"}


def test_the_receipt_discloses_the_instruments_open_defects(finding):
    """A verdict whose known weakness is invisible is not an attestation."""
    assert "instrument_open_defects" in finding
    assert isinstance(finding["instrument_open_defects"], list)


def test_a_refusal_is_retained_as_a_finding(tmp_path):
    """NOT_APPLICABLE is worth keeping: on this date, this was not an agent."""
    (tmp_path / "util.py").write_text("import requests\ndef p(x):\n    return x\n")
    cb = load_codebase(str(tmp_path))
    std = con.load_standard(STANDARD)
    f = bundle.build(cb, std, con.evaluate(cb, std))
    assert f["verdict"] == "NOT_APPLICABLE"
    assert f["classification"] == "not_an_agent"
    assert bundle.intact(f)


def test_an_unsealed_receipt_says_so(finding):
    assert bundle.state(finding) == bundle.UNSEALED


# --- the seal ---------------------------------------------------------------

def test_sealing_then_verifying_against_the_public_key(finding, keys):
    priv, pub = keys
    sealed = S.seal(finding, priv, pub)
    r = S.verify(sealed, pub)
    assert r["state"] == "sealed"
    assert r["content_intact"] and r["signature_valid"] is True


def test_sealing_does_not_change_the_finding_digest(finding, keys):
    """Otherwise re-sealing identical work would look like new work."""
    priv, pub = keys
    sealed = S.seal(finding, priv, pub)
    assert sealed["finding_digest"] == finding["finding_digest"]


def test_editing_a_sealed_receipt_is_caught(finding, keys):
    priv, pub = keys
    forged = copy.deepcopy(S.seal(finding, priv, pub))
    forged["verdict"] = "PASS"
    r = S.verify(forged, pub)
    assert r["content_intact"] is False


def test_a_tampered_receipt_never_reports_a_valid_signature(finding, keys):
    """The bug this pins: the signature covers the digest, so it still checked
    out over a digest that no longer described the body, and a reader looking
    only at signature_valid would have been fooled."""
    priv, pub = keys
    forged = copy.deepcopy(S.seal(finding, priv, pub))
    forged["verdict"] = "PASS"
    r = S.verify(forged, pub)
    assert r["signature_valid"] is False
    assert "attests to something other than" in " ".join(r["reasons"])


def test_resigning_with_another_key_fails_against_the_trusted_key(finding, keys):
    """A customer holds no key that a relying party trusts. That is the paywall."""
    priv, pub = keys
    attacker_priv, attacker_pub = S.generate_keypair()
    body = {k: v for k, v in S.seal(finding, priv, pub).items() if k != "seal"}
    body["verdict"] = "PASS"
    body["finding_digest"] = bundle.recompute(body)
    forged = S.seal(body, attacker_priv, attacker_pub)
    r = S.verify(forged, pub)                 # the key the reader trusts
    assert r["signature_valid"] is False
    assert "not sealed by the key you trust" in " ".join(r["reasons"])


def test_sealing_refuses_an_already_tampered_finding(finding, keys):
    priv, pub = keys
    broken = dict(finding)
    broken["verdict"] = "PASS"
    with pytest.raises(ValueError, match="refusing to seal"):
        S.seal(broken, priv, pub)


def test_verify_reports_rather_than_raises_on_an_unsealed_receipt(finding):
    r = S.verify(finding)
    assert r["state"] == "unsealed"
    assert r["signature_valid"] is None
    assert "nobody has put their name on it" in " ".join(r["reasons"])


def test_key_id_is_derived_from_the_public_key(keys):
    _, pub = keys
    assert S.key_id(pub) == S.key_id(pub)
    _, other = S.generate_keypair()
    assert S.key_id(pub) != S.key_id(other)


# --- metering ---------------------------------------------------------------

def test_re_sealing_the_same_work_is_one_outcome(finding, keys, tmp_path):
    priv, pub = keys
    sealed = S.seal(finding, priv, pub)
    ledger = meter.Ledger(tmp_path / "ledger.jsonl")
    rows = [ledger.record(sealed, "org_a") for _ in range(4)]
    assert ledger.statement("org_a")["billable_outcomes"] == 1
    assert rows[1]["reason"] == "already recorded for this organisation"


def test_a_free_reading_does_not_shadow_the_paid_seal(finding, keys, tmp_path):
    """The bug this pins: idempotency keyed on the digest alone let a customer
    record a free unsealed reading, then seal the identical finding, and the
    seal was waved through as already recorded and never charged."""
    priv, pub = keys
    ledger = meter.Ledger(tmp_path / "ledger.jsonl")
    ledger.record(finding, "org_b")                       # free, unsealed
    row = ledger.record(S.seal(finding, priv, pub), "org_b")
    assert row["reason"] != "already recorded for this organisation"
    assert ledger.statement("org_b")["billable_outcomes"] == 1


def test_a_refusal_is_recorded_and_not_billable(tmp_path):
    (tmp_path / "util.py").write_text("import requests\ndef p(x):\n    return x\n")
    cb = load_codebase(str(tmp_path))
    std = con.load_standard(STANDARD)
    f = bundle.build(cb, std, con.evaluate(cb, std))
    ledger = meter.Ledger(tmp_path / "ledger.jsonl")
    row = ledger.record(f, "org_c")
    assert row["billable"] is False
    assert row["charged"] is False
    assert "refusal to score" in row["reason"]


def test_an_unsealed_reading_is_never_billable(finding, tmp_path):
    ledger = meter.Ledger(tmp_path / "ledger.jsonl")
    assert ledger.record(finding, "org_d")["billable"] is False


def test_charging_starts_after_the_free_quota(finding, keys, tmp_path):
    priv, pub = keys
    ledger = meter.Ledger(tmp_path / "ledger.jsonl", 2)
    charged = []
    for i in range(4):
        body = dict(finding)
        body["chain"] = {"previous": f"sha256:{i:064d}"}   # distinct work
        body["finding_digest"] = bundle.recompute(body)
        charged.append(ledger.record(S.seal(body, priv, pub), "org_e")["charged"])
    assert charged == [False, False, True, True]


def test_the_ledger_records_no_source_no_paths_and_no_file_names(finding, keys, tmp_path):
    priv, pub = keys
    ledger = meter.Ledger(tmp_path / "ledger.jsonl")
    ledger.record(S.seal(finding, priv, pub), "org_f")
    row = json.loads((tmp_path / "ledger.jsonl").read_text().splitlines()[0])
    assert set(row) == {
        "org_id", "outcome_type", "finding_digest", "standard", "verdict",
        "key_id", "recorded_at", "billable", "charged", "reason"}
    assert "agent.py" not in json.dumps(row)


def test_a_customer_can_reconcile_a_charge_against_a_receipt(finding, keys, tmp_path):
    priv, pub = keys
    sealed = S.seal(finding, priv, pub)
    ledger = meter.Ledger(tmp_path / "ledger.jsonl")
    ledger.record(sealed, "org_g")
    assert sealed["finding_digest"] in ledger.statement("org_g")["digests"]


# --- chaining ---------------------------------------------------------------

def test_a_receipt_can_name_its_predecessor(tmp_path):
    (tmp_path / "agent.py").write_text(AGENT)
    cb = load_codebase(str(tmp_path))
    std = con.load_standard(STANDARD)
    first = bundle.build(cb, std, con.evaluate(cb, std))
    second = bundle.build(cb, std, con.evaluate(cb, std),
                          previous=first["finding_digest"])
    assert second["chain"]["previous"] == first["finding_digest"]
    assert second["finding_digest"] != first["finding_digest"]


# --- the disclosure cannot go stale ----------------------------------------

def test_every_open_defect_record_is_declared_in_the_shipped_list():
    """docs/ is the record of account and is excluded from the wheel, so the
    machine-readable list is what reaches a customer. If a record says open and
    this list does not, a receipt would be silently under-disclosing."""
    import re
    from pathlib import Path
    docs = Path(__file__).parent.parent / "docs"
    declared = {d.get("id") for d in bundle.open_defects()}
    missing = []
    for record in sorted(docs.glob("FINDING_*.md")) + sorted(docs.glob("ERRATUM_*.md")):
        m = re.search(r"^\*\*Status:\*\*\s*(.+)$", record.read_text(), re.M)
        if not m:
            continue
        status = m.group(1).lower()
        if status.strip().startswith("open") and record.name.split("_")[0] + "_" + \
                record.name.split("_")[1] not in declared:
            ident = "_".join(record.name.split("_")[:2])
            if ident not in declared:
                missing.append(ident)
    assert not missing, (
        f"these records are marked open but are not in "
        f"auditor/standards/open_defects.yaml: {missing}")


def test_the_shipped_defect_list_is_valid_yaml_with_the_expected_shape():
    defects = bundle.open_defects()
    assert isinstance(defects, list)
    for d in defects:
        assert {"id", "summary", "affects", "recorded"} <= set(d)


# --- the CLI ----------------------------------------------------------------

def test_receipt_and_verify_run_from_the_cli(tmp_path):
    """The module tests all passed while both CLI commands raised NameError on
    a console that was never defined. A surface needs its own test."""
    from click.testing import CliRunner
    from auditor.core.cli import main

    subject = tmp_path / "subject"
    subject.mkdir()
    (subject / "agent.py").write_text(AGENT)
    out = tmp_path / "receipt.json"

    runner = CliRunner()
    made = runner.invoke(main, ["receipt", str(subject), "--out", str(out)])
    assert made.exit_code == 0, made.output
    assert "unsealed" in made.output
    assert out.exists()

    checked = runner.invoke(main, ["verify", str(out)])
    assert checked.exit_code == 0, checked.output
    assert "UNSEALED" in checked.output


def test_verify_exits_nonzero_on_a_tampered_receipt_so_ci_can_gate(tmp_path):
    from click.testing import CliRunner
    from auditor.core.cli import main

    subject = tmp_path / "subject"
    subject.mkdir()
    (subject / "agent.py").write_text(AGENT)
    out = tmp_path / "receipt.json"
    runner = CliRunner()
    runner.invoke(main, ["receipt", str(subject), "--out", str(out)])

    forged = json.loads(out.read_text())
    forged["verdict"] = "PASS"
    out.write_text(json.dumps(forged))

    assert runner.invoke(main, ["verify", str(out)]).exit_code == 1


# --- the receipt must be producible for anything on disk --------------------

def test_a_receipt_is_producible_for_a_file_whose_name_is_not_valid_utf8():
    """A path read back through surrogateescape used to crash canonical()."""
    cb = {"files": {"we\udcffird.py": "x = 1\n"}, "manifest": []}
    record = bundle.subject_record(cb)
    assert record["file_count"] == 1
    assert record["tree_digest"].startswith("sha256:")
    assert record["files"][0][0] == r"we\xffird.py"


def test_a_receipt_is_producible_for_a_file_whose_bytes_are_not_valid_utf8():
    cb = {"files": {"bad.py": "x = '\udcff\udcfe'\n"}, "manifest": []}
    assert bundle.subject_record(cb)["tree_digest"].startswith("sha256:")


def test_two_badly_encoded_paths_are_not_flattened_into_one():
    """Escaping must stay reversible, or two files could share one record."""
    a = bundle.subject_record({"files": {"a\udcff.py": "x\n"}})
    b = bundle.subject_record({"files": {"a\udcfe.py": "x\n"}})
    assert a["tree_digest"] != b["tree_digest"]


def test_a_receipt_with_a_badly_encoded_path_can_be_written_and_read_back(tmp_path):
    f = {"subject": bundle.subject_record({"files": {"we\udcffird.py": "x\n"}})}
    out = bundle.write(f, tmp_path / "receipt.json")
    assert json.loads(out.read_text(encoding="utf-8"))["subject"]["file_count"] == 1


# --- the digest is the product, so it must be stable ------------------------

def test_the_digest_does_not_depend_on_dict_insertion_order():
    one = {"a": 1, "b": {"x": 1, "y": 2}}
    two = {"b": {"y": 2, "x": 1}, "a": 1}
    assert bundle.digest(one) == bundle.digest(two)


def test_the_digest_does_not_depend_on_the_working_directory(tmp_path, monkeypatch):
    (tmp_path / "agent.py").write_text(AGENT)
    std = con.load_standard(STANDARD)
    here = bundle.build(load_codebase(str(tmp_path)), std,
                        con.evaluate(load_codebase(str(tmp_path)), std))
    monkeypatch.chdir(tmp_path)
    there = bundle.build(load_codebase(str(tmp_path)), std,
                         con.evaluate(load_codebase(str(tmp_path)), std))
    assert here["finding_digest"] == there["finding_digest"]


def test_the_digest_survives_a_re_import_of_the_module(finding):
    """Nothing is cached per process, so a fresh import names work the same."""
    import importlib
    again = importlib.reload(bundle)
    try:
        assert again.recompute(finding) == finding["finding_digest"]
    finally:
        importlib.reload(bundle)


def test_changing_the_standard_changes_the_digest(tmp_path):
    (tmp_path / "agent.py").write_text(AGENT)
    cb = load_codebase(str(tmp_path))
    std = con.load_standard(STANDARD)
    first = bundle.build(cb, std, con.evaluate(cb, std))
    altered = copy.deepcopy(std)
    altered["note"] = "a different standard document"
    second = bundle.build(cb, altered, con.evaluate(cb, std))
    assert first["finding_digest"] != second["finding_digest"]


def test_changing_the_chain_pointer_changes_the_digest(finding):
    body = {k: v for k, v in finding.items() if k != "finding_digest"}
    body["chain"] = {"previous": "sha256:" + "0" * 64}
    assert bundle.digest(body) != finding["finding_digest"]


def test_coverage_is_rounded_so_float_noise_cannot_change_the_digest(finding):
    """Six places is enough: coverage is a ratio of file counts, and the digest
    must not move because the last bits of a float did."""
    body = {k: v for k, v in finding.items() if k != "finding_digest"}
    assert body["coverage"] == round(body["coverage"], 6)
    body["coverage"] = round(body["coverage"] + 1e-12, 6)
    assert bundle.digest(body) == finding["finding_digest"]


# --- the seal's edges -------------------------------------------------------

def test_sealing_a_sealed_finding_is_refused_unless_asked_for(finding, keys):
    """A second seal overwrites the first signer's name silently."""
    priv, pub = keys
    sealed = S.seal(finding, priv, pub)
    with pytest.raises(ValueError, match="already sealed"):
        S.seal(sealed, priv, pub)
    other_priv, other_pub = S.generate_keypair()
    resealed = S.seal(sealed, other_priv, other_pub, resealing=True)
    assert S.verify(resealed, other_pub)["signature_valid"] is True


def test_a_key_id_that_does_not_identify_its_own_public_key_is_a_forgery(finding, keys):
    """The real vector: sign with your key, wear the trusted key's name. A
    reader who recognises key_id and never derives it would be fooled."""
    priv, pub = keys
    attacker_priv, attacker_pub = S.generate_keypair()
    forged = S.seal(finding, attacker_priv, attacker_pub)
    forged["seal"]["key_id"] = S.key_id(pub)          # wear the trusted name
    r = S.verify(forged)                              # no key supplied
    assert r["signature_valid"] is False
    assert "does not identify the key that signed it" in " ".join(r["reasons"])


def test_a_malformed_base64_signature_is_reported_not_raised(finding, keys):
    priv, pub = keys
    sealed = S.seal(finding, priv, pub)
    sealed["seal"]["signature"] = "not base64 at all!!"
    r = S.verify(sealed, pub)
    assert r["signature_valid"] is False and r["reasons"]


def test_a_truncated_public_key_is_reported_not_raised(finding, keys):
    priv, pub = keys
    sealed = S.seal(finding, priv, pub)
    r = S.verify(sealed, pub[:8])
    assert r["signature_valid"] is False and r["reasons"]


def test_a_seal_block_missing_fields_is_reported_not_raised(finding, keys):
    priv, pub = keys
    sealed = S.seal(finding, priv, pub)
    del sealed["seal"]["signature"]
    r = S.verify(sealed, pub)
    assert r["signature_valid"] is False
    assert "incomplete" in " ".join(r["reasons"])


# --- the chain --------------------------------------------------------------

def test_a_chain_pointer_that_is_not_a_digest_is_refused_at_build_time(tmp_path):
    (tmp_path / "agent.py").write_text(AGENT)
    cb = load_codebase(str(tmp_path))
    std = con.load_standard(STANDARD)
    with pytest.raises(ValueError, match="not a finding digest"):
        bundle.build(cb, std, con.evaluate(cb, std), previous="yesterday")


def test_an_ordered_run_of_receipts_is_checkable_as_one_chain(tmp_path):
    (tmp_path / "agent.py").write_text(AGENT)
    std = con.load_standard(STANDARD)
    chain = []
    for i in range(3):
        (tmp_path / "agent.py").write_text(AGENT + f"# run {i}\n")
        cb = load_codebase(str(tmp_path))
        previous = chain[-1]["finding_digest"] if chain else None
        chain.append(bundle.build(cb, std, con.evaluate(cb, std),
                                  previous=previous))
    assert bundle.chain_intact(chain)


def test_a_broken_link_in_a_chain_is_named(tmp_path):
    (tmp_path / "agent.py").write_text(AGENT)
    std = con.load_standard(STANDARD)
    cb = load_codebase(str(tmp_path))
    first = bundle.build(cb, std, con.evaluate(cb, std))
    second = bundle.build(cb, std, con.evaluate(cb, std),
                          previous="sha256:" + "0" * 64)
    breaks = bundle.chain_breaks([first, second])
    assert len(breaks) == 1 and "as its predecessor" in breaks[0]


# --- the quota and the ledger under concurrency -----------------------------

def test_the_free_quota_follows_the_environment_when_it_changes(monkeypatch):
    """Read at import, a changed quota had no effect until a restart."""
    monkeypatch.delenv("AUDITOR_FREE_QUOTA", raising=False)
    assert meter.free_quota() == meter.DEFAULT_FREE_QUOTA
    monkeypatch.setenv("AUDITOR_FREE_QUOTA", "3")
    assert meter.free_quota() == 3
    monkeypatch.setenv("AUDITOR_FREE_QUOTA", "not a number")
    assert meter.free_quota() == meter.DEFAULT_FREE_QUOTA


def test_a_ledger_can_be_given_its_own_quota_without_patching_the_module(tmp_path):
    assert meter.Ledger(tmp_path / "l.jsonl", 7).statement("org")["free_quota"] == 7


def test_concurrent_seals_of_different_work_cannot_both_slip_inside_the_quota(
        finding, keys, tmp_path):
    """The race this pins: record() read the billable count, decided, then
    appended. Two threads read the same stale count and both came in free, and
    two unsynchronised appends could tear a line in half."""
    import threading
    priv, pub = keys
    quota = 8
    runs = 64        # enough threads that the unlocked version undercharges
    sealed = []
    for i in range(runs):
        body = {k: v for k, v in finding.items() if k != "finding_digest"}
        body["chain"] = {"previous": f"sha256:{i:064d}"}     # distinct work
        body["finding_digest"] = bundle.recompute(body)
        sealed.append(S.seal(body, priv, pub))

    ledger = meter.Ledger(tmp_path / "ledger.jsonl", quota)
    start = threading.Event()

    def go(f):
        start.wait()
        ledger.record(f, "org_race")

    threads = [threading.Thread(target=go, args=(f,)) for f in sealed]
    for t in threads:
        t.start()
    start.set()
    for t in threads:
        t.join()

    lines = (tmp_path / "ledger.jsonl").read_text().splitlines()
    assert len(lines) == runs                      # no torn or lost lines
    for line in lines:
        json.loads(line)                           # every line whole
    assert ledger.billable_count("org_race") == runs
    assert ledger.charged_count("org_race") == runs - quota


def test_a_bare_date_in_the_shipped_defect_list_cannot_break_a_receipt():
    """YAML reads 2026-11-21 as a date object, which is not JSON serialisable.
    One unquoted value in the shipped disclosure made every receipt
    unproducible, so the list is coerced to text on the way in."""
    import datetime
    coerced = bundle._as_text({"recorded": datetime.date(2026, 11, 21),
                               "n": 1, "ok": True, "none": None,
                               "list": [datetime.date(2026, 1, 1)]})
    assert coerced["recorded"] == "2026-11-21"
    assert coerced["n"] == 1 and coerced["ok"] is True and coerced["none"] is None
    assert coerced["list"] == ["2026-01-01"]
    json.dumps(coerced)          # the property that actually matters


def test_the_receipt_discloses_exactly_what_the_shipped_list_declares(finding):
    """Named FINDING_004 before, and so had to be edited to close it. A test
    that has to be edited when a defect is fixed is pinning the contents of the
    list rather than the disclosure, and the disclosure is the property worth
    having: whatever is open travels with the artefact, and nothing else does.

    This holds when the list is empty, which is when under-disclosure is
    easiest to ship and hardest to notice."""
    declared = [d["id"] for d in bundle.open_defects()]
    assert "instrument_open_defects" in finding
    assert [d["id"] for d in finding["instrument_open_defects"]] == declared
    for entry in finding["instrument_open_defects"]:
        assert entry.get("affects"), "a disclosed defect with no stated effect"


def test_a_defect_added_to_the_list_reaches_the_receipt(tmp_path, monkeypatch):
    """The test above passes trivially while the list is empty. This one proves
    the wire is live, by putting a defect on it."""
    planted = [{"id": "FINDING_000", "summary": "synthetic",
                "affects": "nothing, this is a test", "recorded": "2026-01-01"}]
    monkeypatch.setattr(bundle, "open_defects", lambda: planted)
    (tmp_path / "agent.py").write_text(AGENT)
    cb = load_codebase(str(tmp_path))
    std = con.load_standard(STANDARD)
    built = bundle.build(cb, std, con.evaluate(cb, std))
    assert [d["id"] for d in built["instrument_open_defects"]] == ["FINDING_000"]
