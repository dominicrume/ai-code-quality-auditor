"""The MCP surface: protocol, the three tools, and the gate holding across it."""
import io
import json
from pathlib import Path

from auditor.mcp import server as mcp


AGENT = {
    "agent.py": (
        "import anthropic\n"
        "MAX_SPEND = 500\n"
        "def act(action, tool_calls):\n"
        "    if action.cost > MAX_SPEND:\n"
        "        return require_approval(action)\n"
        "    audit_log.write(action)\n"
        "    if not permitted(action):\n"
        "        audit_log.write_refusal(action)\n"
        "        return denied(action)\n"
        "    return run_tool(action)\n"
    ),
}

NOT_AN_AGENT = {"util.py": "import requests\ndef post(x):\n    return requests.post(x)\n"}


def _write(tmp_path: Path, files: dict) -> Path:
    for name, body in files.items():
        (tmp_path / name).write_text(body)
    return tmp_path


def _call(name: str, args: dict) -> dict:
    res = mcp.handle({"jsonrpc": "2.0", "id": 9, "method": "tools/call",
                      "params": {"name": name, "arguments": args}})
    assert res is not None
    return res


# --- protocol ---------------------------------------------------------------

def test_initialize_answers_with_capabilities_and_server_info():
    res = mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                      "params": {"protocolVersion": "2024-11-05"}})
    r = res["result"]
    assert r["protocolVersion"] == "2024-11-05"
    assert "tools" in r["capabilities"]
    assert r["serverInfo"]["name"] == "ai-code-quality-auditor"


def test_initialize_echoes_a_client_protocol_version():
    res = mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                      "params": {"protocolVersion": "2025-06-18"}})
    assert res["result"]["protocolVersion"] == "2025-06-18"


def test_a_notification_gets_no_response():
    assert mcp.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_ping_is_answered():
    assert mcp.handle({"jsonrpc": "2.0", "id": 2, "method": "ping"})["result"] == {}


def test_unknown_method_is_a_protocol_error():
    res = mcp.handle({"jsonrpc": "2.0", "id": 3, "method": "resources/list"})
    assert res["error"]["code"] == -32601


def test_tools_list_advertises_three_tools_without_leaking_handlers():
    tools = mcp.handle({"jsonrpc": "2.0", "id": 4, "method": "tools/list"})["result"]["tools"]
    assert {t["name"] for t in tools} == {
        "kya_assess", "kya_classify_subject", "kya_standard"}
    for t in tools:
        assert "handler" not in t
        assert t["inputSchema"]["type"] == "object"
        assert len(t["description"]) > 80


def test_unknown_tool_is_rejected():
    assert _call("kya_nonsense", {})["error"]["code"] == -32602


def test_a_missing_path_is_a_tool_error_not_a_crash():
    res = _call("kya_assess", {"path": "/definitely/not/here"})
    assert res["result"]["isError"] is True
    assert "FileNotFoundError" in res["result"]["content"][0]["text"]


def test_a_missing_required_argument_is_a_tool_error():
    res = _call("kya_assess", {})
    assert res["result"]["isError"] is True
    assert "missing argument" in res["result"]["content"][0]["text"]


# --- the tools --------------------------------------------------------------

def test_assess_scores_an_agent_and_grades_every_element(tmp_path):
    root = _write(tmp_path, AGENT)
    d = json.loads(_call("kya_assess", {"path": str(root)})["result"]["content"][0]["text"])
    assert d["subject"] == "agent"
    assert d["verdict"] in ("PASS", "FAIL", "INCOMPLETE")
    assert len(d["elements"]) == 5
    for e in d["elements"]:
        assert e["grade"] in ("measured", "provisional", "withheld")
    assert "reading, not an attestation" in d["disclosure"]


def test_assess_declines_to_score_a_subject_that_is_not_an_agent(tmp_path):
    """The behaviour the surface exists to demonstrate."""
    root = _write(tmp_path, NOT_AN_AGENT)
    d = json.loads(_call("kya_assess", {"path": str(root)})["result"]["content"][0]["text"])
    assert d["verdict"] == "NOT_APPLICABLE"
    assert d["score"] is None
    assert d["elements"] == []
    assert "does not apply" in d["note"]


def test_classify_reports_both_halves_of_the_gate(tmp_path):
    root = _write(tmp_path, AGENT)
    d = json.loads(_call("kya_classify_subject",
                         {"path": str(root)})["result"]["content"][0]["text"])
    assert d["is_agent"] is True and d["standard_applies"] is True
    assert d["model_evidence"] and d["action_evidence"]


def test_standard_states_what_it_refuses_to_conclude():
    d = json.loads(_call("kya_standard", {})["result"]["content"][0]["text"])
    assert d["standard"] == "kya"
    assert len(d["elements"]) == 5
    assert "INCOMPLETE" in d["aggregation"]
    assert "NOT_APPLICABLE" in d["subject_gate"]


def test_a_supplied_standard_that_does_not_exist_is_an_error(tmp_path):
    root = _write(tmp_path, AGENT)
    res = _call("kya_assess", {"path": str(root), "standard_path": "/no/spec.yaml"})
    assert res["result"]["isError"] is True


# --- the loop ---------------------------------------------------------------

def test_serve_reads_a_stream_and_skips_blank_lines():
    stdin = io.StringIO(
        '{"jsonrpc":"2.0","id":1,"method":"ping"}\n'
        "\n"
        '{"jsonrpc":"2.0","method":"notifications/initialized"}\n'
        '{"jsonrpc":"2.0","id":2,"method":"tools/list"}\n'
    )
    stdout = io.StringIO()
    mcp.serve(stdin=stdin, stdout=stdout)
    lines = [json.loads(l) for l in stdout.getvalue().splitlines() if l.strip()]
    assert [m["id"] for m in lines] == [1, 2]   # the notification produced nothing


def test_malformed_json_is_a_parse_error_and_the_loop_survives():
    stdout = io.StringIO()
    mcp.serve(stdin=io.StringIO('not json\n{"jsonrpc":"2.0","id":7,"method":"ping"}\n'),
              stdout=stdout)
    lines = [json.loads(l) for l in stdout.getvalue().splitlines() if l.strip()]
    assert lines[0]["error"]["code"] == -32700
    assert lines[1]["id"] == 7


# --- packaging --------------------------------------------------------------

def test_the_packaged_standard_matches_the_authoring_spec():
    """specs/ is authoritative and excluded from the wheel. The packaged copy
    must not drift from it."""
    from auditor.standards import path as packaged
    authored = Path(__file__).parent.parent / "specs" / "kya_constitution_v1.yaml"
    assert packaged().read_text() == authored.read_text(), (
        "auditor/standards/kya_constitution_v1.yaml has drifted from "
        "specs/kya_constitution_v1.yaml. Copy the authoring spec over it."
    )
