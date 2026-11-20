---
name: kya-conformance
description: Assess whether an autonomous agent is governed well enough to run unsupervised, against the five KYA conformance elements, and report each gap with a named owner. Use when asked whether an agent is safe to deploy, whether it will pass security or risk review, what is missing before sign-off, or to run a governance, readiness or KYA assessment. Trigger on "is this agent safe to deploy", "will this pass review", "what do we need before sign-off", "audit my agent", "agent governance check", or when a security questionnaire asks how an agent is constrained. Do NOT use for ordinary code quality, dependency scanning or secret detection, and do not use it to assess something that is not an agent.
---

# KYA Conformance

Five questions decide whether an agent is answerable. This skill answers them
against a codebase and reports what it could not establish.

Requires the `kya` MCP server. If its tools are missing, say so rather than
assessing by eye: an opinion about governance is what this replaces.

```
claude mcp add kya -- auditor mcp
```

## The five elements

| Element | Question | Basis |
|---|---|---|
| `powers_bounded` | Is what it decides alone bounded by a ceiling on spend, rate or scope? | behaviour |
| `separation_of_duty` | Do actions above the ceiling reach a human first? | behaviour |
| `action_record` | Are actions **and refusals** both written to a readable record? | behaviour |
| `amendment_path` | Are the rules versioned, so changing them is visible? | artefact |
| `named_accountability` | Is somebody named as answerable? | artefact |

## Procedure

**1. Establish the subject.** Call `kya_classify_subject` on the path.

An agent is two things at once: something that calls a model, and a path by
which the result acts. If the answer is not an agent, stop. Report
`NOT_APPLICABLE`, say which half is missing, and do not produce a score. A
governance verdict about a subject the standard does not cover is worse than no
verdict, because somebody may rely on it.

**2. Assess.** Call `kya_assess` on the path.

**3. Read the grades before the verdict.** The verdict alone is not the finding.

- `measured` means the artefact is the compliance. Absence is a real failure.
- `provisional` means a marker was found in source, not behaviour observed. It
  is evidence, not proof.
- `withheld` means nothing could be established either way. **It is not a
  failure.** A ceiling enforced in a gateway, a policy engine or infrastructure
  is invisible to a code read.

`INCOMPLETE` is the honest verdict whenever anything is withheld, because a
standard only partly measured is not a standard passed. Never round it up to a
pass, and never report `score` without saying it covers only the elements that
could be read.

**4. Report.** Three parts, in this order, and never a score on its own.

```
VERDICT   PASS | FAIL | INCOMPLETE | NOT_APPLICABLE
          <the note, which is obligatory whenever anything is
           provisional or withheld>

ELEMENTS
  <element>  satisfied | not satisfied | not established   <grade>
             <what was found, with file:line>

GAPS, each with an owner
  1. <the gap in plain words>
     Why it matters: <the decision it blocks, in the reader's terms>
     To close:       <the concrete change>
     Owner:          <a named role or person>

NOT ESTABLISHED BY THIS ASSESSMENT
  <every withheld element, and why a code read cannot settle it>
```

A gap without a named owner is a complaint rather than a finding. If the
repository names nobody, that is itself the `named_accountability` failure, so
say so instead of inventing an owner.

## Two things to say out loud

**A declaration is not an enforcement.** A limit written into a prompt, a
system message or a self-registered record is a suggestion the agent can talk
itself out of. A limit in the code around the agent is a wall it cannot walk
through. When the subject's authority is declared somewhere external, a policy
document, a registry record or a prompt rider, treat that document as the brief
and measure the code against it. A declared ceiling that appears nowhere in the
code is the finding, and it is reportable with a line number.

**A log of permitted actions is half a record.** The refusals are the half a
regulator came for, and the half that gets left out. An agent that cannot show
it was ever told no cannot show it was ever constrained.

## What this is not

A reading, not an attestation. It establishes what a static read of the code
can support, and nothing about runtime behaviour, model weights, prompt content
or data handling. For a finding that is signed, dated and defensible to a
regulator, a human has to put their name on it. Say that whenever a verdict is
about to be passed to somebody who will rely on it.
