"""Where the text of a file is not code.

Why this exists
---------------
FINDING_003 required two things of its fix. The first, a subject gate, shipped.
The second was written as: *decline to credit a marker found only in a file
whose role is to describe the standard.* That was built for the governance
checker, by matching identifiers from the parsed syntax tree instead of raw
source text. It was never built for the fidelity analysers, and FINDING_004 is
the same defect arriving in the second place: ``auditor scan .`` on this
repository reported ``add``, ``/path`` and ``export`` as shipped surface,
because those are the strings the detectors search for, sitting in the
docstrings that document them.

The naive repair is to exclude the instrument's own paths. That fixes this
repository and leaves every customer whose docstring contains an example route
exactly as exposed. The repair that generalises is to know, per file, which
byte ranges hold string and comment text, and to decline any detection that
begins inside one.

What this is not
----------------
It is not a parse of the code. It answers one question — is this offset inside
a literal or a comment — and answers it exactly for Python, where the
language's own tokeniser is available, and lexically for JavaScript and
TypeScript, where it is not.

The offset tested is the **start of the whole construct**, not the name. A
route's name is written inside a string by design: in ``@app.get("/orders")``
the construct starts at the ``@``, which is code, while the same text inside a
docstring starts inside the string token. That distinction is the entire fix,
and testing the name's offset instead would discard every route in every
codebase.
"""
from __future__ import annotations

import io
import tokenize
from bisect import bisect_right

PY_SUFFIXES = (".py",)
JS_SUFFIXES = (".js", ".jsx", ".ts", ".tsx")


class Mask:
    """The spans of one file that hold string or comment text.

    Spans are merged and sorted on construction so a lookup is a binary
    search: ``index`` tests every match of every pattern against this, and a
    linear scan would make the cost quadratic in a large file.
    """

    __slots__ = ("_starts", "_ends")

    def __init__(self, spans: list[tuple[int, int]]) -> None:
        merged: list[list[int]] = []
        for start, end in sorted(spans):
            if end <= start:
                continue
            if merged and start <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], end)
            else:
                merged.append([start, end])
        self._starts = [s for s, _ in merged]
        self._ends = [e for _, e in merged]

    def __bool__(self) -> bool:
        return bool(self._starts)

    def __len__(self) -> int:
        return len(self._starts)

    def covers(self, offset: int) -> bool:
        """True when this offset falls inside a literal or a comment."""
        i = bisect_right(self._starts, offset) - 1
        return i >= 0 and offset < self._ends[i]


def _line_offsets(content: str) -> list[int]:
    offsets = [0]
    for line in content.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line))
    return offsets


def _offset(offsets: list[int], row: int, col: int) -> int:
    if row < 1:
        return 0
    if row >= len(offsets):
        return offsets[-1]
    return offsets[row - 1] + col


def _python_spans(content: str) -> list[tuple[int, int]]:
    """Exact literal and comment spans, from the language's own tokeniser."""
    quoted = {tokenize.STRING, tokenize.COMMENT}
    # 3.12 splits f-strings into START / MIDDLE / END, and the code inside the
    # braces is real code between them. Masking only MIDDLE is correct on new
    # interpreters, and the attribute is simply absent on older ones.
    middle = getattr(tokenize, "FSTRING_MIDDLE", None)
    if middle is not None:
        quoted.add(middle)

    offsets = _line_offsets(content)
    spans: list[tuple[int, int]] = []
    for tok in tokenize.generate_tokens(io.StringIO(content).readline):
        if tok.type in quoted:
            spans.append((_offset(offsets, *tok.start), _offset(offsets, *tok.end)))
    return spans


def _lexical_spans(content: str, line_comment: str, triple: bool) -> list[tuple[int, int]]:
    """Literal and comment spans found by scanning, for text we cannot parse.

    Used for JavaScript and TypeScript, and for Python that does not tokenise
    — a captured file that will not parse is still a file whose docstrings must
    not be read as routes.

    A regular-expression literal is not tracked. Distinguishing ``/`` as
    division from ``/`` as the start of a pattern needs the parse this module
    does not have, and guessing wrong would mask live code, which hides real
    findings. The error is therefore left in the direction of reporting too
    much rather than too little.
    """
    spans: list[tuple[int, int]] = []
    i, n = 0, len(content)
    while i < n:
        ch = content[i]
        if content.startswith(line_comment, i):
            end = content.find("\n", i)
            end = n if end < 0 else end
            spans.append((i, end))
            i = end
            continue
        if content.startswith("/*", i):
            end = content.find("*/", i + 2)
            end = n if end < 0 else end + 2
            spans.append((i, end))
            i = end
            continue
        if ch in "\"'`":
            quote, size = ch, 1
            if triple and content.startswith(ch * 3, i):
                quote, size = ch * 3, 3
            j = i + size
            while j < n:
                if content[j] == "\\":
                    j += 2
                    continue
                if content.startswith(quote, j):
                    j += size
                    break
                j += 1
            else:
                j = n
            spans.append((i, min(j, n)))
            i = min(j, n)
            continue
        i += 1
    return spans


def mask_for(path: str, content: str) -> Mask:
    """The literal-and-comment mask for one file, empty for unknown types."""
    if path.endswith(PY_SUFFIXES):
        try:
            return Mask(_python_spans(content))
        except (tokenize.TokenError, SyntaxError, IndentationError, ValueError):
            # A capture that does not tokenise still has docstrings in it.
            return Mask(_lexical_spans(content, "#", True))
    if path.endswith(JS_SUFFIXES):
        return Mask(_lexical_spans(content, "//", False))
    return Mask([])
