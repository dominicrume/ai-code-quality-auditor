"""Build the tick-box labelling tool.

Design rule: the rater supplies judgement, never archaeology. Every candidate
a user might be able to invoke is extracted mechanically and presented one at
a time as a single yes/no. 258 clicks replaces ~21,800 lines of reading.

Extraction is deliberately over-inclusive and deliberately independent of
manifest_deriver -- validating a heuristic with its own extractor would
conceal exactly the blind spots kappa exists to expose.
"""
from __future__ import annotations

import csv, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACK = ROOT / "data" / "labels" / "pack"

# Scanned over whole-file text, not line by line: argparse and route calls
# routinely put the name on the line after the open paren, and a line-scanner
# silently misses every one of them.
ROUTE = re.compile(r'@\w+\.(get|post|put|patch|delete|route)\(\s*[\'"]([^\'"]+)', re.I)
JSROUTE = re.compile(r'\b(?:app|router|api)\.(get|post|put|patch|delete)\(\s*[\'"`]([^\'"`]+)', re.I)
ADDPARSER = re.compile(r'add_parser\(\s*[\'"]([a-zA-Z_][\w\-]*)[\'"]')
CLICKCMD = re.compile(r'@\w+\.command\(\s*[\'"]([a-zA-Z_][\w\-]*)[\'"]')
CLICKBARE = re.compile(r'@\w+\.command\(\s*\)\s*(?:\n\s*@[^\n]+)*\s*\n\s*def\s+([a-zA-Z_]\w*)')
PYDEF = re.compile(r'^(?:async )?def ([a-zA-Z]\w*)\s*\(')
PYCLASS = re.compile(r'^class ([A-Z]\w*)')
JSEXPORT = re.compile(r'^export (?:async )?function (\w+)|^export const (\w+)\s*=')

NOISE = {"main", "cli", "app", "__init__", "setup", "teardown"}
CODE_EXT = (".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rb", ".java")

KIND_LABEL = {"route": "HTTP route", "command": "CLI subcommand",
              "function": "function / class"}


def candidates(files: dict) -> list[dict]:
    out, seen = [], set()

    def add(kind, name, where, snippet):
        key = (kind, name)
        if not name or name in NOISE or key in seen:
            return
        seen.add(key)
        out.append({"kind": kind, "name": name, "where": where,
                    "snippet": snippet.strip()[:140]})

    for path, content in sorted(files.items()):
        low = path.lower()
        is_test = "test" in low or "spec." in low
        if not path.endswith(CODE_EXT):
            continue
        lines = content.splitlines()

        def at(pos: int) -> tuple[str, str]:
            """Map a whole-file match offset back to a citable line."""
            n = content.count("\n", 0, pos) + 1
            return f"{path}:{n}", lines[n - 1] if n <= len(lines) else ""

        for rx, kind in ((ROUTE, "route"), (JSROUTE, "route"),
                         (ADDPARSER, "command"), (CLICKCMD, "command"),
                         (CLICKBARE, "command")):
            for m in rx.finditer(content):
                loc, src = at(m.start())
                if kind == "route":
                    add("route", f"{m.group(1).upper()} {m.group(2)}", loc, src)
                else:
                    add("command", m.group(1), loc, src)

        if is_test:
            continue
        for n, line in enumerate(lines, 1):
            stripped = line.lstrip()
            if len(line) - len(stripped) > 0:       # module level only
                continue
            loc = f"{path}:{n}"
            m = PYDEF.match(stripped) or PYCLASS.match(stripped)
            if m and not m.group(1).startswith("_"):
                add("function", m.group(1), loc, line); continue
            m = JSEXPORT.match(stripped)
            if m:
                add("function", m.group(1) or m.group(2), loc, line)

    order = {"route": 0, "command": 1, "function": 2}
    return sorted(out, key=lambda c: (order[c["kind"]], c["name"].lower()))


SPEC_BULLET = re.compile(r'^- \*\*`([^`]+)`\*\* — (.*)$')


def spec_features(item_id: str) -> list[dict]:
    """Read the asked-for list straight out of the pack item."""
    md = (PACK / f"{item_id}.md").read_text()
    feats, inside = [], False
    for line in md.splitlines():
        if line.startswith("These are the ONLY features"):
            inside = True
            continue
        if inside:
            if line.startswith("---"):
                break
            m = SPEC_BULLET.match(line.strip())
            if m:
                feats.append({"id": m.group(1), "desc": m.group(2)})
    return feats


def group(cands: list[dict], files: dict) -> list[dict]:
    """Collapse candidates into the rows a rater actually judges.

    Routes and subcommands stay individual -- each is separately invocable.
    Everything else is grouped by the file it lives in, because the protocol
    counts a feature once however many files it spans, and a module is the
    smallest honest unit of "a capability".
    """
    rows = []
    for c in cands:
        if c["kind"] in ("route", "command"):
            # The source fragment reads as noise here; the location is what a
            # rater would use to go and look.
            rows.append({"kind": c["kind"], "name": c["name"],
                         "where": c["where"], "detail": c["where"]})

    mods: dict[str, list[str]] = {}
    for c in cands:
        if c["kind"] == "function":
            mods.setdefault(c["where"].rsplit(":", 1)[0], []).append(c["name"])
    for path, names in sorted(mods.items()):
        rows.append({
            "kind": "module",
            "name": path,
            "where": f"{len(files.get(path, '').splitlines())} lines",
            "detail": "defines " + ", ".join(sorted(names)),
        })
    return rows


def build() -> list[dict]:
    idx = list(csv.DictReader(open(PACK / "index.csv")))
    sample = {r["run_id"]: r
              for r in csv.DictReader(open(ROOT / "data/labels/hallucination_handlabels.csv"))}
    items = []
    for e in idx:
        run = e["run_ids"].split(";")[0]
        cb = Path(sample[run]["code_path"]).parent / "codebase.json"
        files = json.loads(cb.read_text()).get("files", {}) if cb.exists() else {}
        items.append({
            "id": e["item_id"],
            "spec_name": e["spec_name"],
            "n_files": len(files),
            "asked_for": spec_features(e["item_id"]),
            "rows": group(candidates(files), files),
            "files": {p: c for p, c in sorted(files.items())},
        })
    return items


def render(items: list[dict], rater: str, title: str) -> str:
    payload = json.dumps({"rater": rater, "items": items})
    # A captured file may contain a literal </script>; escaping '<' keeps the
    # embedded JSON from terminating the script tag early.
    payload = payload.replace("<", "\\u003c")
    tpl = (ROOT / "scripts" / "tick_labeller.html").read_text()
    return tpl.replace("__TITLE__", title).replace('"__DATA__"', payload)


if __name__ == "__main__":
    items = build()
    total = sum(len(i["rows"]) for i in items)
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "build"
    out_dir.mkdir(parents=True, exist_ok=True)
    for n in ("1", "2"):
        p = out_dir / f"rater{n}.html"
        p.write_text(render(items, n, f"Rater {n} Ticks"))
        print(f"wrote {p}")
    print(f"{len(items)} screens, {total} rows to scan")
