"""McCabe complexity for JavaScript and TypeScript, without a JS toolchain.

radon reads Python only, which left every TypeScript function in this study
unscored. Rather than add a Node dependency to a Python tool, this walks the
source and counts decision points per function, which is the definition McCabe
gives: one plus the number of branches.

It is a lexical approximation and is honest about that. Strings and comments
are stripped first so that a branch keyword inside a message is not counted,
and nesting is tracked by brace depth so that a nested arrow function is scored
as its own unit rather than folded into its parent.
"""
from __future__ import annotations

import re

# Each of these introduces one independent path through the code.
DECISION = re.compile(
    r"\b(if|for|while|case|catch)\b"
    r"|\?\?|\?\.|&&|\|\||\?(?!\.)"
)

# A method or function header immediately preceding an opening brace. The
# negative lookahead keeps control-flow constructs out: `if (x) {` has the same
# shape as a call followed by a block and would otherwise open a new unit.
KEYWORDS = r"if|for|while|switch|catch|do|else|try|return|typeof|await|with"

# Matched against the text immediately preceding an opening brace, and every
# alternative is anchored to the end of that window. Without the anchor the
# `function` keyword of an enclosing definition matches again at each nested
# brace, and one function is counted as several.
FUNC_START = re.compile(
    r"(?:"
    r"\bfunction\b[^{}();]*"                      # function f(...)  /  function (...)
    r"|=>\s*"                                      # arrow body
    r"|(?<![\w$])(?:async\s+)?"
    r"(?!(?:" + KEYWORDS + r")(?![\w$]))"          # not a control-flow header
    r"[A-Za-z_$][\w$]*\s*\([^()]*\)\s*(?::[^{;]+)?"   # name(...)  /  name(...): T
    r")$"
)

_STRINGS = re.compile(r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"|`(?:\\.|[^`\\])*`")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_LINE_COMMENT = re.compile(r"//[^\n]*")


def strip_noise(src: str) -> str:
    """Remove comments and string bodies so keywords in text are not counted."""
    src = _BLOCK_COMMENT.sub(" ", src)
    src = _LINE_COMMENT.sub(" ", src)
    return _STRINGS.sub('""', src)


def complexities(source: str) -> list[int]:
    """One McCabe score per function-like unit found in the source."""
    src = strip_noise(source)
    scores: list[int] = []
    stack: list[int] = []          # complexity of each open function
    depth_of: list[int] = []       # brace depth at which each was opened
    depth = 0
    i = 0
    while i < len(src):
        ch = src[i]
        if ch == "{":
            # a function header seen just before this brace opens a new unit
            window = src[max(0, i - 120):i].rstrip()
            if FUNC_START.search(window):
                stack.append(1)
                depth_of.append(depth)
            depth += 1
        elif ch == "}":
            depth -= 1
            if stack and depth_of and depth == depth_of[-1]:
                scores.append(stack.pop())
                depth_of.pop()
        elif stack:
            m = DECISION.match(src, i)
            if m:
                stack[-1] += 1
                i = m.end()
                continue
        i += 1
    scores.extend(stack)           # unbalanced braces: keep what was counted
    return scores
