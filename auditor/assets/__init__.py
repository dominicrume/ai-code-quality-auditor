"""Assets shared by every web surface.

The dashboard and the live page are separate Flask applications, and the
stylesheet used to live inside one of them. That made the other one's design a
copy, which is how the two surfaces drifted into different looks for the same
verdicts in the first place. There is one file, it lives here, and both
applications serve it from this package rather than from their own.
"""
from __future__ import annotations

from pathlib import Path

DIR = Path(__file__).resolve().parent
THEME = DIR / "theme.css"


def theme_css() -> str:
    """The one stylesheet, read from the installed package."""
    return THEME.read_text(encoding="utf-8")
