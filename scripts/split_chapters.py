#!/usr/bin/env python3
"""Regenerate the per-chapter files as extracts of DISSERTATION_FULL.md.

These existed as hand-maintained drafts and drifted: by September they still
carried pre-erratum figures and withdrawn statistics while the master had moved
on. Two files claiming to be Chapter 4, one of them wrong, is how a marker ends
up reading the wrong one. They are now derived, never edited.

    .venv/bin/python scripts/split_chapters.py
"""
from __future__ import annotations

import re
import subprocess
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs/dissertation/DISSERTATION_FULL.md"
OUT = SRC.parent

CHAPTERS = {
    "Chapter 3": "CHAPTER_3_METHODS.md",
    "Chapter 4": "CHAPTER_4_RESULTS.md",
}

BANNER = """> **Generated file — do not edit.**
> Extracted from `DISSERTATION_FULL.md` on {when} by
> `scripts/split_chapters.py`. Edit the master and re-run; any change made
> here is overwritten. The master is the submission artefact.

---

"""


def _master_date() -> str:
    """The date the master last changed, not the date the script ran.

    Stamping today's date made every extract differ from its committed copy
    the morning after, so the sync check failed with no change to the text.
    """
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%cs", "--", str(SRC)],
                             cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
        return out or date.today().isoformat()
    except (OSError, subprocess.CalledProcessError):
        return date.today().isoformat()


def main() -> None:
    lines = SRC.read_text().splitlines()
    starts = [(i, l) for i, l in enumerate(lines) if re.match(r"^# Chapter \d", l)]
    starts.append((len(lines), ""))

    written = 0
    for (i, head), (j, _) in zip(starts, starts[1:]):
        key = re.match(r"^# (Chapter \d)", head).group(1)
        if key not in CHAPTERS:
            continue
        body = lines[i:j]
        # editorial blockquotes belong to the master, not to an extract
        body = [l for l in body if not l.startswith(">")]
        while body and not body[-1].strip():
            body.pop()
        # figure paths are relative to docs/dissertation in both files
        text = BANNER.format(when=_master_date()) + "\n".join(body) + "\n"
        p = OUT / CHAPTERS[key]
        p.write_text(text)
        n = len(re.findall(r"\S+", "\n".join(body)))
        print(f"  wrote {p.name}  ({n:,} words)")
        written += 1
    print(f"{written} chapter file(s) regenerated from the master")


if __name__ == "__main__":
    main()
