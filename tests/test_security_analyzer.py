"""Security analyzer — local Bandit scan of the captured codebase."""
import pytest

from auditor.analyzers import security_analyzer


def test_returns_metric_score_per_kloc():
    """A clean codebase yields zero density; the contract shape is fixed."""
    codebase = {"files": {"safe.py": "def add(a, b):\n    return a + b\n"},
                "manifest": []}
    score = security_analyzer.analyze(codebase, [], {"name": "x"})
    assert score.name == "security_density"
    assert score.unit == "per_kloc"
    assert score.value == pytest.approx(0.0)


def test_detects_known_cwe_pattern():
    """A trivial CWE pattern (use of `assert` in non-test code = B101)
    should be flagged by Bandit and reflected in density > 0."""
    codebase = {"files": {"bad.py": "import subprocess\nsubprocess.call('ls', shell=True)\n"},
                "manifest": []}
    score = security_analyzer.analyze(codebase, [], {"name": "x"})
    assert score.value > 0, "expected Bandit to flag shell=True (CWE-78)"


def test_empty_codebase_yields_zero():
    score = security_analyzer.analyze({"files": {}, "manifest": []}, [], {"name": "x"})
    assert score.value == 0.0


def test_non_python_files_are_ignored():
    """Bandit only scans Python; YAML/MD should not throw."""
    codebase = {"files": {"README.md": "# title\n", "spec.yaml": "name: x\n"},
                "manifest": []}
    score = security_analyzer.analyze(codebase, [], {"name": "x"})
    assert score.value == 0.0


def _large_file_with(line: str) -> str:
    """Four hundred harmless lines and one line of interest."""
    return "import urllib.request\n" + "\n".join(f"x{i} = {i}" for i in range(400)) + f"\n{line}\n"


def test_serious_findings_are_named_whatever_the_density():
    """One serious finding in a large file stays far below the density warning,
    so it is named instead. From a field audit (docs/FIELD_REPORT_001.md)."""
    codebase = {"files": {"svc/opener.py": _large_file_with("urllib.request.urlopen(url)")},
                "manifest": []}
    score = security_analyzer.analyze(codebase, [], {"name": "x"})
    assert score.value < 50, "the density alone reads OK"
    assert score.details, "a medium-severity finding must be named"
    assert "1 medium" in score.details[0]
    assert any("MEDIUM B310" in d and "svc/opener.py:402" in d for d in score.details[1:])


def test_low_severity_findings_name_nothing():
    """Only medium and high findings are listed; lows stay in the density."""
    codebase = {"files": {"a.py": "import subprocess\n"}, "manifest": []}
    score = security_analyzer.analyze(codebase, [], {"name": "x"})
    assert score.value > 0
    assert score.details is None
