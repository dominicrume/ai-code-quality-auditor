# Tonight and tomorrow morning

## Tonight — three things only

**1. Get the seven assessment criteria.** Your own submitted proposal form
says it responds "against the module's seven assessment criteria". They are
not written down anywhere in this repository. You cannot walk into a viva
unable to name what you are marked on. Blackboard → EP4DIS → assessment.
**This is the highest-value hour you have left.**

**2. Rehearse the demo twice.** Not the talk — the demo. Terminal at 18pt,
light theme, commands already in history so you can arrow up. The two
commands are in `VIVA_PACK.md` §18:00.

**3. Read `HARD_QUESTIONS.md` once, out loud.** Once. Then stop.

## Do not do tonight

- Do not change the dissertation. It is submitted.
- Do not write new slides after 9pm.
- Do not run a fourth rehearsal. Over-rehearsed sounds recited, and recited
  reads as someone who cannot think on their feet.

## Tomorrow morning, 20 minutes before

```bash
cd ~/Downloads/NEW-enterprise-ai-code-quality-auditor
.venv/bin/python -m pytest -q | tail -2          # expect 258 passed
open viva/DEMO_TRANSCRIPT.txt                     # the fallback, ready
```

Have open, in this order: the terminal, `viva/NUMBERS.md`,
`viva/DEMO_TRANSCRIPT.txt`.

## The three sentences that carry the whole viva

1. *"A linter tells you the code is well written. Nothing tells you it is the
   wrong thing."*
2. *"Both of those agents scored zero. One built the CLI. The other built a
   data pipeline."*
3. *"I would rather tell you where this is thin than have you find it."*

## If the demo fails

Open the transcript. Say: *"Same run, captured yesterday."* Keep talking.
Never debug in front of a panel — it converts a strong viva into a support
call.

## Publishing — after the viva, not before

0.6.0 is built, tagged and pushed to GitHub, and is **not** on PyPI. Leave it
that way until you are out of the room. Publishing the night before gives you
a new variable and no new marks.

```bash
.venv/bin/python -m twine upload dist/ai_code_quality_auditor-0.6.0*
# then yank 0.1.0 … 0.5.1 on pypi.org — publish FIRST, yank SECOND
```

If anyone asks tomorrow why the released version is 0.5.1 while you are
demonstrating 0.6.0: *"0.6.0 is tagged and built; I am not pushing a release
the night before a viva. It goes out tomorrow afternoon."* That is a good
answer. It sounds like someone who ships carefully.
