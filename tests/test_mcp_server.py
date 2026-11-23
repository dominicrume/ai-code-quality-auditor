"""The MCP surface: protocol, the three tools, and the gate holding across it."""

import io
import json
import subprocess
import sys
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


def test_initialize_answers_an_unknown_protocol_version_with_our_own():
    res = mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                      "params": {"protocolVersion": "1999-01-01"}})
    assert res["result"]["protocolVersion"] == mcp.PROTOCOL_VERSION


def test_unknown_method_is_a_protocol_error():
    res = mcp.handle({"jsonrpc": "2.0", "id": 3, "method": "wat/list"})
    assert res["error"]["code"] == -32601


def test_resources_and_prompts_list_are_empty_not_an_error():
    """Clients call all three lists at startup. -32601 shows the user an error
    about a server that is working."""
    for method, key in (("resources/list", "resources"),
                        ("resources/templates/list", "resourceTemplates"),
                        ("prompts/list", "prompts")):
        res = mcp.handle({"jsonrpc": "2.0", "id": 3, "method": method})
        assert "error" not in res
        assert res["result"][key] == []


def test_a_batch_array_is_refused_without_killing_the_loop():
    """A batch used to reach .get on a list and take the whole session down."""
    stdout = io.StringIO()
    mcp.serve(stdin=io.StringIO('[{"jsonrpc":"2.0","id":1,"method":"ping"}]\n'
                                '{"jsonrpc":"2.0","id":2,"method":"ping"}\n'),
              stdout=stdout)
    lines = [json.loads(l) for l in stdout.getvalue().splitlines() if l.strip()]
    assert lines[0]["error"]["code"] == -32600
    assert "atch" in lines[0]["error"]["message"]
    assert lines[1]["id"] == 2          # the loop survived


def test_a_request_without_params_is_answered():
    assert mcp.handle(
        {"jsonrpc": "2.0", "id": 5, "method": "tools/list"})["result"]["tools"]


def test_null_arguments_are_treated_as_none_given():
    res = mcp.handle({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                      "params": {"name": "kya_standard", "arguments": None}})
    assert res["result"]["isError"] is False


def test_a_tool_call_before_initialize_still_works():
    """Some clients probe before the handshake; refusing is worse than serving."""
    assert _call("kya_standard", {})["result"]["isError"] is False


def test_tools_list_advertises_every_tool_without_leaking_handlers():
    """Named a fixed three before, so adding a tool failed this rather than
    checking it. The properties worth pinning hold for any number of tools:
    every registered tool is advertised, no Python callable crosses the wire,
    and each description is long enough for a model to route on."""
    tools = mcp.handle({"jsonrpc": "2.0", "id": 4, "method": "tools/list"})["result"]["tools"]
    assert {t["name"] for t in tools} == {t["name"] for t in mcp.TOOLS}
    assert {"kya_assess", "code_scan", "auditor_doctor"} <= {t["name"] for t in tools}
    for t in tools:
        assert "handler" not in t
        assert t["inputSchema"]["type"] == "object"
        assert len(t["description"]) > 80


def test_a_scan_reading_cannot_be_quoted_without_its_limits(tmp_path):
    """The whole reason this is exposed over MCP rather than only in a
    terminal. A human who saw `Security 2.40 OK` beside nine HIGH findings
    filed a bug report; a model reads the number and says the code is fine."""
    import json as _json
    (tmp_path / "a.ts").write_text("export function go(s){ return eval(s); }\n")
    res = _call("code_scan", {"path": str(tmp_path)})
    assert res["result"]["isError"] is False
    body = _json.loads(res["result"]["content"][0]["text"])
    assert body["limits"], "a reading with no stated limits is not a reading"
    assert any("not confirmed" in l for l in body["limits"])
    assert body["metrics"]["security_density"]["severity"]["HIGH"] == 1
    assert body["metrics"]["security_density"]["band"] != "good"


def test_a_scan_without_a_specification_says_intent_is_unknown(tmp_path):
    import json as _json
    (tmp_path / "a.py").write_text("x = 1\n")
    body = _json.loads(
        _call("code_scan", {"path": str(tmp_path)})["result"]["content"][0]["text"])
    assert any("No specification" in l for l in body["limits"])


def test_the_doctor_tool_reports_the_environment(tmp_path):
    import json as _json
    body = _json.loads(
        _call("auditor_doctor", {})["result"]["content"][0]["text"])
    assert "usable" in body
    assert any(c["name"].startswith("bandit") for c in body["checks"])


def test_every_reading_carries_the_instruments_open_defects(tmp_path):
    """A verdict whose known weakness is invisible to whoever relies on it is
    not an attestation, and an agent relies on it harder than a person does."""
    import json as _json
    from auditor.receipts import bundle
    declared = [d["id"] for d in bundle.open_defects()]
    if not declared:
        pytest.skip("nothing open to disclose")
    (tmp_path / "a.py").write_text("x = 1\n")
    body = _json.loads(
        _call("code_scan", {"path": str(tmp_path)})["result"]["content"][0]["text"])
    assert [d["id"] for d in body["instrument_open_defects"]] == declared


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


# --- robustness --------------------------------------------------------------

def test_a_file_instead_of_a_directory_says_so(tmp_path):
    f = tmp_path / "agent.py"
    f.write_text(AGENT["agent.py"])
    res = _call("kya_assess", {"path": str(f)})
    assert res["result"]["isError"] is True
    assert "is a file" in res["result"]["content"][0]["text"]


def test_a_directory_with_nothing_readable_concludes_nothing(tmp_path):
    (tmp_path / "picture.png").write_bytes(b"\x89PNG\r\n")
    res = _call("kya_classify_subject", {"path": str(tmp_path)})
    assert res["result"]["isError"] is True
    text = res["result"]["content"][0]["text"]
    assert "no readable source files" in text
    assert "nothing is concluded" in text


def test_the_path_is_echoed_as_given_not_resolved(tmp_path):
    """Echoing the resolved path would hand back the home or working directory
    for an argument of ~/x or '.'."""
    root = _write(tmp_path, AGENT)
    given = str(root) + "/."
    d = json.loads(_call("kya_assess", {"path": given})["result"]["content"][0]["text"])
    assert d["path"] == given


def test_a_long_unparsed_list_is_truncated_out_loud(tmp_path):
    for i in range(mcp.MAX_LISTED + 7):
        (tmp_path / f"broken{i}.py").write_text("def nope(:\n")
    _write(tmp_path, AGENT)
    d = json.loads(_call("kya_classify_subject",
                         {"path": str(tmp_path)})["result"]["content"][0]["text"])
    assert len(d["unparsed"]) == mcp.MAX_LISTED
    assert d["unparsed_omitted"] == 7          # never silently


# --- stdout purity -----------------------------------------------------------

def test_stdout_stays_pure_json_while_a_tool_logs(tmp_path):
    """The showstopper, pinned in the configuration that failed: a real process
    over a real pipe, as a client drives it.

    auditor.core.logger builds a StreamHandler(sys.stdout) at import time, so an
    unparseable .py file -- routine in a real repository -- wrote a log line
    into the middle of the protocol and the client dropped the connection.

    Driven in-process this proves nothing, because pytest has already replaced
    stdout. It has to be a subprocess."""
    root = _write(tmp_path, AGENT)
    (root / "oops.py").write_text("def broken(:\n")

    requests = "".join(json.dumps(m) + "\n" for m in (
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                    "clientInfo": {"name": "pipe", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
         "params": {"name": "kya_classify_subject",
                    "arguments": {"path": str(root)}}},
    ))
    repo = Path(__file__).parent.parent
    proc = subprocess.run(
        [sys.executable, "-c",
         "from auditor.mcp.server import serve; serve()"],
        input=requests, capture_output=True, text=True, cwd=repo,
        timeout=120, check=False,
    )

    assert proc.returncode == 0
    # Every line on stdout parses as JSON-RPC, and nothing else is there.
    messages = [json.loads(l) for l in proc.stdout.splitlines() if l.strip()]
    assert [m["id"] for m in messages] == [1, 2]
    assert "could not parse" not in proc.stdout
    assert "could not parse" in proc.stderr      # it went to the right channel

    d = json.loads(messages[1]["result"]["content"][0]["text"])
    assert d["unparsed"] == ["oops.py"]


def test_the_quarantine_restores_stdout_afterwards(capfd):
    before = sys.stdout
    with mcp.quarantine_stdout():
        print("engine noise")
    assert sys.stdout is before
    print("protocol")
    out = capfd.readouterr()
    assert "engine noise" not in out.out
    assert "engine noise" in out.err
    assert "protocol" in out.out


def test_a_broken_pipe_is_a_clean_exit():
    class Gone(io.StringIO):
        def write(self, _):
            raise BrokenPipeError(32, "broken pipe")

    mcp.serve(stdin=io.StringIO('{"jsonrpc":"2.0","id":1,"method":"ping"}\n'),
              stdout=Gone())      # returns rather than raising


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
