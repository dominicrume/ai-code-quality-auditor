# The questions that can hurt, and what to say

Rule for all of them: **concede the fact in the first sentence.** An examiner
testing whether you can see your own weakness stops testing the moment you
show them you can. Defend after you concede, never before.

---

## 1. "Your headline finding is N = 1."

**They are right. Say so first.**

> "It is. The Replit CLI cell is one captured session replayed ten times, and
> the ten rows add no independent evidence — §4.3.1 says that in the text.
>
> What the finding rests on is not the count. It is direct code inspection,
> under two controls: a verified-clean workspace, and a prompt that explicitly
> prohibited pipeline output. The agent produced `run`, `schedule` and
> `check-config` around `run_pipeline`. The intersection with the six
> specified subcommands is empty. That is a case study, and I report it as
> one.
>
> The fix is live multi-session re-capture, which is §6.4."

**Do not** say "but it replicated ten times". They will know that is the
replay, and you will have spent your credibility.

---

## 2. "Half your data are copies. What actually survives?"

> "Two of the four agent conditions are replays — Deviation 001 — so their
> within-cell variance is zero by construction. Treating thirty rows as thirty
> observations is pseudoreplication and it inflates every statistic computed
> over it.
>
> That is why Chapter 4 reports three levels and disowns Level 1 in bold.
> Inference is confined to the two live conditions. What survives is **one**
> comparison: complexity, Claude Code versus Cursor, U = 641.5, p = 0.0047,
> N = 30 each, both arms genuinely replicated.
>
> And I will volunteer the next bit before you ask: a correct correction
> across four metrics is α = 0.0025, and neither Table 4.3 result survives
> that. Section 4.5.2 says so."

**Why volunteer it:** they almost certainly spotted it. Saying it yourself
converts their strongest card into your evidence of rigour.

---

## 3. "Deviation 002 says the Replit CLI cell reports N = 0 and is excluded. That cell is your headline. Which document is wrong?"

**This one is real and you must not improvise.**

> "The log is stale, the data are not. Deviation 002 was written on 31 May,
> when those two cells were deferred. They were captured on 1 June — the
> provenance file timestamps the complete four-by-three-by-ten matrix — and
> the log entry was never given a closing note. That is a documentation
> failure on my part, not a data one.
>
> The test is whether the dataset is what it claims to be, and that is
> checkable: every published figure re-derives from the frozen CSV. I would
> rather be judged on that than on my filing."

A dated addendum has been added to `PROTOCOL_DEVIATIONS.md` today, marked as
added today. **Do not pretend it was always there.** If asked: "I added a
closing note when I found the gap preparing for today."

---

## 4. "Section 4.9 says Antigravity's hallucinations fall entirely in the web-app spec. But Finding 001 says it also substituted a pipeline for your CLI brief. Which is it?"

**Both. And this is your best answer in the whole viva.**

> "Both are true, and the gap between them is the thesis.
>
> Antigravity's hallucination *count* is 1.00 on the web app and 0.00 on the
> CLI. That sentence is accurate. What it does not say is that on the CLI
> brief Antigravity shipped a scheduled data pipeline with no subcommand of
> any kind — and scored zero, because the metric asks what *extra* was
> shipped, and it shipped nothing extra. It shipped something *instead*.
>
> My own governance metric was partly blind to the failure my thesis is
> about. I found that on 12 September, wrote it up as Finding 001, and it is
> the reason the instrument now has a structural shape detector. I can show
> you that running on the capture, live, in about four minutes."

Then **run the demo**. This is the moment to use it.

---

## 5. "Claude Code scored worst on security. Isn't that just the test-assertion artefact?"

> "Partly, and that is Erratum 001. The original figure was 42.05 per kLOC;
> about 77% of it was Bandit's B101 firing on `assert` inside test files, so a
> well-tested submission scored worse than an untested one. Corrected, it is
> 9.65.
>
> 9.65 is still the highest in the study, against a human baseline of 0.00.
> The ordering survived the correction; the magnitude did not."

---

## 6. "Replit scored 0.00 on security. Is Replit the safest?"

> "No, and the number is an artefact I report as one. Bandit reads Python.
> Replit's output was about 6% Python against 52% TypeScript. The denominator
> is nearly empty, so 0.00 means 'not read', not 'secure' — section 5.2.
>
> That is the single clearest example of the failure the whole instrument is
> about, and it was in my own tool. The released version now reports unread
> code as `unread` and refuses to band it."

---

## 7. "Why not SonarQube, or SWE-bench?"

> "SonarQube scores a codebase; it cannot compare tools under controlled
> conditions, and I use static analysers as instruments *inside* the
> experiment rather than as the experiment. SWE-bench asks whether public
> tasks pass their tests — never your specification, and it is blind to an
> agent building the wrong artefact entirely.
>
> Neither asks the question I am asking."

---

## 8. "What is the actual contribution?"

Do not say "five metrics". They exist already.

> "Three things. A capture contract that makes a human session and an agent
> session scoreable by the same analyser. Blinding by construction rather than
> by discipline — the analysers take a codebase and a specification and are
> never given the condition. And specification fidelity as a measurable
> construct: a per-feature verdict with file-and-line evidence, including the
> substitution case no functional benchmark can see.
>
> The empirical contribution is narrower and I would state it narrowly: one
> inferentially supported comparison, and a case study."

---

## 9. "Is deriving the specification from the repository not circular?"

> "It would be if I read the code, and that is exactly why I do not. Intent is
> read from documents that state intent — a requirements file, the README,
> the package description, commit subjects — never from the source tree. A
> specification inferred from the code it measures is satisfied by that code
> by construction: every feature delivered, nothing ever missing, a hundred
> per cent for any repository on earth.
>
> A project that documents nothing gets no scope reading at all. There is a
> test that enforces it."

---

## 10. "What would you do with another year?"

Have this ready; it is often the closing question and a weak answer deflates
a strong viva.

> "Three things, in order. Live multi-session capture for the IDE-bound
> tools, which is the only way to turn the case studies into replicated
> results. A properly powered reliability study — κ on eighteen items is
> suggestive, not settled, and a single item moves it by a tenth. And
> validating the shape detector against hand-labelled captures, because right
> now its behaviour on the two captures that motivated it is a smoke test,
> not validation."

---

## The two sentences to keep in your pocket

If you lose your footing, either of these buys you the room back:

> "I would rather tell you where this is thin than have you find it."

> "That is in the deviations log / the errata — I found it, and here is what
> it changed."
