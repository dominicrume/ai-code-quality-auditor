# Quickstart: the KYA check inside your own agent

Sixty seconds, install to first verified check.

## 1. Install

```sh
pip install ai-code-quality-auditor
```

## 2. Register the server

Claude Code, one command:

```sh
claude mcp add kya -- auditor mcp
```

Any other client: copy its file from `install/`. One per client, named after it.
The `//` lines at the top say where it goes, and everything below them is strict
JSON. Delete the `//` lines if your client rejects comments.

## 3. Check it connected

```sh
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"t","version":"1"}}}' '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' | auditor mcp
```

Three tool names come back: `kya_assess`, `kya_classify_subject`, `kya_standard`.

## 4. Ask your agent

> Run a KYA conformance check on this repository.

An agent comes back graded, not scored out of ten:

```
"verdict": "INCOMPLETE",
"subject": "agent",
"note": "Incomplete: 1 of 5 elements could not be established by reading the
         code (action_record). A limit enforced in infrastructure is invisible
         here, so this is not a finding that they are absent.",
"score_over_readable": 0.5,
"grades": { "measured": 2, "provisional": 2, "withheld": 1 }
```

`measured`: the artefact is the compliance. `provisional`: a marker in source,
not behaviour observed. `withheld`: not established either way, and not a failure.

## 5. The part that matters: it refuses

Point it at something that is not an agent. Real output, from this repository:

```
"verdict": "NOT_APPLICABLE",
"subject": "not_an_agent",
"score": null,
"note": "Subject acts, but nothing was found calling a model. This is ordinary
         software, and the standard does not apply to it.",
"disclosure": "No score was produced. A standard about autonomous agents has
               nothing to say about this subject."
```

On a directory it could not read, `docs/`, it says `"subject": "unreadable"` and
`"coverage": 0.0`, and again no score.

A verdict about a subject the standard does not cover is worse than no verdict,
because somebody may rely on it.

## If the server will not start

`auditor` is not on the client's PATH. Every file in `install/` carries a
commented absolute-path alternative. Find yours with `which auditor`.
