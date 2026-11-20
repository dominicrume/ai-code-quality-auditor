"""The conformance check as an MCP server, over stdio, with no dependencies.

The point of this surface is that nobody adopts anything. A team already runs
Claude Code, Cursor, or an agent of their own. This server registers three
tools in whatever they run, so the check happens where the work happens and the
answer arrives in the conversation that asked for it.

It speaks JSON-RPC 2.0 over newline-delimited stdin and stdout, which is all
MCP's stdio transport is. Writing it by hand rather than against an SDK keeps
the published package's runtime dependencies unchanged, which matters for an
instrument whose first principle is that the same input gives the same number.

What it will not do is answer a question that does not apply. ``kya_assess``
runs the subject gate first, and a codebase that does not both call a model and
have a path by which the result acts gets NOT_APPLICABLE, no score, and the
reason. That is the behaviour the tool exists to demonstrate.
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path
from typing import Any, Callable

from auditor.adapters._shared import load_codebase
from auditor.governance import constitution as con
from auditor.governance import subject as subj

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "ai-code-quality-auditor"

# The repository's specs/ copy is authoritative when running from a checkout.
# An installed wheel does not carry specs/ (the spec box is data, not code), so
# the same file ships as package data under auditor/standards/.
REPO_STANDARD = (
    Path(__file__).resolve().parents[2] / "specs" / "kya_constitution_v1.yaml"
)


# ---------------------------------------------------------------------------
# The tools
# ---------------------------------------------------------------------------

def _standard_path(given: str | None) -> Path:
    if given:
        supplied = Path(given).expanduser()
        if not supplied.exists():
            raise FileNotFoundError(f"no such standard: {supplied}")
        return supplied
    if REPO_STANDARD.exists():
        return REPO_STANDARD
    from auditor.standards import path as packaged
    return packaged()


def _codebase(path: str) -> tuple[dict, Path]:
    root = Path(path).expanduser()
    if not root.exists():
        raise FileNotFoundError(f"no such path: {root}")
    return load_codebase(str(root)), root


def tool_kya_classify(args: dict) -> str:
    """Is this an agent at all."""
    codebase, root = _codebase(args["path"])
    s = subj.classify(codebase)
    return json.dumps({
        "path": str(root),
        "subject": s.kind,
        "is_agent": s.is_agent,
        "standard_applies": s.applicable,
        "coverage": round(s.coverage, 3),
        "model_evidence": s.model_evidence,
        "action_evidence": s.action_evidence,
        "unparsed": s.unparsed[:10],
        "note": s.note,
    }, indent=2)


def tool_kya_assess(args: dict) -> str:
    """The five elements, graded, behind the subject gate."""
    codebase, root = _codebase(args["path"])
    standard = con.load_standard(_standard_path(args.get("standard_path")))
    v = con.evaluate(codebase, standard)
    out: dict[str, Any] = {
        "path": str(root),
        "standard": f"{v.standard} v{v.version}",
        "verdict": v.verdict,
        "subject": v.subject_kind,
        "coverage": round(v.coverage, 3),
        "note": v.note,
    }
    if v.verdict == "NOT_APPLICABLE":
        out["score"] = None
        out["elements"] = []
        out["disclosure"] = (
            "No score was produced. A standard about autonomous agents has "
            "nothing to say about this subject."
        )
    else:
        out["score_over_readable"] = v.score
        out["grades"] = {"measured": v.measured,
                         "provisional": v.provisional,
                         "withheld": v.withheld}
        out["elements"] = [{
            "id": r.id,
            "basis": r.basis,
            "satisfied": r.passed,
            "grade": r.grade,
            "evidence": r.evidence,
            "requirement": r.description,
        } for r in v.results]
        out["disclosure"] = (
            "This is a reading, not an attestation. A provisional element "
            "rests on a marker in source rather than on observed behaviour, "
            "and a withheld element was not established either way."
        )
    return json.dumps(out, indent=2)


def tool_kya_standard(args: dict) -> str:
    """What the standard asks, and what it refuses to conclude."""
    standard = con.load_standard(_standard_path(args.get("standard_path")))
    return json.dumps({
        "standard": standard.get("standard"),
        "version": standard.get("version"),
        "elements": [{
            "id": e["id"],
            "basis": e.get("basis"),
            "requirement": " ".join(e.get("description", "").split()),
            "what_a_code_read_can_establish": (
                "The artefact is the compliance, so absence is a measured "
                "failure." if e.get("basis") == "artefact" else
                "A scan sees a marker, never the behaviour. A marker found is "
                "provisional; none found is withheld, not failed."
            ),
        } for e in standard.get("elements", [])],
        "aggregation": (
            "Any withheld element makes the verdict INCOMPLETE rather than "
            "PASS, because a standard only partly measured is not a standard "
            "passed. There is no threshold to tune."
        ),
        "subject_gate": (
            "An agent is two things at once: something that calls a model, and "
            "a path by which the result acts. Anything else returns "
            "NOT_APPLICABLE with no score."
        ),
    }, indent=2)


TOOLS: list[dict] = [
    {
        "name": "kya_assess",
        "description": (
            "Assess an agent codebase against the five KYA conformance "
            "elements: bounded powers, separation of duty, an action and "
            "refusal record, a versioned amendment path, and named "
            "accountability. Returns a verdict, each element with its evidence "
            "grade, and an explicit statement of what could not be "
            "established. Returns NOT_APPLICABLE with no score when the "
            "subject is not an agent. Use before a security or risk review, or "
            "when asked whether an agent is governed, safe to deploy "
            "unsupervised, or ready for sign-off."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string",
                         "description": "Directory of the agent codebase to assess."},
                "standard_path": {"type": "string",
                                  "description": "Optional path to a standard YAML. Defaults to KYA v1."},
            },
            "required": ["path"],
        },
        "handler": tool_kya_assess,
    },
    {
        "name": "kya_classify_subject",
        "description": (
            "Decide whether a codebase is an autonomous agent before any "
            "standard is applied to it. Reports the evidence for a model call "
            "and for a path by which its output acts, plus how much of the "
            "source could be parsed. Use to check that a governance question "
            "applies at all."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory to classify."},
            },
            "required": ["path"],
        },
        "handler": tool_kya_classify,
    },
    {
        "name": "kya_standard",
        "description": (
            "Return the KYA standard itself: the five elements, what a static "
            "read of code can honestly establish about each, how the aggregate "
            "verdict is formed, and the subject gate. Use to explain what the "
            "check measures and what it declines to conclude."
        ),
        "inputSchema": {"type": "object", "properties": {
            "standard_path": {"type": "string",
                              "description": "Optional path to a standard YAML."},
        }},
        "handler": tool_kya_standard,
    },
]

_HANDLERS: dict[str, Callable[[dict], str]] = {t["name"]: t["handler"] for t in TOOLS}


def _advertised() -> list[dict]:
    return [{k: v for k, v in t.items() if k != "handler"} for t in TOOLS]


# ---------------------------------------------------------------------------
# JSON-RPC 2.0 over stdio
# ---------------------------------------------------------------------------

def _result(mid: Any, payload: dict) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "result": payload}


def _error(mid: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def handle(message: dict) -> dict | None:
    """One request in, one response out. None for a notification."""
    method = message.get("method")
    mid = message.get("id")
    params = message.get("params") or {}

    # A notification has no id and takes no response, including
    # notifications/initialized and notifications/cancelled.
    if mid is None:
        return None

    if method == "initialize":
        return _result(mid, {
            "protocolVersion": params.get("protocolVersion") or PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": _version()},
            "instructions": (
                "Conformance assessment for autonomous agents against the KYA "
                "standard. Call kya_standard to learn what is measured. The "
                "assessment declines to score a subject that is not an agent, "
                "and labels every element with what the reading rests on."
            ),
        })

    if method == "ping":
        return _result(mid, {})

    if method == "tools/list":
        return _result(mid, {"tools": _advertised()})

    if method == "tools/call":
        name = params.get("name")
        handler = _HANDLERS.get(name)
        if handler is None:
            return _error(mid, -32602, f"unknown tool: {name}")
        try:
            text = handler(params.get("arguments") or {})
            return _result(mid, {"content": [{"type": "text", "text": text}]})
        except KeyError as exc:
            return _result(mid, {
                "content": [{"type": "text", "text": f"missing argument: {exc}"}],
                "isError": True,
            })
        except Exception as exc:  # a tool failure is a result, not a protocol error
            return _result(mid, {
                "content": [{"type": "text",
                             "text": f"{type(exc).__name__}: {exc}"}],
                "isError": True,
            })

    return _error(mid, -32601, f"method not found: {method}")


def _version() -> str:
    try:
        from importlib.metadata import version
        return version("ai-code-quality-auditor")
    except Exception:
        return "0"


def serve(stdin=None, stdout=None) -> None:
    """Read requests until the stream closes. Never writes to stdout but JSON."""
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            response = _error(None, -32700, "parse error")
        else:
            try:
                response = handle(message)
            except Exception:
                traceback.print_exc(file=sys.stderr)
                response = _error(message.get("id"), -32603, "internal error")
        if response is not None:
            stdout.write(json.dumps(response) + "\n")
            stdout.flush()
