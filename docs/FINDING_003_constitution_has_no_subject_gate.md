# FINDING_003 — the constitution checker scores repositories that contain no agent

**Status:** fixed, 9 November 2026, in the same day it was recorded.
**Found:** 9 November 2026, by self-scan, before any external use.
**Module:** `auditor/governance/constitution.py`, `specs/kya_constitution_v1.yaml`

## What happens

Pointed at this repository — an experimental instrument with no agent in it,
no spend ceiling, no approval gate and no runtime at all — the KYA constitution
checker returns:

    PASS   score=1.0   measured=2  provisional=3  withheld=0

Every element reported satisfied. The project has none of them.

## Why

Two separate causes, and the second is the serious one.

**A marker vocabulary finds itself.** `separation_of_duty` passed on the string
`require_approval` appearing in `constitution.py` — inside the checker's own
list of markers it searches for. `named_accountability` passed on the word
`owner` in the same file's evidence text. A text match cannot distinguish a
file that *implements* governance from one that *discusses* it, and the file
that discusses it hardest is the checker.

**Nothing asks whether the subject is an agent.** The module will score a
spreadsheet, a static site or a dissertation repository against a standard for
autonomous agents and return a verdict with a number in it. There is no gate on
the subject at all.

## This is the third time, and that is the finding

- **FINDING_001** — metrics reported about code the instrument never read.
- **FINDING_002** — a fidelity verdict against a brief nobody supplied.
- **FINDING_003** — a governance verdict against a subject that is not an agent.

One shape: *the instrument answered a question that did not apply, instead of
declining to answer.* FINDING_002 was fixed by making a reading carry what it
rests on. That machinery is reused here and it is not enough, because grading
the evidence for an element says nothing about whether the element was ever
applicable. A perfectly graded reading of the wrong subject is still wrong.

## What a fix has to do

Not tune the markers. The gate belongs before the elements, by analogy with the
`has_surface` reachability gate in the fidelity analyser:

1. **Establish the subject.** An agent has an entry point that takes an
   instruction and acts: a tool-call loop, a planner, an LLM client with side
   effects. Absent all of it, the standard does not apply and the only
   honest verdict is `NOT_APPLICABLE` — not `PASS`, and not `FAIL`.
2. **Exclude the instrument from its own scan**, and more generally decline to
   credit a marker found only in a file whose role is to describe the standard.
3. **Separate discussing from doing.** A marker inside a string literal, a
   comment or a collection of search terms is weaker evidence than one in an
   executed comparison. Until that distinction exists, PROVISIONAL is carrying
   more weight than it can bear.

## Until then

The five elements, their checkers and the grading are sound and tested
(20 tests). What is not sound is the aggregate verdict on an arbitrary
repository. No published page should quote a KYA score produced by this module
until the subject gate exists.


---

## Fix, 9 November 2026

Both causes fell to one change: **match identifiers, not text.**

`auditor/governance/subject.py` parses Python and reports only names that are
used, so a marker inside a string literal is a mention rather than a use. The
checker can no longer see its own vocabulary, because `require_approval` lives
in this codebase as a string in a tuple. `separation_of_duty` on this
repository went from a false pass to correctly withheld.

A subject gate now runs before any element is read. An agent, for a standard
about autonomy, is two things at once: something that calls a model, and some
path by which the result acts. A model call with no action path is a chatbot; an
action path with no model is ordinary software. Neither is failed. Both are
`NOT_APPLICABLE`, with no score, no element results, and a sentence saying why.

This repository now returns `NOT_APPLICABLE`, pinned by
`test_this_instrument_is_not_an_agent_and_gets_no_kya_score`.

### Two defects inside the fix, both found by self-scan before shipping

The marker lists were twice too loose, and each time the gate over-admitted,
which is the worse direction: an over-admitting gate hands a verdict to a
subject the standard does not cover.

1. The first model list held `chat`, `prompt`, `llm` and `messages`. Those are
   ordinary vocabulary in software that has never called a model, and the
   instrument was classified as an agent.
2. The second matched provider names against any identifier, so
   `anthropic_api_key` in a config dataclass was enough. **Holding a
   provider's key is not calling a provider.** Provider names are now matched
   against imports only, by exact part rather than substring.

Both are pinned by tests. The general lesson, which is the same one
FINDING_002 taught: when a fix is a special case of the real problem it is not
a fix, and a marker list is nearly always a special case.

### What is still not established

The gate reads Python. A subject whose loop is in TypeScript is reported
`UNREADABLE`, never as having no agent, and `coverage` states how much was
parsed. Silence remains not evidence of absence.
