# Privacy: what this tool records, and what can ever leave your machine

Short version: auditing records a line on your own computer, and nothing is sent anywhere unless
you personally run `auditor share` with a destination and confirm it.

This file is the long version, because a tool that audits other people's code has no business
being vague about its own behaviour.

## 1. What a scan records, and where

`auditor scan` appends one line to `~/.auditor/history.jsonl`. One line per scan. It contains:

| Field | Example | Why |
|---|---|---|
| `at` | `2026-09-17T07:01:22+00:00` | when you ran it |
| `project` | `4f1c9a2b77e0` | a salted id for the folder, see §2 |
| `path` | `/Users/you/work/client-x` | so *you* can read your own history. Never shared |
| `files`, `loc`, `python_files`, `readable_files` | `49`, `8340` | size, and how much was analysable |
| `spec_supplied` | `true` | whether a brief was given, never which one |
| `languages` | `["python", "typescript"]` | what the analysers could read |
| `worst_band` | `warn` | the worst reading in that scan |
| `metrics` | `{"security_density": {"value": 5.29, ...}}` | the numbers themselves |
| `auditor_version` | `0.5.1` | which version produced them |

It never contains a file name, a function name, a finding, or a line of your code.

Move the file with `AUDITOR_HOME=/somewhere`. Switch recording off for good with
`AUDITOR_NO_HISTORY=1`, or for one run with `auditor scan . --no-history`.

## 2. Why the folder is a hash

`project` is SHA-256 of the folder's absolute path, salted with a random value created once on
your machine, kept in `~/.auditor/install.json`, and never transmitted. The id is therefore
stable on your machine, which is what makes trends possible, and meaningless anywhere else.
Deleting the identity file, which `auditor forget --all` does, changes the id permanently.

The full path is also stored, in the clear, because your own history is unreadable without it.
It is excluded from every share by an allowlist, and a test asserts it.

## 3. Reading and deleting

```bash
auditor history                      # the last 20 scans
auditor history --project client-x   # one folder, with the change between scans
auditor history --where              # the file's path, to open or delete by hand
auditor forget --project client-x    # delete one folder's rows
auditor forget --all                 # delete everything, including the random ids
```

It is a plain text file of JSON lines. `cat`, `grep` and `rm` work on it. Nothing is hidden from
you, and nothing needs our permission to remove.

## 4. Sharing, if you choose to

`auditor share` exists so that aggregate readings can be contributed to research. It is off. It
does nothing unless you run it, and even then:

- it **prints the entire payload first**, every time;
- it sends only with `--to https://<endpoint>` **and** `--yes`;
- it refuses any destination that is not `https://`;
- it refuses to send at all if anything identifying survived into the payload.

What may be shared is decided by an allowlist in `auditor/core/share.py`, not by a list of things
to strip. A field added to the local history in future is **not** shared until someone adds it to
that list deliberately. A test adds a `client_name` field to a row and asserts it stays home.

| Shared | Never shared |
|---|---|
| metric values, units, bands, coverage | the folder path |
| file, line and language counts | the folder name |
| whether a specification was supplied | the specification's name |
| tool version, OS family, Python version | file names, findings, any code |
| a random installation id | the salted folder id |

Inside one payload, projects are numbered `p1`, `p2`, renumbered on every send, so a receiver can
tell two projects apart within a submission without being able to identify either.

## 5. What we can and cannot see

To be explicit, because it has been asked: the maintainers of this tool have **no** record of
your audits. None was ever collected. For every install before 0.5.1 there is no history at all,
and from 0.5.1 there is a history that lives on your machine and comes to us only if you send it.

The only figure the project has about its own use is the public PyPI download count, which says
how often the package was installed and nothing whatever about what it found.

## 6. Where to check this yourself

- `auditor/core/history.py` — the local store. It imports no network library.
- `auditor/core/share.py` — the only module that can open a socket. Not imported by `scan`,
  `watch` or `live`.
- `tests/test_history_and_share.py` — the assertions behind every claim on this page.
- `scripts/final_launch_check.py` — refuses a release if any other module gains a network call.
