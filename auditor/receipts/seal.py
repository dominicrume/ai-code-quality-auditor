"""The seal, and why it is the only honest paywall for this product.

The check is MIT and public. Anybody can read the code, run it, fork it, and
compute a finding for nothing, forever, and they should: the free reading is the
distribution that makes the paid thing credible, and hiding it would destroy the
asset being sold.

So there is nothing to meter in the computation, and any counter placed in a
client the customer controls is a limit written in a prompt: a suggestion they
can talk themselves out of. Metering by counting calls on somebody else's
machine does not work and pretending otherwise is worse than not charging.

What a customer cannot do, by construction rather than by permission, is produce
a finding signed by a key they do not hold. That is the whole business:

    read   local, MIT, free, unlimited, and honestly labelled `unsealed`
    seal   one call to the holder of the private key, metered, and the only
           form of the finding that another party has reason to accept

An unsealed receipt is not crippled. It is complete, verifiable against its own
content, and useful internally. It simply does not carry anybody's name, which
is precisely what a regulator, an auditor or a counterparty came for. The
customer is never blocked from the work, only from the signature, and the
signature is the thing they are buying.

Ed25519 is used because a verifier needs 32 bytes of public key and no account
with anyone. `auditor verify` checks a sealed receipt offline, against a public
key, years later, with the signer gone.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from pathlib import Path

from auditor.receipts import bundle

ALGORITHM = "ed25519"


class SealingUnavailable(RuntimeError):
    """Raised when the cryptography extra is not installed."""


def _primitives():
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey, Ed25519PublicKey,
        )
        from cryptography.exceptions import InvalidSignature
    except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
        raise SealingUnavailable(
            "Sealing and verifying need the seal extra: "
            "pip install 'ai-code-quality-auditor[seal]'. Reading and "
            "building an unsealed receipt do not."
        ) from exc
    return serialization, Ed25519PrivateKey, Ed25519PublicKey, InvalidSignature


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"))


def generate_keypair() -> tuple[str, str]:
    """A private and public key, base64, raw 32 bytes each.

    The private half never belongs in the repository, in a receipt, or in a
    chat message. Put it in the sealing service's environment and nowhere else.
    """
    serialization, Ed25519PrivateKey, _, _ = _primitives()
    private = Ed25519PrivateKey.generate()
    raw_private = private.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    raw_public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return _b64(raw_private), _b64(raw_public)


def _signed_statement(content_digest: str, sealed_at: str, key_id: str) -> bytes:
    """The bytes a signature is taken over.

    The key inside the statement stays spelled `finding_digest` even for a
    merged envelope whose own field is `content_digest`. It is part of the
    signed blob, and renaming it would invalidate every signature already
    issued for the sake of tidiness.
    """
    """Exactly the bytes a signature covers.

    The finding digest, the moment, and which key. Binding the time means a
    seal cannot be replayed onto a later claim; keying the billing on the
    finding digest alone means re-sealing identical work is not a new outcome.
    """
    return bundle.canonical({
        "alg": ALGORITHM,
        "finding_digest": content_digest,
        "sealed_at": sealed_at,
        "key_id": key_id,
    })


def key_id(public_key_b64: str) -> str:
    import hashlib
    return "sha256:" + hashlib.sha256(_unb64(public_key_b64)).hexdigest()[:16]


def seal(finding: dict, private_key_b64: str, public_key_b64: str,
         *, at: datetime | None = None, resealing: bool = False) -> dict:
    """Return the finding with a seal attached. Refuses a tampered finding.

    Sealing an already sealed finding needs `resealing=True`, because the seal
    block is a single slot: a second seal silently discards the first signer's
    name, which is exactly the move someone would make to pass their own key
    off as the one a reader trusts.
    """
    serialization, Ed25519PrivateKey, _, _ = _primitives()
    if finding.get("seal") and not resealing:
        raise ValueError(
            "this finding is already sealed by "
            f"{finding['seal'].get('key_id')}; pass resealing=True to replace "
            "that signature")
    if not bundle.intact(finding):
        raise ValueError(
            f"{bundle.digest_field(finding)} does not match the receipt; "
            "refusing to seal content that has been altered since it was "
            "computed"
        )
    kid = key_id(public_key_b64)
    sealed_at = (at or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    private = Ed25519PrivateKey.from_private_bytes(_unb64(private_key_b64))
    # Whichever field names this receipt's content. The signature is over the
    # digest, so signing the wrong field would attest to nothing.
    signature = private.sign(
        _signed_statement(finding[bundle.digest_field(finding)], sealed_at, kid))
    out = dict(finding)
    out["seal"] = {
        "algorithm": ALGORITHM,
        "key_id": kid,
        "public_key": public_key_b64,
        "sealed_at": sealed_at,
        "signature": _b64(signature),
    }
    return out


def verify(finding: dict, public_key_b64: str | None = None) -> dict:
    """Check a receipt. Offline, against a public key, by anyone.

    Returns a report rather than raising, because "this does not verify" is an
    answer the caller needs in full.
    """
    report = {
        "state": bundle.state(finding),
        "content_intact": bundle.intact(finding),
        "signature_valid": None,
        "key_id": None,
        "sealed_at": None,
        "reasons": [],
    }
    if not report["content_intact"]:
        # The signature covers the finding digest, so it can still check out
        # over a digest that no longer describes the body. Reporting that as a
        # valid signature invites a reader who checks one field to be fooled by
        # a receipt whose verdict was edited after sealing.
        report["signature_valid"] = False
        report["reasons"].append(
            "the finding has been altered since it was computed: its digest "
            "does not match its content, so its signature attests to something "
            "other than what this receipt now says")
        return report

    seal_block = finding.get("seal")
    if not seal_block:
        report["reasons"].append(
            "unsealed: this is a reading, complete and self-consistent, but "
            "nobody has put their name on it")
        return report

    report["key_id"] = seal_block.get("key_id")
    report["sealed_at"] = seal_block.get("sealed_at")

    missing = [f for f in ("algorithm", "key_id", "sealed_at", "signature")
               if not seal_block.get(f)]
    if missing:
        report["signature_valid"] = False
        report["reasons"].append(
            f"the seal block is incomplete: missing {', '.join(missing)}")
        return report

    key = public_key_b64 or seal_block.get("public_key")
    if not key:
        report["signature_valid"] = False
        report["reasons"].append("no public key to check the signature against")
        return report
    if public_key_b64 and seal_block.get("public_key") and \
            public_key_b64 != seal_block["public_key"]:
        report["signature_valid"] = False
        report["reasons"].append(
            "the receipt carries a different public key from the one supplied; "
            "it was not sealed by the key you trust")
        return report
    if seal_block.get("algorithm") != ALGORITHM:
        report["signature_valid"] = False
        report["reasons"].append(
            f"unsupported algorithm: {seal_block.get('algorithm')!r}")
        return report

    # key_id is what a reader recognises; the public key is what the signature
    # is checked against. An attacker who signs with their own key and copies
    # the trusted key's key_id gets a valid signature under a familiar name,
    # so the two must be proved to be the same key.
    try:
        derived = key_id(key)
    except Exception as exc:
        report["signature_valid"] = False
        report["reasons"].append(f"the public key is not readable: {exc}")
        return report
    if seal_block.get("key_id") != derived:
        report["signature_valid"] = False
        report["reasons"].append(
            f"the seal names key {seal_block.get('key_id')} but its public key "
            f"is {derived}: the key_id does not identify the key that signed it")
        return report

    try:
        _, _, Ed25519PublicKey, InvalidSignature = _primitives()
    except SealingUnavailable as exc:
        # "cannot check" is not "does not verify". None keeps the exit code
        # honest, because only an explicit False means the seal failed.
        report["signature_valid"] = None
        report["reasons"].append(str(exc))
        return report
    try:
        Ed25519PublicKey.from_public_bytes(_unb64(key)).verify(
            _unb64(seal_block["signature"]),
            _signed_statement(finding.get(bundle.digest_field(finding), ""),
                              seal_block.get("sealed_at", ""),
                              seal_block.get("key_id", "")),
        )
        report["signature_valid"] = True
    except InvalidSignature:
        report["signature_valid"] = False
        report["reasons"].append("the signature does not match this finding")
    except Exception as exc:
        report["signature_valid"] = False
        report["reasons"].append(f"could not check the signature: {exc}")

    if report["signature_valid"] and report["content_intact"]:
        report["reasons"].append(
            f"sealed by {report['key_id']} on {report['sealed_at']} and "
            f"unchanged since")
    return report
