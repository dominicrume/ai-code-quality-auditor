# Live run sheet — 25 minutes

Terminal at 18pt, light theme. Two tabs only: terminal, and the repo on
GitHub. Close everything else. Phone face down.

```
cd ~/Downloads/NEW-enterprise-ai-code-quality-auditor
```

---

## 0:00 — Open on the miss (90 sec)

"I said 6pm. It's 8. I'd finished a viva at 2 and I was not fit to do this
at 6, so I did it at 8 instead. That is the smallest honest thing I'll say
tonight, and the rest get bigger."

Do not apologise twice. Move.

---

## 1:30 — The problem (2 min)

"Agents are being handed treasuries and workflows. The tooling we check them
with asks one question: does it work? A linter tells you the code is well
written. Nothing tells you it's the wrong thing."

---

## 3:30 — DEMO ONE: an agent that did the job (3 min)

./.venv/bin/auditor scan data/raw/main_001__internal_tool_cli__claude_code__rep00/claude_code/code --spec specs/internal_tool_cli.yaml --no-history

Point at the green ticks AND the file:line beside each.
"That's a receipt, not a claim. Go and look at line 192."
Point at the one red X. "Asked for, never built. It says so."

---

## 6:30 — DEMO TWO: an agent that did not (4 min)

./.venv/bin/auditor scan data/raw/main_001__internal_tool_cli__antigravity__rep00/antigravity/code --spec specs/internal_tool_cli.yaml --no-history

Let "0 of 6 delivered" sit for two seconds. Then the amber lines:

"Built but unreachable. The code exists, nothing exposes it. It's a kitchen
with no door. A checker that searched for the word 'init' would have scored
this 2 of 6 and been wrong. Mine asks whether you can reach it."

Then the filename: code/pipeline.py.
"I asked for a command-line tool. It wrote a pipeline. The evidence of the
wrong building is in the path."

---

## 10:30 — THE KINTSUGI: my own tool, lying (6 min)   <-- the centrepiece

"Now the part I'd rather not show you. This morning a user pointed this at a
folder of working documents."

Show the screenshot: 0 of 12 delivered, twelve red crosses.

"'Finalise the contract.' 'The why-this-role screening answer.' None of those
is a software feature. Nobody asked for them there. My tool scraped commit
messages, called them a specification, and reported a verdict."

"Every component worked correctly. Discovery found text. The analyser searched
honestly. The system still lied, because nothing in it asked: how confident am
I that this is actually the brief?"

Then the fix, live:

./.venv/bin/auditor scan /path/to/a/docs/folder --no-history

"Intent unknown. Scope drift withdrawn. It tells you why and what to supply."

"A brief you give me is evidence. A brief I guessed is not. Zero against a
guess impugns the guess."

Show the commit on GitHub. Show FINDING_002.

---

## 16:30 — Why this matters for a business (4 min)

- Select on profile, not rank. No single ranking is valid across a portfolio.
- Gate on fidelity. Put it in CI next to the tests, not instead of them.
- Budget for scaffolding debt. One agent shipped 9.56% duplication by default.

"Containment is a precondition for adoption that nobody currently tests."

---

## 20:30 — Close + ask (3 min)

pip install ai-code-quality-auditor

"Point it at something you own. If it gives you a reading you don't believe,
tell me — the last person who did is the reason tonight has a story in it."

Repo and package links in the comments.

---

## IF IT BREAKS

Open viva/auditor_demo.mp4. "Same run, recorded this morning." Keep talking.
Never debug on air.

## DO NOT

- Say SonarCube. It is Bandit, run locally. SonarCloud was piloted and dropped.
- Say the tool proves code is safe. It takes a reading.
- Quote the post-repair kappa. It is circular and you know it.
