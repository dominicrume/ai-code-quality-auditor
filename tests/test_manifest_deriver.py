"""manifest_deriver — heuristic feature/hallucination detection from code."""
from auditor.analyzers.manifest_deriver import derive


SPEC = {"features": [
    {"id": "auth.register"}, {"id": "auth.login"},
    {"id": "course.list"},   {"id": "course.view"},
]}


def test_detects_implemented_features_via_two_segment_tokens():
    code = {"files": {"main.py": (
        "from fastapi import FastAPI\napp = FastAPI()\n"
        "@app.post('/auth/register')\ndef register(): pass\n"
        "@app.post('/auth/login')\ndef login(): pass\n"
        "@app.get('/courses')\ndef list_courses(): pass\n"
        "@app.get('/courses/{cid}')\ndef view_course(cid): pass\n"
    )}}
    result = derive(SPEC, code)
    assert set(result["implemented"]) == {"auth.register", "auth.login",
                                          "course.list", "course.view"}
    assert result["hallucinated_endpoints"] == []


def test_flags_off_spec_endpoint_as_hallucinated():
    code = {"files": {"main.py": (
        "from fastapi import FastAPI\napp = FastAPI()\n"
        "@app.get('/health')\ndef health(): pass\n"
        "@app.post('/auth/login')\ndef login(): pass\n"
    )}}
    result = derive(SPEC, code)
    assert "auth.login" in result["implemented"]
    assert "/health" in result["hallucinated_endpoints"]


def test_empty_codebase_yields_nothing():
    out = derive(SPEC, {"files": {}})
    # The three published keys are asserted exactly; `shape` and `surface` are
    # additive and asserted separately, so adding a signal never silently
    # changes what the hallucination metric reports.
    assert {k: out[k] for k in ("implemented", "hallucinated_endpoints", "hallucinated_commands")} == {
        "implemented": [],
        "hallucinated_endpoints": [],
        "hallucinated_commands": [],
    }
    assert out["shape"]["built_shape"] == "unknown"
    assert out["shape"]["mismatch"] is False
    assert out["surface"] == {"capability": [], "scaffolding": []}


def test_detects_argparse_subcommands():
    spec = {"features": [{"id": "cli.init"}, {"id": "cli.add"}, {"id": "cli.list"}]}
    code = {"files": {"main.py": (
        "import argparse\n"
        "p = argparse.ArgumentParser()\n"
        "sub = p.add_subparsers()\n"
        "sub.add_parser('init')\n"
        "sub.add_parser('add')\n"
        "sub.add_parser('list')\n"
        "sub.add_parser('schedule')\n"   # off-spec — should be flagged
    )}}
    result = derive(spec, code)
    assert "cli.init" in result["implemented"]
    assert "cli.add" in result["implemented"]
    assert "cli.list" in result["implemented"]
    assert "schedule" in result["hallucinated_commands"]


def test_detects_click_named_commands():
    spec = {"features": [{"id": "cli.add"}]}
    code = {"files": {"main.py": (
        "import click\n"
        "@click.group()\ndef cli(): pass\n"
        "@cli.command('add')\ndef _add(): pass\n"
        "@cli.command('run')\ndef _run(): pass\n"   # off-spec
    )}}
    result = derive(spec, code)
    assert "cli.add" in result["implemented"]
    assert "run" in result["hallucinated_commands"]


def test_express_routes_are_detected():
    """A TypeScript/Express service must not score zero by construction.

    Regression for the false negative found by the two-rater kappa validation:
    matching only Python decorator routes made every non-Python web capture
    unfalsifiable. See docs/KAPPA_RESULTS_001.md.
    """
    spec = {"features": [{"id": "course.list"}, {"id": "auth.login"}]}
    codebase = {"files": {"src/routes/courses.ts": (
        "router.get('/courses', listCourses);\n"
        "router.post('/auth/login', login);\n"
        "router.get('/healthz', health);\n"
    )}}
    out = derive(spec, codebase)
    assert "/healthz" in out["hallucinated_endpoints"]
    assert "/courses" not in out["hallucinated_endpoints"]
    assert "/auth/login" not in out["hallucinated_endpoints"]
