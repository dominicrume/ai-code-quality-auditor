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

import contextlib
import io
import json
import logging
import os
import sys
import traceback
from pathlib import Path
from typing import Any, Callable

from auditor.adapters._shared import CODE_SUFFIXES, load_codebase
from auditor.governance import constitution as con
from auditor.governance import subject as subj

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "ai-code-quality-auditor"

# Versions of the MCP protocol this server will speak back. A client asking for
# anything else is answered with ours, which is what the spec requires: echoing
# a version we have never heard of is a promise we cannot keep.
SUPPORTED_PROTOCOLS = frozenset({
    "2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25",
})

# How many unparsed-file names a tool result will carry. The rest are counted,
# never dropped in silence: a truncation the caller cannot see is a lie about
# the reading.
MAX_LISTED = 25

# The repository's specs/ copy is authoritative when running from a checkout.
# An installed wheel does not carry specs/ (the spec box is data, not code), so
# the same file ships as package data under auditor/standards/.
REPO_STANDARD = (
    Path(__file__).resolve().parents[2] / "specs" / "kya_constitution_v1.yaml"
)


# ---------------------------------------------------------------------------
# Keeping stdout pure
# ---------------------------------------------------------------------------
#
# FINDING: the stdio transport is a single channel of newline-delimited JSON.
# One stray byte on it and the client drops the connection. The engine this
# server calls into logs through ``auditor.core.logger.get_logger``, whose
# handler is a ``StreamHandler(sys.stdout)``, so an ordinary warning -- a .py
# file that will not parse, which is a routine thing to meet in a real
# repository -- wrote a log line into the middle of the protocol and killed the
# session.
#
# Reassigning ``sys.stdout`` is not enough: the logging handler captured the
# stream object when the logger was first built, at import time, so it holds a
# writer onto file descriptor 1 whatever ``sys.stdout`` later points at. So the
# redirect happens at the descriptor: for the duration of a tool call, fd 1 is
# pointed at fd 2. Anything the engine writes to stdout -- log record, print,
# rich console, warning, C-level write -- lands on stderr, where a client
# treats it as diagnostics. Responses are written outside this window, onto the
# restored descriptor.


def _stdout_handlers() -> list[logging.StreamHandler]:
    """Every live logging handler currently writing to stdout.

    A ``StreamHandler`` captures its stream object when it is built, so it
    keeps writing to whatever stdout was at import time no matter what
    ``sys.stdout`` is rebound to later. Each one is re-pointed for the
    duration of a tool call and put back afterwards.
    """
    streams = {id(s) for s in (sys.stdout, sys.__stdout__) if s is not None}
    loggers: list[Any] = [logging.getLogger()]
    loggers += [lg for lg in logging.Logger.manager.loggerDict.values()
                if isinstance(lg, logging.Logger)]
    found = []
    for lg in loggers:
        for h in list(lg.handlers):
            if not isinstance(h, logging.StreamHandler):
                continue
            stream = getattr(h, "stream", None)
            if stream is None:
                continue
            if id(stream) in streams:
                found.append(h)
                continue
            with contextlib.suppress(Exception):
                if stream.fileno() == 1:
                    found.append(h)
    return found


@contextlib.contextmanager
def quarantine_stdout():
    """For the duration of the block, stdout is stderr.

    Three redirections, because each covers a hole the others do not:
    ``sys.stdout`` for new writers, file descriptor 1 for anything holding the
    descriptor (including C-level writes), and each live logging handler's own
    stream reference, for handlers built before this ran.
    """
    saved_obj = sys.stdout
    handlers = [(h, h.stream) for h in _stdout_handlers()]
    for handler, _ in handlers:
        with contextlib.suppress(Exception):
            handler.setStream(sys.stderr)
    with contextlib.suppress(Exception):
        saved_obj.flush()

    out_fd = err_fd = None
    try:
        err_fd = sys.stderr.fileno()
        out_fd = 1
        os.fstat(out_fd)
    except (AttributeError, OSError, ValueError, io.UnsupportedOperation):
        out_fd = err_fd = None

    duplicate = None
    if out_fd is not None and err_fd is not None and out_fd != err_fd:
        try:
            duplicate = os.dup(out_fd)
            os.dup2(err_fd, out_fd)
        except OSError:
            duplicate = None

    sys.stdout = sys.stderr
    try:
        yield
    finally:
        sys.stdout = saved_obj
        with contextlib.suppress(Exception):
            sys.stderr.flush()
        for handler, stream in handlers:
            with contextlib.suppress(Exception):
                handler.setStream(stream)
        if duplicate is not None:
            with contextlib.suppress(OSError):
                os.dup2(duplicate, out_fd)
            with contextlib.suppress(OSError):
                os.close(duplicate)


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


def _given_path(args: dict) -> str:
    """The ``path`` argument, as a non-empty string.

    ``arguments`` arriving as ``null`` or without ``path`` is a client error
    worth a readable message rather than a KeyError's bare repr.
    """
    value = args.get("path")
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            "missing argument: 'path' (a directory to read) is required")
    return value


def _codebase(path: str) -> tuple[dict, str]:
    """Load a codebase, failing with a sentence a client can act on.

    The path is echoed back exactly as the caller gave it. Reporting the
    resolved absolute path instead would hand back the home directory or the
    server's working directory for an argument of ``~/x`` or ``.`` -- more of
    the filesystem than the caller asked about.
    """
    root = Path(path).expanduser()
    if not root.exists():
        raise FileNotFoundError(f"no such path: {path}")
    if not root.is_dir():
        raise NotADirectoryError(
            f"{path} is a file. This check reads a whole codebase; "
            "pass the directory that contains it."
        )
    codebase = load_codebase(str(root))
    if not codebase.get("files"):
        raise ValueError(
            f"no readable source files under {path} "
            f"(looked for {', '.join(sorted(CODE_SUFFIXES))}). "
            "Nothing was read, so nothing is concluded."
        )
    return codebase, path


def _listed(items: list, key: str, out: dict) -> None:
    """Put at most MAX_LISTED entries in ``out``, and say how many were left."""
    out[key] = items[:MAX_LISTED]
    if len(items) > MAX_LISTED:
        out[f"{key}_omitted"] = len(items) - MAX_LISTED


def tool_kya_classify(args: dict) -> str:
    """Is this an agent at all."""
    codebase, root = _codebase(_given_path(args))
    s = subj.classify(codebase)
    body: dict[str, Any] = {
        "path": root,
        "subject": s.kind,
        "is_agent": s.is_agent,
        "standard_applies": s.applicable,
        "coverage": round(s.coverage, 3),
        "files_read": len(codebase.get("files", {})),
        "model_evidence": s.model_evidence,
        "action_evidence": s.action_evidence,
        "note": s.note,
    }
    _listed(s.unparsed, "unparsed", body)
    return json.dumps(body, indent=2)


def tool_kya_assess(args: dict) -> str:
    """The five elements, graded, behind the subject gate."""
    codebase, root = _codebase(_given_path(args))
    standard = con.load_standard(_standard_path(args.get("standard_path")))
    v = con.evaluate(codebase, standard)
    out: dict[str, Any] = {
        "path": root,
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


def tool_doctor(args: dict) -> str:
    """What this installation can and cannot do.

    The first tool an agent should reach for when a reading looks wrong or a
    call fails. Two of the three field reports on 23 November 2026 were a
    correct install that could not find bandit and a correct install the shell
    could not see. Both left a human guessing; over MCP they would leave a
    model guessing, which is worse, because a model guesses fluently.
    """
    from auditor.core.doctor import run
    return json.dumps(run().as_dict(), indent=2)


def tool_code_scan(args: dict) -> str:
    """The quality reading, with its limits as fields rather than as prose.

    Why this exists over MCP at all: every installation failure reported from
    the field was a command-line failure. There is no PATH here, no console
    script and no activation step -- the host starts this server with an
    interpreter that already has the package. Running the scan through MCP
    removes that entire class of problem rather than documenting around it.

    Why the limits are fields: a human who read `Security 2.40 OK` beside nine
    HIGH findings was suspicious enough to file a report. A model reads the
    number and says the code is fine. So what the reading does not cover is
    returned as structured data an agent has to step over deliberately, not as
    a sentence at the bottom it can summarise away.
    """
    from auditor.core.scan import scan_directory

    codebase, root = _codebase(_given_path(args))
    result = scan_directory(Path(_given_path(args)).expanduser())

    metrics: dict[str, Any] = {}
    for o in result.outcomes:
        if not o.applicable:
            metrics[o.name] = {"measured": False, "why_not": o.skipped_reason}
            continue
        entry: dict[str, Any] = {
            "measured": True,
            "value": o.value,
            "unit": o.unit,
            "band": o.band,
            "count": o.count,
            "coverage": o.coverage,
        }
        diagnostics = getattr(o, "diagnostics", None) or {}
        if diagnostics.get("severity"):
            entry["severity"] = diagnostics["severity"]
        if diagnostics.get("unavailable"):
            entry["not_analysed"] = diagnostics["unavailable"]
        if o.details:
            _listed(list(o.details), "findings", entry)
        metrics[o.name] = entry

    # Everything a reader is entitled to before quoting any number above.
    limits: list[str] = [
        "Static matches, not confirmed exploitable vulnerabilities. Each one "
        "needs a human to decide whether the input is attacker-controlled and "
        "whether the code is reachable.",
    ]
    aside = result.not_authored or {}
    if aside:
        kinds: dict[str, int] = {}
        for kind in aside.values():
            kinds[kind] = kinds.get(kind, 0) + 1
        limits.append(
            f"{len(aside)} files were not measured ("
            + ", ".join(f"{n} {k.replace('_', ' ')}" for k, n in sorted(kinds.items()))
            + ") because this project redistributes or builds them rather than "
            "writing them. Do not propose edits to those files.")
    if not result.spec_name:
        limits.append(
            "No specification was supplied, so nothing is known about what "
            "this project was asked to build. Feature completeness and scope "
            "drift are not reported and must not be inferred.")

    body: dict[str, Any] = {
        "path": root,
        "files_measured": result.file_count,
        "lines_measured": result.total_loc,
        "worst_band": result.worst_band,
        "specification": result.spec_name,
        "metrics": metrics,
        "limits": limits,
    }
    if aside:
        _listed([f"{k}: {p}" for p, k in sorted(aside.items())], "not_measured", body)
    # Known defects in this instrument, carried with every reading it produces.
    from auditor.receipts import bundle
    defects = bundle.open_defects()
    if defects:
        body["instrument_open_defects"] = [
            {"id": d["id"], "affects": d.get("affects")} for d in defects]
    return json.dumps(body, indent=2)


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
    {
        "name": "code_scan",
        "description": (
            "Measure code quality in a directory: security findings by "
            "severity, complexity, duplication, and -- when a specification "
            "is present -- which requested features were delivered. Returns "
            "every reading with its coverage and band, plus an explicit "
            "`limits` list stating what the reading does not cover: static "
            "matches are not confirmed vulnerabilities, vendored and generated "
            "files are excluded and must not be edited, and nothing is known "
            "about intent without a specification. Read `limits` before "
            "summarising any number from this tool."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string",
                         "description": "Directory to scan."},
            },
            "required": ["path"],
        },
        "handler": tool_code_scan,
    },
    {
        "name": "auditor_doctor",
        "description": (
            "Report what this installation of the auditor can and cannot do, "
            "and the exact command to fix anything missing. Call this first "
            "when a tool here fails, when a reading looks wrong, or when a "
            "user reports that the `auditor` command is not found. Names any "
            "defect already known to be open in the instrument."
        ),
        "inputSchema": {"type": "object", "properties": {}},
        "handler": tool_doctor,
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


def _negotiated(asked: Any) -> str:
    """The version to answer with: the client's if we speak it, else ours."""
    if isinstance(asked, str) and asked in SUPPORTED_PROTOCOLS:
        return asked
    return PROTOCOL_VERSION


def handle(message: Any) -> dict | None:
    """One request in, one response out. None for a notification.

    A tool failure is always a *result* carrying ``isError``, never a
    JSON-RPC error: the distinction is what lets a client show the reason to
    the user instead of reporting that the server is broken. Only a malformed
    or unknown request is a protocol error.
    """
    # A batch array is legal JSON-RPC 2.0 and is explicitly out of scope for
    # MCP's stdio transport. Before this check, a batch reached ``.get`` on a
    # list, raised, and took the serve loop down with it -- so one stray batch
    # from one client ended the session for every later request.
    if not isinstance(message, dict):
        return _error(None, -32600, (
            "invalid request: expected a single JSON-RPC object per line. "
            "Batch arrays are not supported over MCP stdio."
        ))

    method = message.get("method")
    mid = message.get("id")
    params = message.get("params")
    if not isinstance(params, dict):
        params = {}

    # A notification has no id and takes no response, including
    # notifications/initialized and notifications/cancelled. Cancellation is
    # accepted and ignored on purpose: every tool here is a short synchronous
    # read, so there is no in-flight work to stop, and the spec allows a
    # receiver to complete a request it could not cancel.
    if mid is None:
        return None

    if method == "initialize":
        return _result(mid, {
            "protocolVersion": _negotiated(params.get("protocolVersion")),
            "capabilities": {"tools": {"listChanged": False}},
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

    # This server offers no resources and no prompts, and says so by answering
    # with nothing rather than with -32601. Several clients call all three
    # lists at startup regardless of advertised capabilities, and a method-not-
    # found there shows the user an error about a server that is working fine.
    if method in ("resources/list", "resources/templates/list"):
        return _result(mid, {"resources": [], "resourceTemplates": []})
    if method == "prompts/list":
        return _result(mid, {"prompts": []})

    if method == "tools/call":
        name = params.get("name")
        handler = _HANDLERS.get(name) if isinstance(name, str) else None
        if handler is None:
            return _error(mid, -32602, f"unknown tool: {name}")
        arguments = params.get("arguments")
        if not isinstance(arguments, dict):
            arguments = {}
        try:
            # Nothing the engine logs may reach the protocol channel.
            with quarantine_stdout():
                text = handler(arguments)
            return _result(mid, {
                "content": [{"type": "text", "text": text}],
                "isError": False,
            })
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
    from auditor._version import __version__
    return __version__


def _mute_stdout_fd() -> None:
    """Point fd 1 at the null device, so interpreter exit cannot re-raise.

    Once the client has gone, CPython's shutdown flush of ``sys.stdout`` would
    raise BrokenPipeError again and print a scary traceback over a perfectly
    ordinary disconnection.
    """
    with contextlib.suppress(Exception):
        null = os.open(os.devnull, os.O_WRONLY)
        os.dup2(null, 1)
        os.close(null)


def serve(stdin=None, stdout=None) -> None:
    """Read requests until the stream closes. Writes nothing but JSON.

    Exits cleanly on EOF (the client closed its end) and on BrokenPipeError
    (the client went away mid-write), which are both normal shutdowns, not
    faults.
    """
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    try:
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
                    mid = message.get("id") if isinstance(message, dict) else None
                    response = _error(mid, -32603, "internal error")
            if response is not None:
                stdout.write(json.dumps(response) + "\n")
                stdout.flush()
    except (BrokenPipeError, KeyboardInterrupt):
        if stdout is sys.stdout:
            _mute_stdout_fd()
        return
    with contextlib.suppress(Exception):
        stdout.flush()
