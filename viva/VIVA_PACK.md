# Viva pack — 23 October 2026

45 minutes in the room. **You speak for 30, maximum.** The remaining 15 belong
to them, and leaving it is not generosity, it is strategy: a panel that gets
its questions in feels it examined you, and a panel that feels rushed marks
defensively.

Timings below are cumulative. Say the clock out loud to yourself in rehearsal
twice. Do not rehearse a third time — over-rehearsal is what makes a viva
sound recited, and a recited viva reads as a student who cannot think on
their feet.

---

## The spine

One sentence you can say at 2am:

> **A linter can tell you the code is well written. Nothing can tell you it is
> the wrong thing. I built the instrument that can, and it found the wrong
> thing in my own data.**

Everything below is in service of that sentence.

---

## 0:00 – 2:00 · Open on the problem, not on yourself

Do not open with "my name is" and the agenda. They have your name.

> "Last year a team asked an agent for a command-line tool with six
> subcommands. It delivered a scheduled data pipeline. No command-line
> interface at all. Every quality gate they had went green, because every
> gate they had was asking whether the code was *good*, and none of them was
> asking whether it was *what was requested*.
>
> That is not a hypothetical. It is capture seventeen of my own study, and I
> will run it live in about twenty minutes."

**Why this works:** it is a story (pathos), it is your own data (ethos), and
it sets the promise the demo later redeems. You have told them to stay awake
for the demo.

---

## 2:00 – 5:00 · The question, stated as the dissertation states it

Put the research question on screen verbatim. Read it. Do not paraphrase a
research question in a viva — paraphrasing invites "so which is it?"

Then one line of positioning:

> "Benchmarks like SWE-bench ask: did it pass the tests? Linters ask: is it
> well written? Neither asks: is it the thing that was asked for. That gap is
> where my contribution sits."

**Transition:** *"So how do you measure that? You need three things: a fixed
specification, conditions that cannot see each other, and metrics that cannot
be gamed by the thing being measured."*

---

## 5:00 – 11:00 · Method

Six minutes, no more. Cover exactly:

1. **Five conditions**, named: `human_control`, `claude_code`,
   `cursor_agent`, `antigravity`, `replit_agent`.
2. **Three pre-registered specifications**, externalised as YAML so no spec
   content is ever hardcoded in the instrument.
3. **Ten repetitions per cell**, and say the deviation out loud before they
   find it — see "the three they will probe" below.
4. **Five metrics**, one analyser file each, never bundled.
5. **Blinding by construction:** the analysers receive a codebase and a
   specification. They are never told which condition produced the code.
   Say the phrase *"blinded by interface design, not by discipline"* — it is
   the strongest methodological sentence you own.

**Transition:** *"That is the apparatus. Here is what it found."*

---

## 11:00 – 18:00 · Findings, with the numbers on screen

Means across three specifications. **Verified against
`data/reports/main_001_plus_human.csv` on 22 October 2026** — 615 rows.

| metric | antigravity | claude_code | cursor_agent | human_control | replit_agent |
|---|---|---|---|---|---|
| security density (/kLOC) | 1.47 | **9.65** | 5.93 | **0.00** | 0.00 |
| complexity (mean cc) | 2.60 | 3.35 | 2.72 | **2.24** | 2.39 |
| duplication (%) | 4.26 | 0.00 | 0.90 | 0.00 | **9.56** |
| hallucinations (count) | 0.33 | 0.00 | 0.17 | 0.00 | **1.33** |
| correction frequency | — | — | — | 334.45 | — |

Three sentences, not thirteen:

- **"The agent with the best reputation produced the highest security
  density in this study."** `claude_code`, 9.65 per kLOC against a human
  baseline of 0.00. Do not editorialise. Let them react.
- **"The human baseline was not best at everything — it was best at the
  things humans are careful about."** Security and duplication: zero.
  Complexity: lowest. This is a defensible, modest claim.
- **"Correction frequency only exists for the human condition, by
  construction."** An agent has no keystrokes. Say this *before* they ask why
  the row is empty, or it looks like missing data.

**Transition:** *"Those are the numbers the dissertation reports. The more
interesting result is the one the numbers could not see."*

---

## 18:00 – 25:00 · The live demo — seven minutes, rehearsed

This is the centre of the viva. It is show-and-tell: they watch the
instrument work on real data, not a slide claiming it works.

**Before you walk in:** terminal font size 18pt minimum, light theme, window
maximised, `cd` already done, wifi irrelevant (everything is local).

### Step 1 — the brief (30 seconds)

```bash
head -20 specs/internal_tool_cli.yaml
```

> "Six subcommands. Pre-registered before any agent ran. This file is the
> definition of what was asked for."

### Step 2 — the agent that complied (90 seconds)

```bash
auditor scan data/raw/main_001__internal_tool_cli__claude_code__rep00/claude_code/code \
  --spec specs/internal_tool_cli.yaml
```

> "Five of six delivered, and every tick cites a file and a line. The one
> cross is `--help`. Not found."

### Step 3 — the agent that did not (2 minutes)

```bash
auditor scan data/raw/main_001__internal_tool_cli__antigravity__rep00/antigravity/code \
  --spec specs/internal_tool_cli.yaml
```

> **"Nought of six."**
>
> *(pause — let them read it)*
>
> "Four features missing outright. Two more where something with roughly the
> right name exists, and nothing a user can type reaches it. And at the
> bottom —"

```
Wrong shape: you asked for a command-line tool, and what is here
looks like a data pipeline
```

### Step 4 — the point (2 minutes)

> "Here is why this matters to the thesis. Both of those captures scored
> **0.00 on my own hallucination metric.** Identical. The metric asks what
> extra the agent shipped, and this agent shipped nothing extra — it shipped
> something *instead*. My own governance metric was partly blind to the
> failure my thesis is about.
>
> I did not discover that from the numbers. I discovered it by building a
> structural detector and pointing it at my own data. It is written up as
> Finding 001, and it is a limitation of the construct, not an erratum — no
> published number changes."

**This is the single best moment available to you.** A student who finds the
hole in their own instrument, documents it, and shows it live is demonstrating
exactly the critical self-appraisal the mark scheme rewards.

### Step 5 — zero setup (1 minute, only if time allows)

```bash
auditor scan ~/some-other-project
```

> "No specification was supplied here. It read the README, wrote
> `.auditor/spec.yaml`, and audited against it. It never reads your source
> code to decide what you wanted — a specification inferred from the code it
> measures is satisfied by that code by construction. A project that
> documents nothing gets no scope reading at all."

**Fallback:** if anything misbehaves, `viva/DEMO_TRANSCRIPT.txt` is the same
run captured today. Open it and keep talking. Never debug in front of a panel.

**Transition:** *"Which brings me to what this does not do."*

---

## 25:00 – 28:00 · Limitations, volunteered

Volunteering the weakness is worth more marks than defending it. You are
marked on critical appraisal, and you cannot demonstrate appraisal of a flaw
you waited to be shown.

Say all three. Out loud. Before they ask. See the next section for the
wording.

---

## 28:00 – 30:00 · Close

> "The contribution is not the five numbers. Static analysis has existed for
> thirty years. The contribution is specification fidelity as a measurable
> construct: a per-feature verdict, with evidence, against what was actually
> asked for — including the case where an agent builds the wrong thing
> entirely, which no functional benchmark can see.
>
> The instrument is released, it is installed about two hundred and fifty
> times a month, and it has audited its own maker. The self-audit is in the
> repository, warnings included."

Stop. Do not add "so, yeah". Stop on "warnings included" and look up.
