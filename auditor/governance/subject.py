"""Whether the thing in front of you is an agent, asked before it is graded.

FINDING_003: the constitution checker scored this repository -- an experimental
instrument with no agent, no ceiling and no runtime -- and returned PASS on all
five elements. Two causes, one fix.

The first was that a marker vocabulary finds itself. ``separation_of_duty``
passed on the string ``require_approval`` appearing in the checker's own list of
strings to search for. The second was that nothing asked whether the subject was
an agent at all, so a static site or a dissertation repository would be scored
against a standard for autonomous agents.

Both fall to the same change: **match identifiers, not text.** A marker inside a
string literal, a comment or a docstring is a mention; a marker that is the name
of something called, assigned, imported or passed is a use. This module parses
Python source and reports only the latter, which is why the checker can no
longer see its own vocabulary: those markers live in tuples of strings.

What remains honest about the limit: this reads Python. A subject whose agent
loop is in TypeScript is reported as unreadable rather than as absent, and
``coverage`` says how much of the subject was parsed. Silence is still never
evidence of absence.

An agent, for the purpose of a standard about autonomy, is two things at once:
something that calls a model, and some way for the result to act. A model call
with no action path is a chatbot and is out of scope; an action path with no
model is ordinary software. Neither is refused a verdict because it failed, but
because the question does not apply.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field

from auditor.core.evidence import MEASURED, WITHHELD
from auditor.core.logger import get_logger

log = get_logger("subject")

AGENT = "agent"
NOT_AN_AGENT = "not_an_agent"
UNREADABLE = "unreadable"

# Calling a model. Deliberately narrow: a provider SDK, or a call only a model
# client makes. The first cut of this list included "chat", "prompt", "llm" and
# "messages", and it classified this instrument as an agent -- those words are
# ordinary vocabulary in software that has never called a model. A gate that
# over-admits is worse than no gate, because it hands a verdict to a subject the
# standard does not cover.
# Matched against IMPORTS ONLY, and by exact part rather than substring. The
# second cut of this list matched identifiers, and `anthropic_api_key` sitting
# in a config dataclass was enough to classify this instrument as an agent.
# Holding a provider's key is not calling a provider.
_MODEL_IMPORTS = frozenset({
    "anthropic", "openai", "litellm", "langchain", "langgraph", "llama_index",
    "ollama", "mistralai", "cohere", "generativeai", "vertexai",
    "transformers", "boto3",
})

# Matched against used names: a call only a model client makes.
_MODEL_CALLS = (
    "chatcompletion", "invoke_model", "generate_content", "create_message",
    "chat_completion",
)

# A way for the result to act. Either a tool-calling surface, or a module that
# reaches the world. These stay broader than the model markers on purpose: they
# only ever matter in combination with one, so a generic hit alone decides
# nothing.
_ACTION_MARKERS = (
    "tool_calls", "tool_call", "tool_use", "toolcall", "register_tool",
    "function_call", "agentexecutor", "create_agent", "crewai", "autogen",
    "swarm", "run_tool", "dispatch_tool", "subprocess", "requests", "httpx",
)


@dataclass
class Subject:
    """What the subject is, and how much of it could be read."""

    kind: str
    grade: str
    coverage: float                 # share of files this module could parse
    model_evidence: list[str] = field(default_factory=list)
    action_evidence: list[str] = field(default_factory=list)
    unparsed: list[str] = field(default_factory=list)

    @property
    def is_agent(self) -> bool:
        return self.kind == AGENT

    @property
    def applicable(self) -> bool:
        """Whether a standard about autonomous agents applies to this subject."""
        return self.kind == AGENT

    @property
    def note(self) -> str:
        if self.kind == AGENT:
            seen = f"{self.model_evidence[0]}, {self.action_evidence[0]}"
            return f"Subject is an agent: it calls a model and can act ({seen})."
        if self.kind == UNREADABLE:
            return (
                "Could not read enough of this subject to say whether it is an "
                "agent. No Python source parsed, so a loop written in another "
                "language is invisible here. This is not a finding that no "
                "agent is present."
            )
        if self.model_evidence and not self.action_evidence:
            return (
                "Subject calls a model but no path was found by which its "
                "output acts. A standard about autonomy does not apply to "
                "something that only answers."
            )
        if self.action_evidence and not self.model_evidence:
            return (
                "Subject acts, but nothing was found calling a model. This is "
                "ordinary software, and the standard does not apply to it."
            )
        return (
            "No agent found in this subject: nothing calls a model and no tool "
            "or action path was found. The standard does not apply."
        )


def _imports(tree: ast.AST) -> set[str]:
    """Module parts actually imported, lowercased."""
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                out.update(part.lower() for part in a.name.split("."))
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.update(part.lower() for part in node.module.split("."))
    return out


def imports(codebase: dict) -> dict[str, set[str]]:
    """Per-file imported module parts, for markers that must be an import."""
    out: dict[str, set[str]] = {}
    for path, content in (codebase.get("files", {}) or {}).items():
        if not path.endswith(".py"):
            continue
        try:
            out[path] = _imports(ast.parse(content))
        except SyntaxError:
            continue
    return out


def _identifiers(source: str) -> set[str]:
    """Every name actually used, lowercased. Strings and comments contribute none.

    This is the whole fix for FINDING_003's first cause. ``"require_approval"``
    sitting in a tuple of search terms is a Constant and never reaches here;
    ``require_approval(action)`` is a Name and does.
    """
    tree = ast.parse(source)
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            out.add(node.id.lower())
        elif isinstance(node, ast.Attribute):
            out.add(node.attr.lower())
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(node.name.lower())
        elif isinstance(node, ast.keyword) and node.arg:
            out.add(node.arg.lower())
        elif isinstance(node, ast.arg):
            out.add(node.arg.lower())
        elif isinstance(node, ast.Import):
            for a in node.names:
                out.update(part.lower() for part in a.name.split("."))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                out.update(part.lower() for part in node.module.split("."))
            out.update(a.name.lower() for a in node.names)
    return out


def identifiers(codebase: dict) -> tuple[dict[str, set[str]], list[str]]:
    """Per-file identifier sets, plus the files that could not be parsed."""
    per_file: dict[str, set[str]] = {}
    unparsed: list[str] = []
    for path, content in (codebase.get("files", {}) or {}).items():
        if not path.endswith(".py"):
            continue
        try:
            per_file[path] = _identifiers(content)
        except SyntaxError as exc:
            log.warning("subject: could not parse %s (%s) -- excluded, never counted as empty", path, exc)
            unparsed.append(path)
    return per_file, unparsed


def used(per_file: dict[str, set[str]], markers: tuple[str, ...]) -> list[str]:
    """Where a marker is the name of something used, not a string that mentions it."""
    found: list[str] = []
    for path, names in per_file.items():
        for name in sorted(names):
            if any(m in name for m in markers):
                found.append(f"{path}: {name}")
                break
    return found


def classify(codebase: dict) -> Subject:
    """Decide whether a standard about autonomous agents applies at all."""
    per_file, unparsed = identifiers(codebase)
    total_py = len(per_file) + len(unparsed)
    coverage = (len(per_file) / total_py) if total_py else 0.0

    if not per_file:
        return Subject(kind=UNREADABLE, grade=WITHHELD, coverage=coverage,
                       unparsed=unparsed)

    model = [f"{path}: imports {name}"
             for path, mods in imports(codebase).items()
             for name in sorted(mods & _MODEL_IMPORTS)]
    model += used(per_file, _MODEL_CALLS)
    action = used(per_file, _ACTION_MARKERS)

    kind = AGENT if (model and action) else NOT_AN_AGENT
    return Subject(kind=kind, grade=MEASURED, coverage=coverage,
                   model_evidence=model[:4], action_evidence=action[:4],
                   unparsed=unparsed)
