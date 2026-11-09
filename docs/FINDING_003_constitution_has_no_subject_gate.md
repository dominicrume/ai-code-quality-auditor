# FINDING_003 — the constitution checker scores repositories that contain no agent

**Status:** open. The module ships with the defect recorded and the verdict
unsafe to quote.
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
