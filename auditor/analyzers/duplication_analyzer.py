"""Code duplication — k-line shingle detection.

See docs/METRICS.md: % of source lines appearing inside a duplicated
6-line shingle (whitespace-normalised, blank lines removed). No parser and
no external tool required, so it reads every language the loader ingests.

Which files count:
  The loader ingests documentation and configuration alongside code, and
  because this metric needs no parser it measured all of it. On this
  instrument's own repository that meant 41,116 lines of Markdown against
  12,431 of Python: the reported figure was three-quarters a statement about
  prose. Repeated prose in a changelog or a methodology appendix is not
  duplicated code, and a reading called "Duplication" on a code audit is
  taken to mean code.
  Version 2 therefore counts code files only. Version 1 is retained so the
  study's published figures remain reproducible: ``analyze(..., version=1)``
  returns exactly what data/reports/main_001.csv records.
"""
from __future__ import annotations

from collections import defaultdict

from auditor.models.audit_result import MetricScore

SHINGLE_K = 6

# 1 = every ingested file, the analyser the published study ran with.
# 2 = code only. Default for new audits.
DEFAULT_VERSION = 2

# Suffixes this metric treats as code. Documentation and configuration are
# ingested by the loader for other purposes and are not counted here.
CODE_ONLY: frozenset[str] = frozenset({
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".rb", ".sql",
})


def _is_code(path: str) -> bool:
    return any(path.endswith(s) for s in CODE_ONLY)


def _normalise(content: str) -> list[tuple[int, str]]:
    """Return [(original_index, stripped_line), ...] for non-blank lines."""
    out: list[tuple[int, str]] = []
    for idx, raw in enumerate(content.splitlines()):
        s = " ".join(raw.split())  # collapse all whitespace runs
        if s:
            out.append((idx, s))
    return out


def analyze(codebase: dict, interaction_log: list[dict], spec: dict,
            version: int = DEFAULT_VERSION) -> MetricScore:
    # File -> list of (line_index, normalised_line)
    per_file: dict[str, list[tuple[int, str]]] = {
        path: _normalise(content)
        for path, content in codebase.get("files", {}).items()
        if version < 2 or _is_code(path)
    }
    total_lines = sum(len(v) for v in per_file.values())
    if total_lines == 0:
        return MetricScore(name="duplication_pct", value=0.0, unit="%")

    # Build a global shingle index: tuple_of_lines -> list of (file, start_idx)
    shingles: dict[tuple[str, ...], list[tuple[str, int]]] = defaultdict(list)
    for path, norm in per_file.items():
        if len(norm) < SHINGLE_K:
            continue
        for i in range(len(norm) - SHINGLE_K + 1):
            key = tuple(line for _, line in norm[i:i + SHINGLE_K])
            shingles[key].append((path, i))

    # Mark every line that participates in a shingle with >=2 occurrences.
    duplicated: set[tuple[str, int]] = set()
    for key, occurrences in shingles.items():
        if len(occurrences) < 2:
            continue
        for path, start in occurrences:
            norm = per_file[path]
            for offset in range(SHINGLE_K):
                duplicated.add((path, norm[start + offset][0]))

    pct = 100.0 * len(duplicated) / total_lines
    # Shingling needs no parser, so every non-blank line was read. Reporting
    # that explicitly keeps duplication from being the one metric with no
    # coverage figure beside the others.
    return MetricScore(name="duplication_pct", value=pct, unit="%",
                       scanned_lines=total_lines, total_lines=total_lines,
                       count=len(duplicated))
