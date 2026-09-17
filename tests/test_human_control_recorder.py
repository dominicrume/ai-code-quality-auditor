"""Recorder classifier — maps raw pynput keys to capture-contract event types.

Skipped wherever pynput cannot be imported, since the classifier's input
types come from the pynput module itself.

Deliberately not `pytest.importorskip("pynput")`. On a headless runner
pynput *is* installed and raises ImportError from inside its own package
because there is no X display, and since pytest 8.2 importorskip re-raises
an ImportError it did not itself cause — which aborted collection of the
entire suite. The condition we mean is "pynput will not load here",
whatever the reason for it.
"""
import pytest

try:
    import pynput
except ImportError as exc:                       # absent, or no display to attach to
    pytest.skip(f"pynput unavailable: {exc}", allow_module_level=True)

from auditor.adapters.human_control_recorder import _classify


def test_backspace_classified_as_backspace():
    assert _classify(pynput.keyboard.Key.backspace) == "backspace"


def test_delete_classified_as_delete():
    assert _classify(pynput.keyboard.Key.delete) == "delete"


def test_printable_char_classified_as_keystroke():
    # KeyCode.from_char is pynput's documented way to fabricate a printable key.
    assert _classify(pynput.keyboard.KeyCode.from_char("a")) == "keystroke"


def test_modifier_key_classified_as_keystroke():
    # Shift/ctrl/etc. count as typed actions in the capture contract.
    assert _classify(pynput.keyboard.Key.shift) == "keystroke"
