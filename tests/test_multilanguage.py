"""Multi-language analysis, and the guarantee that version 1 still reproduces.

The published study was scored by Python-only analysers. Adding JavaScript and
TypeScript support is only safe if the old behaviour remains addressable, so
every test here pins both: what version 2 now sees, and that version 1 sees
exactly what it always did.
"""
from auditor.analyzers import (complexity_analyzer, js_complexity, js_security,
                               languages, security_analyzer)


# ----------------------------------------------------------------- coverage
def test_coverage_reports_the_share_of_source_a_metric_could_read():
    files = {"a.py": "x = 1\n" * 40, "b.ts": "const x = 1;\n" * 60}
    scanned, total = languages.line_counts(files, languages.PYTHON)
    assert (scanned, total) == (40, 100)


def test_vendor_directories_are_not_counted_as_source():
    files = {"node_modules/dep/index.js": "x\n" * 500, "src/app.ts": "y\n" * 10}
    _, total = languages.line_counts(files, languages.TYPESCRIPT)
    assert total == 10


def test_a_partial_reading_is_flagged_as_partial():
    cb = {"files": {"a.py": "x = 1\n", "b.ts": "const x = 1;\n" * 20}}
    m = security_analyzer.analyze(cb, [], {}, version=1)
    assert m.is_partial, "python-only over a TS codebase must not look complete"
    m2 = security_analyzer.analyze(cb, [], {}, version=2)
    assert not m2.is_partial


# ----------------------------------------------------------------- security
def test_javascript_findings_carry_a_cwe():
    found = js_security.scan("app.ts", 'const API_KEY = "sk-live-abcdefghij";\n')
    assert found and found[0]["issue_cwe"]["id"] == "798"


def test_an_ambiguous_name_is_not_flagged():
    """A governance metric must not be inflated by guesses. `KEY` alone could be
    anything; only names that say what they hold are counted."""
    assert js_security.scan("app.ts", 'const KEY = "abcdefghij";\n') == []


def test_comments_are_not_scanned():
    assert js_security.scan("a.ts", "// eval(x)\n") == []


def test_version_one_ignores_typescript_entirely():
    cb = {"files": {"a.py": "x = 1\n", "evil.ts": "eval(payload);\n"}}
    assert security_analyzer.analyze(cb, [], {}, version=1).value == 0.0
    assert security_analyzer.analyze(cb, [], {}, version=2).value > 0


# --------------------------------------------------------------- complexity
def test_control_flow_blocks_are_not_counted_as_functions():
    src = "function f(a) { if (a) { return 1; } return 0; }"
    assert js_complexity.complexities(src) == [2]


def test_nested_functions_are_scored_separately():
    src = "function outer() { const g = (y) => { if (y) { return 1; } }; }"
    assert sorted(js_complexity.complexities(src)) == [1, 2]


def test_keywords_inside_strings_and_comments_do_not_count():
    src = '// if for while\nconst s = "if for while";\nfunction q() { return 1; }'
    assert js_complexity.complexities(src) == [1]


def test_typescript_complexity_is_scored_only_from_version_two():
    cb = {"files": {"a.ts": "function f(x) { if (x) { return 1; } return 0; }\n"}}
    assert complexity_analyzer.analyze(cb, [], {}, version=1).value == 0.0
    assert complexity_analyzer.analyze(cb, [], {}, version=2).value == 2.0
