# The Agent Constitution receipt envelope, version 2

**Status: normative in this repository, and a proposal to the other.** Defined,
implemented and tested here in `auditor/receipts/envelope.py`. It is not yet
what `auditor receipt` emits, for a reason given under *Sequencing* below.

Media type: `application/agent-constitution-receipt+json`

## Why there is one envelope

Two hash-chained receipt formats existed, by one author, for the two halves of
one question:

- **Was the agent built with rules?** Read the artefact. Produces a verdict
  with a grade per element. Signed, Ed25519, with a key id bound to its own
  public key.
- **What did the rules actually stop?** Read the record. Produces a chain of
  refusals, each committing to the one before. Unsigned, so a chain forged from
  scratch verifies everywhere.

Those are not competitors. They are design time and run time, and each closed a
hole the other had written down in public. The static read cannot establish
three of the five elements and says so, every time, by construction. A verified
refusal chain is exactly what establishes one of them. Meanwhile the chain's own
open question asked for a signature profile, which the static side had already
built and tested.

Two formats for one chain of evidence is the thing that reads as indecision. So:
**one envelope, two payload types, and the chain, the digest and the seal
defined once.**

## Shape

    {
      "envelope_version": 2,
      "standard":    { "name": "agent-constitution", "version": 1,
                       "digest": "sha256:<64 hex>" },
      "receipt_type": "conformance" | "refusal",
      "method":       "static_conformance" | "behavioural_evidence",
      "instrument":  { "name": "...", "version": "..." },
      "subject":     { ... },
      "payload":     { ... },
      "chain":       { "n": <integer >= 0>, "previous": "sha256:..." | null },
      "disclosed_defects": [ ... ],
      "content_digest": "sha256:<64 hex>",
      "seal": null | { "alg": "ed25519", "key_id": "...", "signature": "..." }
    }

`receipt_type` selects the payload. `method` says which method of the standard
produced it, and a verifier uses it with the standard's `established_by` ceiling
to decide what grade the evidence may reach. Nothing else in the document may
raise that ceiling.

## The three rules that make it worth anything

### 1. Assurance is derived, and there is no field for it

A verifier reports one of `self_attested`, `sealed` or `anchored`, and computes
it from what the reader brought, never from the document.

The other format got this right in principle and still had the level as a
concept the document discussed. This envelope goes further: **there is no
assurance field at all.** A producer cannot assert a level it does not have if
there is nowhere to write one. `seal`, `instrument`, `standard` and
`disclosed_defects` are all written by the producer and none of them raises the
level.

| Level | Reached when |
|---|---|
| `self_attested` | always, by default. The content digest matches the content |
| `sealed` | a signature verifies against a public key **the reader supplied**, and the `key_id` identifies that key |
| `anchored` | the reader also found this chain head in a record outside the producer's control, and says so |

A reader who did not go and look may not raise the level. `ledger_ref` in a
refusal payload is an address, not evidence: either the record is there with
that rule at that time, or it is not.

### 2. Canonical form is ASCII, by escaping and not by prohibition

Sorted keys, no whitespace, and **every non-ASCII character escaped as
`\uXXXX`**.

This exists because of a real interoperability bug: Python's JSON writer escapes
non-ASCII by default and JavaScript's does not, so the same receipt seals
differently in two languages and a cross-language verifier disagrees with itself.
The other format fixed this by forbidding non-ASCII in a sealed body, at the
stated cost that *a refusal reason in a non-Latin script cannot be sealed as
written.*

Escaping is strictly better. The bytes are identical in every language and the
text survives. A refusal reason in Arabic, Chinese or Yoruba seals, verifies and
reads back exactly as written. **This closes a limitation the other format
declares about itself.**

Amounts are strings. A float does not round-trip identically across languages
and an amount that changes in transit is not evidence.

### 3. The digest covers the content and not the moment

`content_digest` is taken over the whole envelope except `content_digest` and
`seal`. The same work therefore has the same name forever, which gives
idempotent billing for nothing: a customer who runs a check a hundred times has
produced one finding.

A refusal's own time is material, so it lives **inside** `payload` and is
covered. Only the envelope's issuing moment is excluded, and the envelope has no
field for it.

## The two payloads

### `conformance`

Produced by a static read. Carries, per element: the id, the `basis`, the
requirement, `satisfied` as true, false or null, the derived `grade`, and the
evidence string. Plus the verdict, the coverage, the score over readable
elements only, the files that could not be parsed, and the subject
classification.

`subject` is a digest over `(path, content hash)` pairs with a tree digest.
Enough to prove later which exact bytes were read, and not enough to
reconstruct a line of them.

### `refusal`

Produced by an enforcement point, as it refuses.

    "payload": {
      "attempt":    { "what": "...", "amount": "40.00", "currency": "GBP",
                      "payee": "..." },
      "rule":       "the rule that decided",
      "outcome":    "refused",
      "decided_by": "the enforcement point, not the agent",
      "at":         "<ledger time, RFC 3339>",
      "ledger_ref": "<optional address of the enforcement record>"
    }

`subject` for a refusal identifies the mandate, not a codebase.

## What this does not prove

Written here rather than only in prose, because a reader who has only this file
is entitled to the limits.

- **An unsealed chain forged from scratch verifies.** The chain proves nobody
  edited or reordered it. It does not prove whose it is. That is what `sealed`
  is for, and `self_attested` is the honest default.
- **Completeness is not established.** An agent that never attempts anything
  leaves nothing. A refusal decided on a path that does not write a record
  leaves nothing. Neither method claims otherwise.
- **Truncating the tail is detectable only against an externally held count or
  head.** `chain.n` makes a gap visible to a reader who knows what the count
  should be, and to nobody else.
- **`agent_ref` and `ledger_ref` establish nothing.** They are pointers so an
  identity system or a ledger can be reached from a receipt, without this
  format competing with either.
- **No signature profile is mandatory.** A reader who needs one requires
  `sealed` and refuses anything below it.

## Sequencing

This envelope is implemented and tested here. `auditor receipt` still emits
`receipt_version: 1`, and that is deliberate.

Changing canonical form changes every digest. Digests are what the metering
treats as the billable unit, so flipping the emitter unilaterally would charge a
customer twice for one unchanged codebase, the day after a release. It would
also produce a merged format that only one of the two producers can write, which
is a rename rather than a merge.

The default flips in one release, when the refusal producer emits this envelope
too. Until then `verify` reads both, v1 receipts keep verifying, and the version
two path is exercised by its own tests and vectors. A merge announced before
both sides can write it would be the kind of claim this whole method exists to
refuse.
