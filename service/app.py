"""The sealing service: the one call a customer cannot make for themselves.

Everything else in this product is MIT and runs on the customer's machine. The
reading is free and unlimited by design, because the adoption is what makes the
signature worth having. This service exists to do the single thing that cannot
be self-built, by construction rather than by permission: put a name on a
finding using a key the customer does not hold.

Shape of the deal, enforced here and nowhere else:

    free      every reading, every refusal, unlimited, forever
    free      the first AUDITOR_FREE_QUOTA sealed findings per organisation
    billable  each sealed finding after that, once per distinct finding

What this service never receives: source code. A finding carries digests of the
files that were read, not their contents, so a customer can prove later which
exact bytes were assessed and this service can prove it never held them. That is
the answer to the only question an enterprise security review really asks.

Transport is MCP over Streamable HTTP: one POST carrying a JSON-RPC message,
one JSON response. No SSE, because nothing here streams and a server that
advertises streaming it does not do is a liability.

Secrets come from the environment and are never logged, echoed or returned:

    AUDITOR_SEAL_PRIVATE_KEY   base64 Ed25519 private key, 32 bytes raw
    AUDITOR_SEAL_PUBLIC_KEY    base64 Ed25519 public key, published openly
    AUDITOR_API_KEYS           org_id:sha256_of_key, comma separated
    AUDITOR_FREE_QUOTA         sealed findings before charging starts
    AUDITOR_LEDGER_PATH        where outcomes are recorded
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys

from flask import Flask, jsonify, request

from auditor.receipts import bundle, meter
from auditor.receipts import seal as seal_mod

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "kya-sealing-service"

# The service owns its own default rather than importing one from the library.
# Deliberate: the library's quota is about a local ledger, and this number is a
# commercial decision that belongs with the thing that charges for it.
DEFAULT_FREE_QUOTA = 25

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Configuration, read once, never echoed
# ---------------------------------------------------------------------------

def _keys() -> dict[str, str]:
    """{sha256_of_api_key: org_id}. The raw key is never stored anywhere.

    A leaked configuration therefore does not leak a usable credential, and a
    customer's key cannot be recovered by anyone holding this deployment.
    """
    out: dict[str, str] = {}
    for pair in (os.environ.get("AUDITOR_API_KEYS") or "").split(","):
        pair = pair.strip()
        if not pair or ":" not in pair:
            continue
        org, digest = pair.split(":", 1)
        out[digest.strip().lower()] = org.strip()
    return out


def _free_quota() -> int:
    try:
        return int(os.environ.get("AUDITOR_FREE_QUOTA", DEFAULT_FREE_QUOTA))
    except ValueError:
        return DEFAULT_FREE_QUOTA


def _ledger() -> meter.Ledger:
    return meter.Ledger(os.environ.get("AUDITOR_LEDGER_PATH", "/data/outcomes.jsonl"))


def _presented_key() -> str | None:
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return request.headers.get("x-api-key") or None


def authenticate() -> tuple[str | None, str | None]:
    """Return (org_id, error). Constant-time comparison, no key in any message."""
    presented = _presented_key()
    if not presented:
        return None, "no API key presented; send Authorization: Bearer <key>"
    digest = hashlib.sha256(presented.encode("utf-8")).hexdigest()
    for known, org in _keys().items():
        if hmac.compare_digest(digest, known):
            return org, None
    return None, "the API key presented is not recognised"


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

def tool_seal_finding(args: dict, org_id: str) -> tuple[dict, bool]:
    """Seal a finding the customer computed locally. The billable outcome."""
    finding = args.get("finding")
    if isinstance(finding, str):
        try:
            finding = json.loads(finding)
        except json.JSONDecodeError as exc:
            return {"error": f"finding is not valid JSON: {exc}"}, True
    if not isinstance(finding, dict):
        return {"error": "finding must be the receipt object or its JSON text"}, True

    if not finding.get("finding_digest"):
        return {"error": "finding carries no finding_digest; produce it with "
                         "auditor receipt"}, True
    if not bundle.intact(finding):
        return {"error": "the finding has been altered since it was computed: "
                         "its digest does not match its content. Nothing is "
                         "sealed and nothing is charged."}, True
    if finding.get("seal"):
        return {"error": "this finding already carries a seal"}, True

    private = os.environ.get("AUDITOR_SEAL_PRIVATE_KEY")
    public = os.environ.get("AUDITOR_SEAL_PUBLIC_KEY")
    if not private or not public:
        return {"error": "the service is not configured to seal"}, True

    ledger = _ledger()
    quota = _free_quota()
    already = ledger.seen(org_id, finding["finding_digest"], billable_only=True)
    if not already and ledger.billable_count(org_id) >= quota:
        # A real deployment checks the billing provider here. Refusing is the
        # correct behaviour: a seal implies somebody stands behind it, and
        # nobody should stand behind one they have not agreed to.
        if os.environ.get("AUDITOR_BILLING_ENABLED", "").lower() not in ("1", "true", "yes"):
            return {"error": f"free quota of {quota} sealed findings used. "
                             f"Readings stay free and unlimited. Add billing to "
                             f"seal further findings.",
                    "quota_used": ledger.billable_count(org_id),
                    "free_quota": quota}, True

    try:
        sealed = seal_mod.seal(finding, private, public)
    except seal_mod.SealingUnavailable as exc:
        return {"error": str(exc)}, True
    except ValueError as exc:
        return {"error": str(exc)}, True

    row = ledger.record(sealed, org_id)
    return {
        "receipt": sealed,
        "billing": {
            "outcome_type": row["outcome_type"],
            "charged": row["charged"],
            "reason": row["reason"],
            "finding_digest": row["finding_digest"],
        },
        "verify_offline": (
            "auditor verify receipt.json --public-key " + public
        ),
    }, False


def tool_quota(args: dict, org_id: str) -> tuple[dict, bool]:
    ledger = _ledger()
    statement = ledger.statement(org_id)
    statement["free_quota"] = _free_quota()
    statement.pop("digests", None)
    return statement, False


def tool_public_key(args: dict, org_id: str) -> tuple[dict, bool]:
    public = os.environ.get("AUDITOR_SEAL_PUBLIC_KEY")
    if not public:
        return {"error": "no signing key is configured"}, True
    return {
        "algorithm": seal_mod.ALGORITHM,
        "public_key": public,
        "key_id": seal_mod.key_id(public),
        "how_to_verify": (
            "Anyone can check a sealed receipt offline, with no account and no "
            "call to this service: pip install 'ai-code-quality-auditor[seal]' "
            "then auditor verify receipt.json --public-key <this key>"
        ),
    }, False


TOOLS = [
    {
        "name": "seal_finding",
        "description": (
            "Seal a conformance finding so it can be relied on by somebody who "
            "was not there. Takes a receipt produced locally by `auditor "
            "receipt` and returns it signed and dated, verifiable offline by "
            "anyone holding the public key. Source code is never sent: a "
            "finding carries digests of the files that were read, not their "
            "contents. Sealing the same finding twice is one outcome."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"finding": {
                "type": ["object", "string"],
                "description": "The receipt object, or its JSON text."}},
            "required": ["finding"],
        },
        "handler": tool_seal_finding,
    },
    {
        "name": "sealing_quota",
        "description": (
            "How many sealed findings this organisation has recorded, how many "
            "were charged, and what remains of the free quota. Readings and "
            "refusals are always free and are not counted against it."
        ),
        "inputSchema": {"type": "object", "properties": {}},
        "handler": tool_quota,
    },
    {
        "name": "sealing_public_key",
        "description": (
            "The public key this service seals with, and how to verify a "
            "receipt offline without calling this service at all."
        ),
        "inputSchema": {"type": "object", "properties": {}},
        "handler": tool_public_key,
    },
]

_HANDLERS = {t["name"]: t["handler"] for t in TOOLS}


def _advertised():
    return [{k: v for k, v in t.items() if k != "handler"} for t in TOOLS]


# ---------------------------------------------------------------------------
# MCP over Streamable HTTP
# ---------------------------------------------------------------------------

def _result(mid, payload):
    return {"jsonrpc": "2.0", "id": mid, "result": payload}


def _error(mid, code, message):
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def dispatch(message: dict, org_id: str):
    method = message.get("method")
    mid = message.get("id")
    params = message.get("params") or {}

    if mid is None:
        return None

    if method == "initialize":
        return _result(mid, {
            "protocolVersion": params.get("protocolVersion") or PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": "1"},
            "instructions": (
                "Sealing for conformance findings. Compute a finding locally "
                "with `auditor receipt`, which is free and unlimited, then seal "
                "it here when somebody else has to rely on it. No source code "
                "is sent or stored."
            ),
        })
    if method == "ping":
        return _result(mid, {})
    if method == "tools/list":
        return _result(mid, {"tools": _advertised()})
    if method in ("resources/list", "prompts/list"):
        return _result(mid, {"resources": []} if method.startswith("resources")
                       else {"prompts": []})
    if method == "tools/call":
        name = params.get("name")
        handler = _HANDLERS.get(name)
        if handler is None:
            return _error(mid, -32602, f"unknown tool: {name}")
        try:
            payload, is_error = handler(params.get("arguments") or {}, org_id)
        except Exception as exc:
            app.logger.exception("tool %s failed", name)
            payload, is_error = {"error": f"{type(exc).__name__}"}, True
        return _result(mid, {
            "content": [{"type": "text",
                         "text": json.dumps(payload, indent=2)}],
            "isError": is_error,
        })
    return _error(mid, -32601, f"method not found: {method}")


@app.post("/mcp")
def mcp_endpoint():
    org_id, error = authenticate()
    if error:
        return jsonify(_error(None, -32001, error)), 401

    message = request.get_json(silent=True)
    if not isinstance(message, dict):
        if isinstance(message, list):
            return jsonify(_error(None, -32600,
                                  "JSON-RPC batches are not supported")), 400
        return jsonify(_error(None, -32700, "parse error")), 400

    response = dispatch(message, org_id)
    if response is None:
        return "", 202
    return jsonify(response), 200


@app.get("/healthz")
def healthz():
    public = os.environ.get("AUDITOR_SEAL_PUBLIC_KEY")
    return jsonify({
        "ok": True,
        "can_seal": bool(os.environ.get("AUDITOR_SEAL_PRIVATE_KEY") and public),
        "key_id": seal_mod.key_id(public) if public else None,
        "organisations_configured": len(_keys()),
    })


@app.get("/.well-known/kya-public-key")
def well_known_key():
    """The public half, served openly, so verification needs no account."""
    public = os.environ.get("AUDITOR_SEAL_PUBLIC_KEY")
    if not public:
        return jsonify({"error": "no signing key configured"}), 404
    return jsonify({"algorithm": seal_mod.ALGORITHM, "public_key": public,
                    "key_id": seal_mod.key_id(public)})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    if not os.environ.get("AUDITOR_SEAL_PRIVATE_KEY"):
        print("AUDITOR_SEAL_PRIVATE_KEY is not set; /mcp will refuse to seal.",
              file=sys.stderr)
    app.run(host="0.0.0.0", port=port)
