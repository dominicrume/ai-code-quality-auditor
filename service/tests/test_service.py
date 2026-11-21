"""The sealing service: authentication, the paywall, and what it never stores."""
import hashlib
import json
import os
import secrets
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from auditor.adapters._shared import load_codebase          # noqa: E402
from auditor.governance import constitution as con           # noqa: E402
from auditor.receipts import bundle                          # noqa: E402
from auditor.receipts import seal as seal_mod                # noqa: E402

AGENT = (
    "import anthropic\n"
    "MAX_SPEND = 500\n"
    "def act(action, tool_calls):\n"
    "    if action.cost > MAX_SPEND:\n"
    "        return require_approval(action)\n"
    "    audit_log.write(action)\n"
    "    return run_tool(action)\n"
)
API_KEY = "kya_" + secrets.token_urlsafe(16)
ORG = "org_test"


@pytest.fixture
def client(tmp_path, monkeypatch):
    priv, pub = seal_mod.generate_keypair()
    monkeypatch.setenv("AUDITOR_SEAL_PRIVATE_KEY", priv)
    monkeypatch.setenv("AUDITOR_SEAL_PUBLIC_KEY", pub)
    monkeypatch.setenv(
        "AUDITOR_API_KEYS",
        f"{ORG}:{hashlib.sha256(API_KEY.encode()).hexdigest()}")
    monkeypatch.setenv("AUDITOR_LEDGER_PATH", str(tmp_path / "outcomes.jsonl"))
    monkeypatch.setenv("AUDITOR_FREE_QUOTA", "2")
    monkeypatch.setenv("AUDITOR_BILLING_ENABLED", "false")
    import app as service_app
    service_app.app.config.update(TESTING=True)
    c = service_app.app.test_client()
    c._public_key = pub
    return c


@pytest.fixture
def finding(tmp_path):
    subject = tmp_path / "subject"
    subject.mkdir()
    (subject / "agent.py").write_text(AGENT)
    cb = load_codebase(str(subject))
    std = con.load_standard("specs/kya_constitution_v1.yaml")
    return bundle.build(cb, std, con.evaluate(cb, std))


def call(client, tool, args, key=API_KEY):
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    res = client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": tool, "arguments": args}}, headers=headers)
    return res


def payload(res):
    return json.loads(res.get_json()["result"]["content"][0]["text"])


# --- authentication ---------------------------------------------------------

def test_no_key_is_refused(client, finding):
    res = call(client, "seal_finding", {"finding": finding}, key=None)
    assert res.status_code == 401
    assert "no API key" in res.get_json()["error"]["message"]


def test_a_wrong_key_is_refused(client, finding):
    res = call(client, "seal_finding", {"finding": finding}, key="kya_wrong")
    assert res.status_code == 401
    assert "not recognised" in res.get_json()["error"]["message"]


def test_an_x_api_key_header_also_works(client):
    res = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
                      headers={"x-api-key": API_KEY})
    assert res.status_code == 200


# --- the protocol -----------------------------------------------------------

def test_initialize_and_tools_list(client):
    res = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1,
                                    "method": "initialize", "params": {}},
                      headers={"Authorization": f"Bearer {API_KEY}"})
    assert res.get_json()["result"]["serverInfo"]["name"] == "kya-sealing-service"
    res = client.post("/mcp", json={"jsonrpc": "2.0", "id": 2,
                                    "method": "tools/list"},
                      headers={"Authorization": f"Bearer {API_KEY}"})
    names = {t["name"] for t in res.get_json()["result"]["tools"]}
    assert names == {"seal_finding", "sealing_quota", "sealing_public_key"}


def test_a_notification_is_accepted_without_a_body(client):
    res = client.post("/mcp", json={"jsonrpc": "2.0",
                                    "method": "notifications/initialized"},
                      headers={"Authorization": f"Bearer {API_KEY}"})
    assert res.status_code == 202


def test_batches_are_refused_explicitly(client):
    res = client.post("/mcp", json=[{"jsonrpc": "2.0", "id": 1, "method": "ping"}],
                      headers={"Authorization": f"Bearer {API_KEY}"})
    assert res.status_code == 400
    assert "batches are not supported" in res.get_json()["error"]["message"]


# --- sealing ----------------------------------------------------------------

def test_sealing_returns_a_receipt_that_verifies_offline(client, finding):
    body = payload(call(client, "seal_finding", {"finding": finding}))
    report = seal_mod.verify(body["receipt"], client._public_key)
    assert report["signature_valid"] is True and report["content_intact"]


def test_the_finding_digest_survives_sealing(client, finding):
    body = payload(call(client, "seal_finding", {"finding": finding}))
    assert body["receipt"]["finding_digest"] == finding["finding_digest"]


def test_a_tampered_finding_is_refused_and_not_charged(client, finding):
    forged = dict(finding)
    forged["verdict"] = "PASS"
    res = call(client, "seal_finding", {"finding": forged})
    assert res.get_json()["result"]["isError"] is True
    assert "altered since it was computed" in payload(res)["error"]
    assert payload(call(client, "sealing_quota", {}))["billable_outcomes"] == 0


def test_an_already_sealed_finding_is_refused(client, finding):
    first = payload(call(client, "seal_finding", {"finding": finding}))["receipt"]
    res = call(client, "seal_finding", {"finding": first})
    assert res.get_json()["result"]["isError"] is True
    assert "already carries a seal" in payload(res)["error"]


def test_a_finding_sent_as_json_text_is_accepted(client, finding):
    body = payload(call(client, "seal_finding",
                        {"finding": json.dumps(finding)}))
    assert "receipt" in body


def test_rubbish_input_is_a_tool_error_not_a_crash(client):
    res = call(client, "seal_finding", {"finding": "not json at all"})
    assert res.get_json()["result"]["isError"] is True


# --- the paywall ------------------------------------------------------------

def test_resealing_identical_work_is_one_outcome(client, finding):
    call(client, "seal_finding", {"finding": finding})
    assert payload(call(client, "sealing_quota", {}))["billable_outcomes"] == 1


def test_the_service_refuses_past_the_free_quota_rather_than_sealing_free(
        client, finding):
    """A seal implies somebody stands behind it. With no billing configured,
    refusing is the honest behaviour."""
    for i in range(2):
        body = dict(finding)
        body["chain"] = {"previous": f"sha256:{i:064d}"}
        body["finding_digest"] = bundle.recompute(body)
        assert "receipt" in payload(call(client, "seal_finding", {"finding": body}))
    third = dict(finding)
    third["chain"] = {"previous": f"sha256:{9:064d}"}
    third["finding_digest"] = bundle.recompute(third)
    res = call(client, "seal_finding", {"finding": third})
    assert res.get_json()["result"]["isError"] is True
    assert "free quota of 2" in payload(res)["error"]


def test_quota_reports_without_leaking_other_organisations(client, finding):
    call(client, "seal_finding", {"finding": finding})
    body = payload(call(client, "sealing_quota", {}))
    assert body["org_id"] == ORG
    assert "digests" not in body


# --- what it never stores ---------------------------------------------------

def test_no_source_reaches_the_ledger(client, finding, tmp_path):
    call(client, "seal_finding", {"finding": finding})
    recorded = (tmp_path / "outcomes.jsonl").read_text()
    assert "MAX_SPEND" not in recorded
    assert "agent.py" not in recorded
    assert "import anthropic" not in recorded


def test_the_api_key_is_never_echoed_anywhere(client, finding):
    body = payload(call(client, "seal_finding", {"finding": finding}))
    assert API_KEY not in json.dumps(body)


def test_the_private_key_is_never_returned(client, finding):
    body = payload(call(client, "seal_finding", {"finding": finding}))
    assert os.environ["AUDITOR_SEAL_PRIVATE_KEY"] not in json.dumps(body)
    pub = payload(call(client, "sealing_public_key", {}))
    assert pub["public_key"] == client._public_key
    assert os.environ["AUDITOR_SEAL_PRIVATE_KEY"] not in json.dumps(pub)


# --- operational ------------------------------------------------------------

def test_healthz_says_whether_it_can_seal(client):
    body = client.get("/healthz").get_json()
    assert body["ok"] is True and body["can_seal"] is True
    assert body["organisations_configured"] == 1


def test_the_public_key_is_served_without_a_key(client):
    body = client.get("/.well-known/kya-public-key").get_json()
    assert body["public_key"] == client._public_key


def test_sealing_is_refused_when_no_key_is_configured(client, finding, monkeypatch):
    monkeypatch.delenv("AUDITOR_SEAL_PRIVATE_KEY")
    res = call(client, "seal_finding", {"finding": finding})
    assert res.get_json()["result"]["isError"] is True
    assert "not configured to seal" in payload(res)["error"]
