"""Turn a plain-English brief into a spec.

Scope drift is the metric that catches an agent building the wrong thing —
and it was gated behind hand-authoring YAML, which is why nobody reached it.

A user already knows what they asked the agent for; they typed it once
already. This converts that text into the spec, transparently and without
a model: one feature per line or bullet, slugged into an id. The result is
written to disk so it can be read, corrected, and version-controlled — it
is a starting point the user owns, not a hidden inference.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

_BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s*")
_NON_WORD = re.compile(r"[^a-z0-9]+")

# Words that carry no meaning in an identifier.
#
# The line to hold: a verb that tells *us* to produce software is filler
# ("build a course listing page" is about the page), while a verb naming an
# operation the software performs is the feature ("add an item" is about add,
# which is the subcommand somebody has to go and write). "add" and "create"
# were originally filler, which turned "add an item" into the id `item` and
# left the fidelity table nothing to match a subcommand against.
#
# Prepositions are kept out of this set on purpose: stripping "in" turned
# "log in" into `log`, and a phrasal verb loses its meaning without its
# particle.
_STOP = {
    "a", "an", "the", "and", "or", "to", "for", "of", "with", "that", "this",
    "can", "should", "must", "will", "be", "is", "are", "it", "user", "users",
    "able", "allow", "allows", "build", "builds", "make", "makes", "as",
    "support", "supports", "implement", "implements", "develop", "develops",
    "please", "want", "need", "would", "like",
    # The deliverable as a whole, naming itself. "The program must add two
    # numbers" is a requirement about `add`, and an id of `program.add.two`
    # puts a word the code never declares in the position the matcher tests
    # first, which reported a correct three-function script as 0 of 3
    # delivered. Same principle as "build" above: a word that refers to the
    # artefact is filler, and a word that names an operation is the feature.
    #
    # Deliberately not here: "page", "site", "report", "service", "dashboard".
    # Those name a thing somebody has to go and build, which is exactly what a
    # fidelity verdict is looking for. See FINDING_011.
    "program", "application", "app", "software", "script", "system",
    "project", "codebase",
}


def slugify(text: str, fallback: str) -> str:
    """"Users can log in with email" -> "log.in.email"."""
    words = [w for w in _NON_WORD.sub(" ", text.lower()).split() if w and w not in _STOP]
    return ".".join(words[:3]) if words else fallback


def parse_brief(brief: str) -> list[dict[str, str]]:
    """Split a brief into one feature per line or bullet."""
    features: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in brief.splitlines():
        line = _BULLET.sub("", raw).strip().rstrip(".;,")
        if len(line) < 3:
            continue
        base = slugify(line, f"feature.{len(features) + 1}")
        fid, n = base, 2
        while fid in seen:
            fid, n = f"{base}.{n}", n + 1
        seen.add(fid)
        features.append({"id": fid, "description": line})
    return features


def build_spec(brief: str, name: str = "live_session") -> dict:
    """A complete, valid spec derived from the brief."""
    return {
        "name": name,
        "version": "1.0.0",
        "_derived_from_brief": True,
        "features": parse_brief(brief),
        "governance": [
            {"rule": "no_secrets_in_source",
             "description": "No credentials, keys or tokens committed to the repo."},
        ],
        "allowlist": {"external_apis": []},
    }


def spec_path_for(project: Path) -> Path:
    return Path(project) / ".auditor" / "spec.yaml"


def save_spec(project: Path, spec: dict) -> Path:
    """Write the spec where the user can find and edit it.

    The header says where the content came from, because a specification the
    tool wrote for you and one you wrote yourself carry different authority
    and a reader a month later cannot tell them apart otherwise.
    """
    path = spec_path_for(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    origin = spec.get("_discovered_from")
    if origin:
        header = (
            f"# Derived automatically from {origin} when the audit first ran.\n"
            "# Nothing here was read from your source code: a specification\n"
            "# inferred from the code it measures would be satisfied by that\n"
            "# code by construction.\n"
            "# It is provisional. Correct it, and the audit follows.\n"
        )
    else:
        header = (
            "# Generated from the brief you gave.\n"
            "# This is yours to edit — it is the definition of 'what was asked for',\n"
            "# and every scope-drift finding is measured against it.\n"
        )
    path.write_text(header + yaml.safe_dump(spec, sort_keys=False))
    return path


def load_spec(project: Path) -> dict | None:
    """Any spec already present for this project."""
    path = spec_path_for(project)
    if path.exists():
        try:
            return yaml.safe_load(path.read_text())
        except yaml.YAMLError:
            return None
    return None


# Where a person writes their requirements when they are not writing our
# schema. See FINDING_011.
#
# A field report ran a scan with a hand-written `spec.yaml` whose sentences sat
# under `requirements:`. Nothing read them, so the fidelity table was omitted
# entirely, the scope-drift count printed 0.00 OK, and the footer still said
# "measured against spec.yaml". The user reasonably concluded the tool had
# confirmed the implementation matched the requirements. It had not checked a
# single one.
#
# These keys are read as a list of requirement sentences. The order is the
# order they are tried.
_FEATURE_KEYS = ("features", "requirements", "acceptance_criteria",
                 "user_stories", "stories", "must_have", "deliverables")


def _sentences(value) -> list[str]:
    """The requirement sentences in ``value``, if it holds any.

    A list of strings is a list of requirements. A list of dicts is already
    our own schema and is not touched here. Anything else is not a list of
    requirements, and guessing further is how a brief gets invented.
    """
    if not isinstance(value, list):
        return []
    lines = [str(v).strip() for v in value if isinstance(v, str) and str(v).strip()]
    return lines if len(lines) == len(value) else []


def normalise_spec(spec: dict | None) -> dict | None:
    """A supplied specification, with its features made readable.

    Why this is a measurement and not a guess, which is the whole distinction
    this instrument rests on: **a human wrote these sentences into this file.**
    FINDING_002 was about features invented from commit subjects, where the
    thing in doubt was the brief itself. Here the brief is not in doubt. It is
    in the wrong key, and reading somebody's own words out of the key they
    chose is parsing, not inference.

    Nothing is written back to disk and no sentence is altered. Only an ``id``
    is added, by the same slug that `parse_brief` has always used, so a
    feature keeps the user's wording in `description` and the matcher gets
    something stable to match on.

    When no key holds anything usable, the spec is returned with
    ``_no_features`` set to the list of keys that were tried, so a caller can
    say what was looked for instead of silently reporting nothing.
    """
    if not isinstance(spec, dict):
        return spec

    existing = spec.get("features")
    if isinstance(existing, list) and any(
            isinstance(f, dict) and f.get("id") for f in existing):
        return spec                                  # already our schema

    for key in _FEATURE_KEYS:
        lines = _sentences(spec.get(key))
        if not lines:
            continue
        out = dict(spec)
        out["features"] = parse_brief("\n".join(lines))
        if key != "features":
            # Recorded so the report can name the key, because a reader who
            # wrote `requirements:` needs to know that is what was measured.
            out["_features_from_key"] = key
        out.pop("_no_features", None)
        return out

    out = dict(spec)
    out["_no_features"] = list(_FEATURE_KEYS)
    return out
