"""Receipts: the billable artefact, and the two ways the paywall was bypassable."""
import copy
import json

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


def test_charging_starts_after_the_free_quota(finding, keys, tmp_path, monkeypatch):
    monkeypatch.setattr(meter, "FREE_QUOTA", 2)
    priv, pub = keys
    ledger = meter.Ledger(tmp_path / "ledger.jsonl")
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
