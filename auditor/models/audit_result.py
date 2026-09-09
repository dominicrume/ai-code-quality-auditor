"""Data shapes for audit results. Pydantic = validated, serialisable, testable."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class MetricScore(BaseModel):
    """One metric's reading, and how much of the codebase it could see.

    A density computed over 6% of a project is not the same claim as one
    computed over 100% of it, and reporting them identically is how a tool
    turns "I could not read your code" into "your code is clean". Every
    analyser therefore declares its own coverage.
    """

    name: str
    value: float
    unit: str = ""
    details: list[str] | None = None

    # Lines the analyser could evaluate, and lines of source it was given.
    scanned_lines: int | None = None
    total_lines: int | None = None
    languages: list[str] | None = None

    @property
    def coverage(self) -> float | None:
        """Fraction of source lines this metric was able to evaluate."""
        if not self.total_lines:
            return None
        return round((self.scanned_lines or 0) / self.total_lines, 4)

    @property
    def is_partial(self) -> bool:
        """True when the reading rests on less than most of the codebase."""
        c = self.coverage
        return c is not None and c < 0.5


CONDITIONS = Literal[
    "human_control",  # baseline
    "claude_code",    # Anthropic
    "cursor_agent",   # Cursor
    "antigravity",    # Google Gemini
    "replit_agent",   # Replit
]


class AuditResult(BaseModel):
    run_id: str
    condition: CONDITIONS  # type: ignore[valid-type]
    spec_name: str
    spec_version: str
    metrics: list[MetricScore]
    timestamp: datetime
