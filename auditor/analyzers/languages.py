"""Which files an analyser can read, and how much of the codebase that is.

Every metric in this instrument was originally Python-only. On the study's own
captures that meant scoring roughly forty per cent of what the agents wrote and
reporting the result as though it covered all of it, which is how a
TypeScript-dominated project came to score 0.00 for security (Erratum 001,
section 5.2). Analysers now declare what they could read, so a reading over a
fraction of a codebase is visibly that.
"""
from __future__ import annotations

PYTHON = (".py",)
TYPESCRIPT = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")

# Everything an analyser might reasonably be asked to treat as source. Config,
# documentation and lockfiles are excluded: counting them as unscanned source
# would understate coverage as unfairly as ignoring them overstates it.
SOURCE = PYTHON + TYPESCRIPT + (
    ".go", ".rb", ".java", ".kt", ".rs", ".php", ".cs", ".swift", ".scala",
)

VENDOR = (
    "node_modules/", "/.venv/", "venv/", "site-packages/", "dist/", "build/",
    "__pycache__/", ".git/", "vendor/", ".next/", "coverage/", "generated/",
)


def is_source(path: str) -> bool:
    if any(v in f"/{path}" for v in VENDOR):
        return False
    return path.endswith(SOURCE)


def in_languages(path: str, suffixes: tuple[str, ...]) -> bool:
    return is_source(path) and path.endswith(suffixes)


def line_counts(files: dict[str, str], suffixes: tuple[str, ...]) -> tuple[int, int]:
    """Return (lines an analyser for these languages can read, total source lines)."""
    scanned = total = 0
    for path, content in files.items():
        if not is_source(path):
            continue
        n = len(content.splitlines())
        total += n
        if path.endswith(suffixes):
            scanned += n
    return scanned, total


def present(files: dict[str, str]) -> list[str]:
    """Language families actually present, for reporting."""
    out = []
    if any(in_languages(p, PYTHON) for p in files):
        out.append("python")
    if any(in_languages(p, TYPESCRIPT) for p in files):
        out.append("javascript/typescript")
    other = sorted({
        p.rsplit(".", 1)[-1] for p in files
        if is_source(p) and not p.endswith(PYTHON + TYPESCRIPT)
    })
    out += other
    return out
