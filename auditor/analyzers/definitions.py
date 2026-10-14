"""What the codebase actually defines, and where.

Why this exists
---------------
The scope-drift metric credited a specification feature when the feature id's
terminal token appeared anywhere in a single blob of every file concatenated
together. Given a six-feature CLI specification and an ETL script implementing
none of it, that rule credited five of the six, because the words ``add``,
``list``, ``export``, ``validate`` and ``remove`` occur in the script's
comments. On Python it would credit ``cli.list`` for the word in ``list(x)``.

A claim about delivery has to rest on something the code declares, not on a
word appearing somewhere in it. This module builds that index: every command,
route, function, class and export the codebase defines, each with the file and
line where it is written, so a verdict can cite its evidence.

Surface and internals
---------------------
A definition is either part of the **surface** a user can invoke -- a
registered subcommand or an HTTP route -- or an **internal**: a function, class
or export that exists but that nobody outside the program can reach. The
distinction is what separates "this was delivered" from "something with the
right name exists but no user can call it", which is a different and more
interesting finding than absence.

Scope
-----
Python and JavaScript/TypeScript, matching the languages the other analysers
read (see docs/METRICS.md). Lexical, not a parse tree: a regex cannot tell a
definition inside dead code from a live one. It can tell a definition from a
word in a comment, which is the error being corrected here.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# ---------------------------------------------------------------- definitions

SURFACE_KINDS = frozenset({"command", "route"})


@dataclass(frozen=True)
class Definition:
    """One thing the codebase declares."""
    name: str          # as written
    kind: str          # command | route | function | class | export
    file: str
    line: int
    method: str = ""   # routes only: GET, POST, ...

    @property
    def where(self) -> str:
        return f"{self.file}:{self.line}"

    @property
    def is_surface(self) -> bool:
        return self.kind in SURFACE_KINDS

    def describe(self) -> str:
        if self.kind == "command":
            return f'subcommand "{self.name}"'
        if self.kind == "route":
            return f"route {self.method} {self.name}".replace("  ", " ")
        return f"{self.kind} {self.name}"


# --------------------------------------------------------------- the patterns
#
# Each entry is (kind, compiled pattern). Group 1 is the name. Patterns are
# applied per file so a line number can be recovered from the match offset.

_PY_PATTERNS = [
    # Registered subcommands, which are surface: a user can type them.
    ("command", re.compile(r"""add_parser\(\s*["']([a-zA-Z_][\w\-]*)["']""")),
    ("command", re.compile(r"""@\w+\.command\(\s*["']([a-zA-Z_][\w\-]*)["']""")),
    # @click.command() with the name taken from the function beneath it.
    ("command", re.compile(
        r"""@\w+\.command\(\s*\)\s*(?:\n\s*@[^\n]+)*\s*\n\s*def\s+([a-zA-Z_]\w*)""")),
    # Typer: @app.command() def name(...)
    ("route", re.compile(
        r"""@\w+\.(get|post|put|delete|patch)\(\s*["']([^"']+)["']""", re.I)),
    ("function", re.compile(r"""^[ \t]*(?:async[ \t]+)?def[ \t]+([a-zA-Z_]\w*)""", re.M)),
    ("class", re.compile(r"""^[ \t]*class[ \t]+([A-Za-z_]\w*)""", re.M)),
]

_JS_PATTERNS = [
    ("route", re.compile(
        r"""\b(?:app|router|api|server)\.(get|post|put|delete|patch)\(\s*["'`]([^"'`]+)""",
        re.I)),
    # Commander / yargs style registered commands.
    ("command", re.compile(r"""\.command\(\s*["'`]([a-zA-Z_][\w\-]*)""")),
    ("function", re.compile(
        r"""^[ \t]*(?:export[ \t]+)?(?:default[ \t]+)?(?:async[ \t]+)?function[ \t]*\*?[ \t]*([a-zA-Z_$][\w$]*)""",
        re.M)),
    ("class", re.compile(r"""^[ \t]*(?:export[ \t]+)?class[ \t]+([A-Za-z_$][\w$]*)""", re.M)),
    # const handler = (...) => and export const handler = ...
    ("export", re.compile(
        r"""^[ \t]*export[ \t]+(?:const|let|var)[ \t]+([a-zA-Z_$][\w$]*)""", re.M)),
    ("function", re.compile(
        r"""^[ \t]*(?:const|let|var)[ \t]+([a-zA-Z_$][\w$]*)[ \t]*=[ \t]*(?:async[ \t]*)?\([^)]*\)[ \t]*=>""",
        re.M)),
]

_PY_SUFFIXES = (".py",)
_JS_SUFFIXES = (".js", ".jsx", ".ts", ".tsx")


def _line_of(content: str, offset: int) -> int:
    return content.count("\n", 0, offset) + 1


def index(codebase: dict) -> list[Definition]:
    """Every definition in the codebase, with the file and line of each.

    Duplicates are kept: the same name defined in two files is two facts, and
    a verdict that cites one of them should cite the one it found.
    """
    out: list[Definition] = []
    for path, content in (codebase.get("files") or {}).items():
        if path.endswith(_PY_SUFFIXES):
            patterns = _PY_PATTERNS
        elif path.endswith(_JS_SUFFIXES):
            patterns = _JS_PATTERNS
        else:
            continue
        for kind, pattern in patterns:
            for match in pattern.finditer(content):
                # A route pattern captures its method first, then its path.
                if kind == "route" and match.re.groups == 2:
                    method, name = match.group(1).upper(), match.group(2)
                    at = match.start(2)
                else:
                    method, name = "", match.group(1)
                    at = match.start(1)
                if not name:
                    continue
                out.append(Definition(name=name, kind=kind, file=path,
                                      line=_line_of(content, at), method=method))
    return out


# ------------------------------------------------------------------- matching

_SPLIT = re.compile(r"[^a-zA-Z0-9]+")
_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")

# Verbs a generated name wraps a feature in. `handle_add`, `addCommand` and
# `cmd_add` are all the feature `add`, and refusing them would trade the old
# rule's over-crediting for under-crediting.
_AFFIXES = frozenset({
    "handle", "handler", "cmd", "command", "do", "run", "exec", "execute",
    "on", "get", "post", "put", "delete", "patch", "fn", "func", "main",
    "api", "route", "endpoint", "view", "controller", "service", "action",
})


def words(name: str) -> list[str]:
    """``handle_addItem`` -> ``['handle', 'add', 'item']``."""
    parts: list[str] = []
    for chunk in _SPLIT.split(name):
        if not chunk:
            continue
        parts += [p.lower() for p in _CAMEL.split(chunk) if p]
    return parts


def _inflect(token: str) -> set[str]:
    out = {token, f"{token}s"}
    if token.endswith("s"):
        out.add(token[:-1])
    return {t for t in out if len(t) > 1}


# Words that name where code lives rather than what it does. One of these on
# its own is never evidence that a feature was built: treating ``cli`` as
# evidence credited four features of an ``internal_tool_cli`` specification to
# a single ``def cli()`` group function.
_SCAFFOLD_WORDS = frozenset({
    "cli", "api", "app", "web", "http", "service", "server", "core", "main",
    "src", "lib", "ui", "client", "command", "commands", "module", "package",
    "system", "tool", "tools", "feature", "features", "project",
})


def feature_tokens(feature_id: str) -> tuple[set[str], set[str]]:
    """``(head, supporting)`` token sets for a feature id.

    Which segment of a dotted id carries the meaning depends on who wrote it.
    A hand-authored specification namespaces by surface, so ``cli.export`` is
    about ``export``, the last segment. An id derived from a sentence reads in
    English order, so ``add.item`` is about ``add``, the first. Picking either
    position by rule gets the other kind wrong, so the distinction is made on
    the word: a word naming where code lives is skipped, and the first
    remaining segment is the **head** -- the thing the feature actually asks
    to be done.

    Only the head constitutes evidence. The remaining segments support it but
    cannot stand in for it, because they are usually the object rather than
    the action: crediting any of them credited ``remove.item`` to a
    ``def add_item``, which is a different feature on the same noun.
    """
    parts = [p.lower() for p in feature_id.split(".") if p]
    meaningful = [p for p in parts if p not in _SCAFFOLD_WORDS] or parts
    if not meaningful:
        return set(), set()
    head = _inflect(meaningful[0])
    supporting: set[str] = set()
    for part in parts[1:] if meaningful[0] == parts[0] else meaningful[1:]:
        supporting |= _inflect(part)
    return head, supporting - head


# What a feature's verb implies about the HTTP method that would implement it.
# Without this, "submit a claim" and "look up a claim" both matched the first
# route whose path contained "claim", so two features cited one line and the
# second was credited to code that does something else.
_VERB_METHOD = {
    "POST":   {"submit", "create", "add", "register", "send", "post", "open", "raise", "file"},
    "GET":    {"get", "look", "view", "show", "read", "fetch", "list", "search", "find", "browse"},
    "PUT":    {"update", "edit", "change", "replace", "set", "modify"},
    "PATCH":  {"update", "edit", "change", "patch", "modify"},
    "DELETE": {"delete", "remove", "purge", "cancel", "close", "archive"},
}


def _method_allows(method: str, head: set[str]) -> bool:
    """True unless the feature's verb clearly implies a different method."""
    if not method:
        return True
    implied = {m for m, verbs in _VERB_METHOD.items() if head & verbs}
    return not implied or method in implied


def matches(definition: Definition, feature_id: str) -> bool:
    """True when this definition declares the thing the feature asks for.

    The test is on the *words of a declared name*, not on a substring being
    present somewhere in the file. ``def extract`` does not match
    ``cli.export``; ``def export_csv`` and ``@cli.command("export")`` do.

    Routes are the one place a namespace alone counts. REST puts the action in
    the HTTP method and the noun in the path, so ``GET /courses`` is how a
    service implements ``course.list`` and there is no ``list`` to find.
    """
    head, supporting = feature_tokens(feature_id)
    if not head:
        return False

    if definition.kind == "route":
        # REST puts the action in the HTTP method and the noun in the path, so
        # `GET /courses` is how a service implements `course.list` and there is
        # no `list` to find. A path segment matching either set counts.
        if not _method_allows(definition.method, head):
            return False
        segments = {s.lower() for s in _SPLIT.split(definition.name) if s}
        return bool(segments & (head | supporting))

    name_words = words(definition.name)
    if not name_words:
        return False
    if "".join(name_words) in head:
        return True
    meaningful = [w for w in name_words if w not in _AFFIXES] or name_words
    return bool(head & set(meaningful))
