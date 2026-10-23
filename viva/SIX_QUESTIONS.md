# The six questions

Two examiners, three each. Your friend's three flavours: clarify a statement,
why did you do it that way, why did you not do it the other way.

Read this once. Do not memorise it. The answers are already in your
dissertation; this is only where to find them fast.

---

## The one rule

**Concede the fact in the first sentence, then explain.** Every examiner is
testing whether you can see your own work clearly. They stop pressing the
moment you show them you can.

Your dissertation is unusually honest — three deviations, two errata, a whole
section disowning your own statistics. That is your armour. Use it. Never
defend a number the text itself qualifies.

---

# Flavour 1 — "Clarify this statement"

### "What do you mean by architectural-prior dominance?"
> "The agent had a strong prior about what a project of that kind looks like,
> and that prior beat the brief. I asked for a command-line tool with six
> subcommands. It shipped a data pipeline. The workspace was verified clean
> and the prompt explicitly forbade pipeline output, so it was not
> contamination and it was not an ambiguous brief. The prior simply won."

### "What is 'blinded by construction'?"
> "Every analyser has the same signature — it receives a codebase and a
> specification, and nothing else. It is never given the condition label; the
> orchestrator attaches that after scoring. So a biased analyser would have to
> be biased without knowing what to be biased about. That is stronger than
> blinding by protocol, because it is enforced by the type signature rather
> than by my discipline."

### "Explain pseudoreplication in your own words."
> "Two of the four tools live inside an IDE I cannot script. I captured one
> session per specification and replayed it ten times so the CSV had a
> consistent shape. Those ten rows look like ten observations and are one.
> Counting them as ten inflates every statistic computed over them. Section
> 4.5.1 says so, and 4.5.2 disowns those numbers in bold."

### "You say Level 3 is 'a power result, not a null result'. Why does that matter?"
> "Because a null result would mean I found the tools to be the same. I did
> not. With three cells per condition only an overwhelming effect could reach
> my threshold, so finding nothing is what the design predicts whether or not
> a difference exists. Reporting it as a null would be claiming evidence of
> absence from a design that cannot produce it."

### "Replit scored 0.00 on security. Is Replit the most secure tool?"
> "No, and I report it as an artefact rather than a win. Bandit reads Python.
> Replit's output is 6% Python against 52% TypeScript, so there is almost
> nothing for the scanner to read, and it wrote no tests either. The metric is
> a per-language density, not a vulnerability count. Section 5.2."

### "Your human baseline scored complexity 0.00 on the CLI. Is that plausible?"
> "It is an artefact and the most methodologically useful data point I have. I
> wrote that CLI as top-level script code with no functions. McCabe complexity
> is measured per function, so there was nothing to average over. It is not a
> simpler program — it is an undecomposed one. The metric is confounded with
> decomposition style, which the instrument surfaced rather than hid."

---

# Flavour 2 — "Why did you do it that way?"

### "Why Bonferroni at 0.01?"
> "Five metrics, family-wise error at 0.05, so 0.01 per metric. Fixed before
> collection, in the pre-registration. And I will volunteer the problem with
> it: a correct correction for the four metrics I actually tested is 0.0025,
> and neither of my two significant results survives that. Section 4.5.2."

### "Why non-parametric tests?"
> "Not a preference — a consequence. The replay conditions contribute zero
> within-cell variance, which violates the equal-variance precondition for
> every metric. The pre-registration specified Shapiro–Wilk and Levene as
> gates, and they failed, so Kruskal–Wallis was the registered fallback."

### "Why three specifications?"
> "To tell a general tool property from a task-specific one. It turned out to
> be essential. A CLI-only study would have indicted Replit and left
> Antigravity looking clean; a web-app-only study would have found them
> equally culpable and missed Replit's worst failure entirely. Table 4.2."

### "Why local Bandit instead of SonarCloud?"
> "The SonarCloud design queried one project key per specification, so every
> condition shared a numerator while the denominator varied — structurally
> broken. I abandoned it in the pilot and documented why."

### "Why report Level 1 at all if you disown it?"
> "So a reader who downloads the CSV and runs the obvious test arrives at my
> arithmetic and can see exactly why it must be discounted. Hiding it would
> mean the first person to reproduce my data would think they had caught me."

### "Why exclude the human baseline from the statistics?"
> "One session per specification. It cannot support variance estimation, so it
> is a reference floor, not a condition. Deviation 003."

---

# Flavour 3 — "Why did you NOT do X?"

### "Why not capture Replit and Antigravity live, like the others?"
**The big one. Expect it.**
> "They expose no scriptable interface — one runs in a browser IDE, the other
> on a desktop. I could drive the two CLI tools with subprocess; I could not
> drive those. So I captured each by hand and replayed. That is the most
> serious limitation in the thesis, I say so in §5.7, and it is the first
> priority of any continuation in §6.4. It is a finding about the instrument
> rather than about the vendors."

### "Why not run the two-way ANOVA you pre-registered for RQ3?"
> "It is inadmissible on the executed design. With one effective observation
> per cell in two conditions the interaction term has no residual degrees of
> freedom — the statistic is undefined. An earlier draft reported interaction
> F-statistics and I withdrew them. RQ3 is answered descriptively instead,
> and I say that plainly rather than reporting a number I cannot defend."

### "Why not quote the repaired kappa? It's 1.00."
> "Because it is circular. The raters' disagreement is what exposed the
> defect; repairing it and then measuring against the same labels proves
> nothing. Validating the repaired instrument needs a fresh sample and raters
> who have not seen these items. The figures of record are 0.87, 0.85 and
> 0.73."

### "Why not more tools — Copilot, Windsurf, Devin?"
> "Scope and capture cost. Each tool is one adapter, so the instrument extends
> cheaply; what does not extend cheaply is ten replications per cell on a tool
> with no scriptable interface. I would rather four tools captured properly
> than eight captured the way I had to capture Replit."

### "Why not measure runtime behaviour or maintenance cost?"
> "Deliberately out of scope — §1.6 — and in future work. Everything I measure
> is computable by static analysis without a runtime oracle, which is what
> makes it reproducible by someone who was not there."

### "Why not report total vulnerability counts as well as density?"
> "I should have, and §6.4 says so. Density alone is what let Replit's 0.00
> look like a security result. A total-CWE companion is the fix."

---

# If you only hold three things

1. **"Half my data are copies."** Say it before they do.
2. **"Both agents scored zero. One built the CLI. The other built a pipeline."**
   Your thesis in one sentence.
3. **"I would rather tell you where this is thin than have you find it."**

---

# One thing to volunteer unprompted

They are reading the September submission. Since then you found that the
evidence rule behind the hallucination count credited a feature whenever its
name appeared anywhere in the codebase — a word in a comment was enough. You
wrote it up as Erratum 003, fixed it, and released it.

Say this near the end:

> "One thing that is not in the document you have. After submission I found
> that the evidence rule behind the hallucination count was too weak — it
> credited a feature if the word appeared anywhere, including in a comment. I
> published it as a third erratum and corrected the instrument. The published
> figures remain reproducible under the old rule, and version 0.6.0 went live
> yesterday."

That is a student still auditing their own work a month after submitting it.
It is the best thing you can say in that room.
