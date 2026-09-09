"""CWE-tagged security patterns for JavaScript and TypeScript.

Bandit covers Python and nothing else, which left the majority of this study's
captured code unscanned. This is not a replacement for a full JS analyser; it is
a curated set of patterns for the weaknesses that actually appear in generated
web code, each mapped to the CWE the security metric already counts by, so a
finding here is the same kind of object as a finding from Bandit.

Rules are deliberately conservative. A false positive inflates a governance
metric, which is worse than a miss.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    id: str
    cwe: str
    severity: str
    pattern: re.Pattern[str]
    message: str


RULES: tuple[Rule, ...] = (
    Rule("JS101", "CWE-95", "HIGH",
         re.compile(r"\beval\s*\(|new\s+Function\s*\("),
         "Dynamic code execution from a string"),
    Rule("JS102", "CWE-79", "MEDIUM",
         re.compile(r"\.innerHTML\s*=|dangerouslySetInnerHTML"),
         "Markup assigned without escaping"),
    Rule("JS103", "CWE-78", "HIGH",
         re.compile(r"\b(exec|execSync)\s*\(\s*[`\"'][^`\"']*\$\{"),
         "Shell command built by interpolation"),
    Rule("JS104", "CWE-798", "HIGH",
         re.compile(r"""(?i)\b(api[_-]?key|secret|password|token)\s*[:=]\s*["'][^"']{8,}["']"""),
         "Credential literal in source"),
    Rule("JS105", "CWE-295", "HIGH",
         re.compile(r"rejectUnauthorized\s*:\s*false|NODE_TLS_REJECT_UNAUTHORIZED\s*=\s*['\"]?0"),
         "TLS certificate verification disabled"),
    Rule("JS106", "CWE-338", "MEDIUM",
         re.compile(r"Math\.random\s*\(\s*\)[^\n]{0,60}\b(token|secret|key|nonce|salt|id)\b",
                    re.I),
         "Non-cryptographic randomness used for a security value"),
    Rule("JS107", "CWE-319", "LOW",
         re.compile(r"""["']http://(?!localhost|127\.0\.0\.1|0\.0\.0\.0)"""),
         "Cleartext HTTP endpoint"),
    Rule("JS108", "CWE-89", "HIGH",
         re.compile(r"""(query|execute)\s*\(\s*[`"'][^`"']*(SELECT|INSERT|UPDATE|DELETE)"""
                    r"""[^`"']*\$\{""", re.I),
         "SQL built by interpolation"),
)

_COMMENT = re.compile(r"^\s*(//|/\*|\*)")


def scan(path: str, content: str) -> list[dict]:
    """Findings in one file, shaped like the Bandit results the metric counts."""
    out = []
    for n, line in enumerate(content.splitlines(), 1):
        if _COMMENT.match(line):
            continue
        for rule in RULES:
            if rule.pattern.search(line):
                out.append({
                    "test_id": rule.id,
                    "issue_cwe": {"id": rule.cwe.removeprefix("CWE-")},
                    "issue_severity": rule.severity,
                    "issue_text": rule.message,
                    "filename": path,
                    "line_number": n,
                })
    return out
