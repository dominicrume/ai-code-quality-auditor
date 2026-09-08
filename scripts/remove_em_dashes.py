#!/usr/bin/env python3
"""Replace every em dash in the dissertation with conventional punctuation.

Heavy em-dash use is a recognised marker of machine-generated prose, which is a
poor look in a dissertation whose subject is machine-generated work. En dashes
are left alone: they are correct typography for ranges (2.2-2.5) and for
compound proper names (Shapiro-Wilk, Mann-Whitney, Aston-Capgemini).

Rules, in order of application:
  1. Headings           "Chapter 1 - Introduction"  ->  colon
  2. Paired dashes      "X - aside - Y"             ->  commas, or parentheses
                                                        when the aside itself
                                                        contains a comma
  3. Single, before a coordinator ("and", "but")    ->  comma
  4. Single, before an independent clause           ->  semicolon
  5. Single, otherwise (appositive, list, gloss)    ->  comma, or colon when
                                                        what follows is a list

The output is reviewed by hand afterwards; these rules get the shape right,
they do not replace judgement.

    .venv/bin/python scripts/remove_em_dashes.py [--check]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs/dissertation/DISSERTATION_FULL.md"

EM = "—"

# A clause that can stand alone: pronoun or determiner followed by a verb.
INDEP = re.compile(
    r"^(it|this|that|these|those|they|the\s+\w+|there|its|their|he|she|we|i)\s+"
    r"(is|are|was|were|has|have|had|does|do|did|can|could|will|would|may|might|"
    r"must|should|becomes?|makes?|gives?|shows?|means?|remains?|carries|rests?|"
    r"stands?|holds?|reads?|scored?|scores?|ships?|treats?|measures?)\b",
    re.I)

LIST_AHEAD = re.compile(r"^[^.;:]{0,140}?,[^.;:]{0,140}?,")


def split_sentences(text: str) -> list[str]:
    return re.split(r"(?<=[.!?])\s+", text)


def fix_sentence(sent: str) -> str:
    if EM not in sent:
        return sent

    # 2. paired dashes
    while sent.count(EM) >= 2:
        a = sent.index(EM)
        b = sent.index(EM, a + 1)
        inner = sent[a + 1:b].strip()
        before = sent[:a].rstrip()
        after = sent[b + 1:].lstrip()
        if "," in inner:
            sent = f"{before} ({inner}) {after}"
        else:
            sent = f"{before}, {inner}, {after}"
        sent = re.sub(r"\s+([,.;:])", r"\1", sent)
        sent = re.sub(r",\s*,", ",", sent)
        sent = re.sub(r"\(\s*", "(", sent)
        sent = re.sub(r"\s*\)", ")", sent)

    # 3-5. a single remaining dash
    if EM in sent:
        a = sent.index(EM)
        before = sent[:a].rstrip()
        after = sent[a + 1:].lstrip()
        low = after.lower()
        if re.match(r"^(and|but|so|yet|or)\b", low):
            joiner = ", "
        elif INDEP.match(low):
            joiner = "; "
        elif LIST_AHEAD.match(after):
            joiner = ": "
        else:
            joiner = ", "
        if before.endswith((",", ";", ":")):
            before = before[:-1]
        sent = f"{before}{joiner}{after}"

    sent = re.sub(r"\s+([,.;:])", r"\1", sent)
    sent = re.sub(r",\s*,", ",", sent)
    sent = re.sub(r";\s*;", ";", sent)
    return sent


def fix_line(line: str) -> str:
    if EM not in line:
        return line
    # 1. headings and the title block: a colon reads better than a comma
    if line.startswith("#") or line.startswith("**MSc"):
        return line.replace(f" {EM} ", ": ")
    if line.lstrip().startswith(("|", ">")):
        return line.replace(f" {EM} ", ", ")
    return " ".join(fix_sentence(s) for s in split_sentences(line))


def main() -> None:
    text = SRC.read_text()
    # operate on flattened paragraphs so a dash split across a line break is seen
    paras = re.split(r"(\n\s*\n)", text)
    out = []
    for chunk in paras:
        if chunk.strip() == "" or EM not in chunk:
            out.append(chunk)
            continue
        if chunk.lstrip().startswith(("|", ">", "#", "**MSc")):
            out.append("\n".join(fix_line(l) for l in chunk.split("\n")))
            continue
        lines = chunk.split("\n")
        flat = " ".join(l.strip() for l in lines)
        fixed = " ".join(fix_sentence(s) for s in split_sentences(flat))
        # re-wrap to the file's ~80-column convention
        words, line, wrapped = fixed.split(" "), "", []
        for w in words:
            if len(line) + len(w) + 1 > 80 and line:
                wrapped.append(line)
                line = w
            else:
                line = f"{line} {w}".strip()
        if line:
            wrapped.append(line)
        out.append("\n".join(wrapped))

    result = "".join(out)
    remaining = result.count(EM)
    if "--check" in sys.argv:
        print(f"would leave {remaining} em dashes")
        return
    SRC.write_text(result)
    print(f"em dashes remaining: {remaining}")


if __name__ == "__main__":
    main()
