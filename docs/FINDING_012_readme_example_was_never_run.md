# FINDING_012 — the README's headline example was never run

**Status:** closed for the published claim, open for the two defects it exposed
**Found:** 26 November 2026, during a claim audit of the PyPI project page
**Versions affected:** every release up to and including 0.6.11
**Owner:** Orume Dominic Uririe

## What was claimed

The first code block in `README.md`, reproduced verbatim on the PyPI project page
and therefore the first thing any prospective user read, showed this:

```
Specification fidelity  2 of 4 delivered

✓  Submit a new claim with a policy number    api.py:4   route POST /claims
✓  Look up a claim by reference               api.py:8   route GET /claims/<ref>
✗  Attach supporting documents to a claim                not found
!  Notify the assessor when a claim is        api.py:12  function notify_assessor
   submitted                                             exists, nothing exposes it
~  /admin/purge                               api.py:15  not asked for
```

It was written by hand. Nobody ran it.

## What the tool actually does

A minimal Flask service was built to match the example exactly — four routes, one
unexposed `notify_assessor`, an unrequested `/admin/purge`, and the four
requirements as written — and scanned with 0.6.12:

```
Specification fidelity  2 of 4 delivered

✓  Submit a new claim with a policy number   api.py:6   function submit_claim
✗  Look up a claim by reference                         not found
✗  Attach supporting documents to a claim               not found
✓  Notify the assessor when a claim is       api.py:13  function notify_assessor
   submitted
```

Four divergences, in descending order of seriousness:

1. **A requirement that is implemented reads `✗ not found`.** "Look up a claim by
   reference" is slugged `look.up.claim`. `defs.matches` tests the head word.
   Nothing in any codebase declares `look`. `get_claim`, decorated
   `GET /claims/<ref>`, is right there. This is a false red against working code,
   which is the failure class FINDING_011 named and did not finish closing.
2. **Flask routes are not routes.** `_PY_PATTERNS` matches
   `@\w+\.(get|post|put|delete|patch)\(` — the FastAPI and Typer decorator family.
   Flask's `@app.route("/claims", methods=["POST"])` does not match it, so the
   endpoint falls through to the `function` pattern. The published evidence string
   `route POST /claims` is not reachable from the code the example showed.
3. **The unexposed function read as delivered, not unreachable.** The example
   promised `!` for `notify_assessor`; the run returned `✓`.
4. **The unrequested route produced no drift row.** The example promised
   `~ /admin/purge`; scope drift read `0.00 OK`.

## Why it matters more than a stale snippet

The three verdicts are the product. The claim that distinguishes this tool from a
linter is that it knows what you asked for and cites a file and a line for every
answer. Publishing a hand-written illustration of that claim, on the page where
people decide whether to install it, is the same defect as a scan reporting a
specification it never read (FINDING_011) — a reading that cannot fail is not a
reading, and an example that was never executed is not evidence.

It also means the figure "2 of 4 delivered" in the example was correct by
coincidence. Two of the four verdicts behind it were wrong.

## What changed

- Both README examples are now output captured from real runs against fixtures,
  and the README says so in the text beside them.
- The Flask route gap and the verb-head-word gap are stated in a new "What it will
  not tell you" section rather than left to be discovered.
- No analyser behaviour was changed. Correcting a published claim and changing what
  the instrument measures are separate acts, and doing both in one pass is how a
  metric gets quietly fitted to the story being told about it.

## What is still open

Defect 1 (verb head words) and defect 2 (Flask routes) are real and unfixed.
Both change what `fidelity` reports, so both need their own records, their own
tests, and a pass over the published figures that fidelity feeds before anything
is changed. Defects 3 and 4 are not yet established as defects: the example that
provoked them was fiction, and the behaviour may be correct. They need a fixture
built to test the question before anyone calls them bugs.

## The limit of this record

This audit checked the README against the tool. It did not check the dissertation,
the papers, or the dashboard against the tool. Those are separate claim surfaces
and none of them has been audited at this level.
