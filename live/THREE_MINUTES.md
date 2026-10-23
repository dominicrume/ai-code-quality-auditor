# Three minutes. Two commands. One confession.

Terminal 18pt, light theme, full screen. Nothing else open.

    cd ~/Downloads/NEW-enterprise-ai-code-quality-auditor

===========================================================
0:00 — 0:25   THE HOOK
===========================================================

"I said 6pm. It's 8. I was defending a dissertation at 2 and I wasn't fit
 to do this at 6.

 That's the smallest honest thing I'll say in the next three minutes."

===========================================================
0:25 — 0:45   THE PROBLEM
===========================================================

"Agents are being handed treasuries and workflows.

 A linter tells you the code is well written.
 Nothing tells you it's the wrong thing."

===========================================================
0:45 — 1:20   COMMAND ONE
===========================================================

PASTE:

./.venv/bin/auditor scan data/raw/main_001__internal_tool_cli__claude_code__rep00/claude_code/code --spec specs/internal_tool_cli.yaml --no-history

"I asked for six commands. Five are there — and look beside each one.
 tool.py line 192. That's a receipt, not a claim.

 One red. Asked for, never built. It says so."

===========================================================
1:20 — 2:05   COMMAND TWO            <-- the money shot
===========================================================

PASTE:

./.venv/bin/auditor scan data/raw/main_001__internal_tool_cli__antigravity__rep00/antigravity/code --spec specs/internal_tool_cli.yaml --no-history

WAIT TWO SECONDS. Let zero land.

"Zero of six. Same brief.

 And the amber — the code exists, nothing exposes it.
 A kitchen with no door.

 A checker that searched for the word 'init' would have scored this
 two out of six and been wrong. Mine asks whether you can reach it.

 Look at the filename. pipeline.py.
 I asked for a command-line tool. It built a data pipeline."

===========================================================
2:05 — 2:45   THE CONFESSION
===========================================================

"Now the part I'd rather skip.

 This morning a user pointed my tool at a folder of documents.
 It reported zero of twelve delivered — against twelve things
 nobody asked for. It had scraped commit messages and called them
 a specification.

 My own tool. Lying with a straight face.

 Every part worked. Nothing asked: how sure am I this is the brief?

 It's fixed. Pushed an hour ago. Fourth defect written up rather
 than quietly patched — first one found by somebody outside."

===========================================================
2:45 — 3:00   THE ASK
===========================================================

"pip install ai-code-quality-auditor

 Point it at something you own. If it gives you a reading you don't
 believe — tell me. The last person who did is why this talk has a
 story in it."

===========================================================
IF IT BREAKS
===========================================================
Open viva/auditor_demo.mp4. "Same run, recorded this morning."
Keep talking. Never debug on air.

NEVER SAY
- SonarCube. It is Bandit, run locally.
- That it proves code is safe. It takes a reading.
