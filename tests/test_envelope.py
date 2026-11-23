"""The merged receipt envelope: one format, two payload types.

docs/RECEIPT_ENVELOPE.md is the normative text. These tests pin the three
properties that make it worth having, and each of the three came from a
limitation one of the two merged formats declared about itself.
"""
from __future__ import annotations

import json

import pytest

from auditor.adapters._shared import load_codebase
from auditor.governance import constitution as con
from auditor.receipts import envelope as E
from auditor.receipts import seal as S

STANDARD = "specs/agent_constitution_v1.yaml"

AGENT = '''
import anthropic

MAX_SPEND = 100

def act(task, spend):
    if spend > MAX_SPEND:
        audit_log.write("refused: over cap")
        return escalate_to_human(task)
    client = anthropic.Anthropic()
    return client.messages.create(model="m", messages=[{"role": "user", "content": task}])
'''


@pytest.fixture
def conformance(tmp_path):
    (tmp_path / "agent.py").write_text(AGENT)
    cb = load_codebase(str(tmp_path))
    std = con.load_standard(STANDARD)
    return E.build_conformance(cb, std, con.evaluate(cb, std))


@pytest.fixture
def refusal():
    return E.build_refusal(
        subject={"mandate": "mandate-7", "cap": "100.00", "currency": "GBP"},
        attempt={"what": "buy a football", "amount": "40.00",
                 "currency": "GBP", "payee": "sports-shop"},
        rule="payee not on allow-list",
        decided_by="ledger:participant-1",
        at="2026-11-23T09:00:00Z",
    )


# --- one envelope, two payloads --------------------------------------------

def test_both_payload_types_share_one_envelope(conformance, refusal):
    shape = lambda e: sorted(k for k in e if k != "seal")
    assert shape(conformance) == shape(refusal)
    assert conformance["receipt_type"] == "conformance"
    assert refusal["receipt_type"] == "refusal"


def test_the_method_cannot_be_mismatched_to_the_type(conformance):
    assert conformance["method"] == E.STATIC
    forged = json.loads(json.dumps(conformance))
    forged["method"] = E.BEHAVIOURAL
    forged["content_digest"] = E.content_digest(forged)
    assert any("only" in p for p in E.validate(forged))


def test_the_renamed_standard_is_what_a_new_receipt_names(conformance):
    assert conformance["standard"]["name"] == "agent-constitution"
    assert E.validate(conformance) == []


def test_the_old_standard_identity_still_verifies(tmp_path):
    """A receipt made against kya/1 was true when it was made. Renaming a
    standard must not invalidate a record somebody is holding."""
    (tmp_path / "agent.py").write_text(AGENT)
    cb = load_codebase(str(tmp_path))
    std = con.load_standard("specs/kya_constitution_v1.yaml")
    env = E.build_conformance(cb, std, con.evaluate(cb, std))
    assert env["standard"]["name"] == "kya"
    assert E.validate(env) == []


# --- 1. assurance is derived, and there is no field for it -----------------

def test_an_unsealed_receipt_is_self_attested(conformance):
    assert E.assurance(conformance) == E.SELF_ATTESTED


def test_a_sealed_receipt_is_still_self_attested_without_a_key():
    """An unverified signature is a string. The reader has to bring the key."""
    private, public = S.generate_keypair()
    env = E.build_refusal(
        subject={"mandate": "m"}, attempt={"what": "x", "amount": "1.00"},
        rule="over cap", decided_by="ledger:p1", at="2026-11-23T09:00:00Z")
    sealed = S.seal(env, private, public)
    assert E.assurance(sealed) == E.SELF_ATTESTED
    assert E.assurance(sealed, public_key=public) == E.SEALED


def test_only_a_reader_who_looked_can_say_anchored():
    private, public = S.generate_keypair()
    env = E.build_refusal(
        subject={"mandate": "m"}, attempt={"what": "x", "amount": "1.00"},
        rule="over cap", decided_by="ledger:p1", at="2026-11-23T09:00:00Z")
    sealed = S.seal(env, private, public)
    assert E.assurance(sealed, public_key=public,
                       anchor_checked=True) == E.ANCHORED


def test_a_declared_assurance_level_is_refused(refusal):
    """The strongest form of 'the verifier derives it' is having nowhere to
    write it. A producer that writes one anyway must be rejected, because
    something downstream will eventually read it."""
    for field in ("assurance", "assurance_level", "verified", "trusted"):
        forged = json.loads(json.dumps(refusal))
        forged[field] = "anchored"
        forged["content_digest"] = E.content_digest(forged)
        problems = E.validate(forged)
        assert any("derived by the verifier" in p for p in problems), field


def test_a_ledger_ref_does_not_raise_the_level():
    """An address is not evidence. Either the record is there, or it is not."""
    env = E.build_refusal(
        subject={"mandate": "m"}, attempt={"what": "x", "amount": "1.00"},
        rule="over cap", decided_by="ledger:p1", at="2026-11-23T09:00:00Z",
        ledger_ref="canton://participant-1/ChargeRefused#abc")
    assert env["payload"]["ledger_ref"].startswith("canton://")
    assert E.assurance(env) == E.SELF_ATTESTED


def test_altered_content_has_no_assurance_level_at_all(refusal):
    forged = json.loads(json.dumps(refusal))
    forged["payload"]["rule"] = "nothing was wrong"
    with pytest.raises(ValueError, match="content digest"):
        E.assurance(forged)


# --- 2. canonical ASCII, by escaping rather than prohibition ---------------

def test_canonical_form_is_ascii_so_two_languages_agree():
    body = {"reason": "تجاوز الحد"}
    out = E.canonical(body)
    out.decode("ascii")                      # would raise if it were not
    assert b"\\u" in out


def test_a_non_latin_refusal_reason_seals_and_reads_back():
    """The format being merged in forbids non-ASCII in a sealed body, at the
    stated cost that a refusal reason in a non-Latin script cannot be sealed as
    written. Escaping keeps the text and the identical bytes."""
    reason = "超出限额"      # "exceeds the limit"
    env = E.build_refusal(
        subject={"mandate": "m"}, attempt={"what": reason, "amount": "1.00"},
        rule=reason, decided_by="ledger:p1", at="2026-11-23T09:00:00Z")
    assert E.validate(env) == []
    assert env["payload"]["rule"] == reason
    reread = json.loads(E.canonical(env).decode("ascii"))
    assert reread["payload"]["rule"] == reason
    assert E.intact(reread)


def test_an_amount_must_be_a_string():
    with pytest.raises(ValueError, match="round-trip"):
        E.build_refusal(
            subject={"mandate": "m"}, attempt={"what": "x", "amount": 1.10},
            rule="over cap", decided_by="ledger:p1", at="2026-11-23T09:00:00Z")


# --- 3. the digest covers the content and not the moment -------------------

def test_the_same_work_has_the_same_name(tmp_path):
    (tmp_path / "agent.py").write_text(AGENT)
    cb = load_codebase(str(tmp_path))
    std = con.load_standard(STANDARD)
    a = E.build_conformance(cb, std, con.evaluate(cb, std))
    b = E.build_conformance(cb, std, con.evaluate(cb, std))
    assert a["content_digest"] == b["content_digest"]


def test_a_refusals_own_time_is_covered_by_its_digest(refusal):
    """A refusal's time is material, so it is inside the payload, not excluded
    as an issuing moment would be."""
    moved = json.loads(json.dumps(refusal))
    moved["payload"]["at"] = "2020-01-01T00:00:00Z"
    assert not E.intact(moved)


def test_no_source_is_carried(conformance):
    blob = json.dumps(conformance)
    assert "MAX_SPEND" not in blob
    assert "anthropic" not in blob


def test_the_open_defect_disclosure_travels(conformance):
    from auditor.receipts import bundle
    declared = [d["id"] for d in bundle.open_defects()]
    assert [d["id"] for d in conformance["disclosed_defects"]] == declared


# --- the chain -------------------------------------------------------------

def _chain_of(three):
    out, prev = [], None
    for i, kw in enumerate(three):
        env = E.build_refusal(previous=prev, n=i, **kw)
        out.append(env)
        prev = env["content_digest"]
    return out


BASE = dict(subject={"mandate": "m"}, rule="over cap",
            decided_by="ledger:p1", at="2026-11-23T09:00:00Z")


def test_an_unbroken_chain_verifies():
    chain = _chain_of([dict(BASE, attempt={"what": f"a{i}", "amount": "1.00"})
                       for i in range(3)])
    assert E.chain_intact(chain)


def test_an_edited_middle_link_is_detected():
    chain = _chain_of([dict(BASE, attempt={"what": f"a{i}", "amount": "1.00"})
                       for i in range(3)])
    chain[1]["payload"]["rule"] = "nothing was wrong"
    assert not E.chain_intact(chain)


def test_a_removed_tail_is_visible_through_the_counter():
    """Pointers alone cannot see a truncation: the remaining chain is valid.
    The counter is what makes it visible to a reader who knows the count."""
    chain = _chain_of([dict(BASE, attempt={"what": f"a{i}", "amount": "1.00"})
                       for i in range(3)])
    assert E.chain_breaks(chain[1:]), "a chain starting at n=1 must not pass"


def test_the_first_link_cannot_name_a_predecessor():
    with pytest.raises(ValueError, match="first link"):
        E.build_refusal(previous="sha256:" + "a" * 64, n=0,
                        attempt={"what": "x", "amount": "1.00"}, **BASE)


def test_a_later_link_must_name_one():
    with pytest.raises(ValueError, match="predecessor is required"):
        E.build_refusal(previous=None, n=1,
                        attempt={"what": "x", "amount": "1.00"}, **BASE)


def test_a_malformed_pointer_is_refused():
    with pytest.raises(ValueError, match="not a content digest"):
        E.build_refusal(previous="yesterday", n=1,
                        attempt={"what": "x", "amount": "1.00"}, **BASE)


# --- a refusal has to name who refused -------------------------------------

def test_a_refusal_must_name_the_rule_that_decided():
    with pytest.raises(ValueError, match="no named rule"):
        E.build_refusal(subject={"mandate": "m"},
                        attempt={"what": "x", "amount": "1.00"},
                        rule="  ", decided_by="ledger:p1",
                        at="2026-11-23T09:00:00Z")


def test_a_refusal_must_name_the_enforcement_point():
    """A refusal an agent recorded about itself is not evidence of
    enforcement, and this is the only place that distinction can be held."""
    with pytest.raises(ValueError, match="enforcement point"):
        E.build_refusal(subject={"mandate": "m"},
                        attempt={"what": "x", "amount": "1.00"},
                        rule="over cap", decided_by="",
                        at="2026-11-23T09:00:00Z")


# --- the validator never crashes -------------------------------------------

@pytest.mark.parametrize("junk", [
    None, 3, "a string", [], {}, {"envelope_version": 2},
    {"envelope_version": 99, "receipt_type": "x"},
])
def test_the_validator_reports_rather_than_raises(junk):
    problems = E.validate(junk)
    assert isinstance(problems, list) and problems


# --- a reader who cannot check must not round up ---------------------------

def test_a_reader_without_crypto_gets_self_attested(monkeypatch, refusal):
    """Sealing is an optional extra, so a reader handed a sealed receipt may
    have no way to check it. "Cannot check" is not "does not verify" and is
    certainly not "verified": it degrades to the honest default, and it must
    not raise, because the receipt is still readable."""
    forged = dict(refusal)
    forged["seal"] = {"algorithm": "ed25519", "key_id": "sha256:" + "d" * 16,
                      "public_key": "x" * 44,
                      "sealed_at": "2026-11-23T09:00:00Z",
                      "signature": "y" * 88}
    from auditor.receipts import seal as S

    def unavailable(*a, **k):
        raise S.SealingUnavailable("no cryptography installed")
    monkeypatch.setattr(S, "_primitives", unavailable)
    assert E.assurance(forged) == E.SELF_ATTESTED
    assert E.assurance(forged, public_key="x" * 44) == E.SELF_ATTESTED


def test_a_bad_signature_does_not_reach_sealed(refusal):
    private, public = S.generate_keypair()
    sealed = S.seal(refusal, private, public)
    sealed["seal"]["signature"] = "z" * 88
    # The content is still intact, so this is a signature question, not a
    # tampering question, and it must land on self_attested rather than raise.
    assert E.assurance(sealed, public_key=public) == E.SELF_ATTESTED


def test_a_key_that_is_not_the_receipts_key_does_not_reach_sealed(refusal):
    private, public = S.generate_keypair()
    _, other = S.generate_keypair()
    sealed = S.seal(refusal, private, public)
    assert E.assurance(sealed, public_key=other) == E.SELF_ATTESTED
