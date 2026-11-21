# Sealing service

The one call a customer cannot make for themselves.

Everything else runs on their machine, free and MIT. `auditor receipt` produces
a complete, self-consistent finding and carries nobody's name. This service puts
a name on it, using a key the customer does not hold, which is the whole
business and the only honest paywall for a tool whose source is public.

## What it never receives

Source code. A finding carries a digest per file, not the contents, so a
customer can prove later which exact bytes were assessed and this service can
prove it never held them. That is the answer to the question every enterprise
security review actually asks.

## Endpoints

| | |
|---|---|
| `POST /mcp` | MCP over Streamable HTTP. One JSON-RPC message, one JSON reply. Requires `Authorization: Bearer <key>` |
| `GET /healthz` | Liveness, and whether sealing is configured |
| `GET /.well-known/kya-public-key` | The public half, served openly, so verifying needs no account |

Tools: `seal_finding`, `sealing_quota`, `sealing_public_key`.

## Run it locally

```bash
cp .env.example .env            # then fill in the keys
pip install -r requirements.txt
set -a && . ./.env && set +a
python app.py
```

## Deploy

```bash
fly secrets set AUDITOR_SEAL_PRIVATE_KEY=... AUDITOR_SEAL_PUBLIC_KEY=...
fly deploy
```

## What is billable

| Outcome | Charged |
|---|---|
| A reading, sealed or not | No |
| A refusal, `NOT_APPLICABLE` | No |
| A sealed finding, within the free quota | No |
| A sealed finding beyond it | Once, per distinct finding |

Re-sealing identical work is one outcome forever, because the finding digest
covers content and not time. A customer cannot be surprised by a bill for a
loop in their CI.

Past the free quota with no billing provider configured, the service refuses to
seal rather than sealing for nothing. A seal implies somebody stands behind it,
and nobody should stand behind one they have not agreed to.
