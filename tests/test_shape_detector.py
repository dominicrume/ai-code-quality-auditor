"""Tests for architectural-shape detection.

The cases are written from the protocol, not fitted to the rater labels. Two
of them reproduce behaviour observed in the run_001 captures; those are marked
as smoke tests rather than validation, for the reason given in
docs/KAPPA_RESULTS_001.md.
"""
from auditor.analyzers.shape_detector import (
    CLI,
    DATA_PIPELINE,
    UNKNOWN,
    WEB_SERVICE,
    classify_surface,
    detect_shape,
    shape_mismatch,
    specified_shape,
)

CLI_SPEC = {
    "name": "internal_tool_cli",
    "features": [
        {"id": "cli.init", "description": "`tool init <name>` creates a project."},
        {"id": "cli.add", "description": "`tool add <key> <value>` appends a pair."},
    ],
}

WEB_SPEC = {
    "name": "agent_education_system",
    "features": [
        {"id": "auth.login", "description": "Student can log in and receive a session token."},
        {"id": "course.list", "description": "Authenticated user can list available courses."},
    ],
}

PIPELINE_SPEC = {
    "name": "data_pipeline",
    "features": [
        {"id": "pipeline.ingest", "description": "Read a CSV from disk."},
        {"id": "pipeline.load", "description": "Write rows to SQLite."},
    ],
}


# --- what the brief asks for -------------------------------------------------

def test_cli_spec_is_read_as_cli():
    assert specified_shape(CLI_SPEC) == CLI


def test_web_spec_is_read_as_web_service_without_the_word_web():
    # The brief never says "web" or "endpoint"; it says a user logs in and
    # lists things. Session-scoped actions for named actors describe a service.
    assert specified_shape(WEB_SPEC) == WEB_SERVICE


def test_pipeline_spec_is_read_as_pipeline():
    assert specified_shape(PIPELINE_SPEC) == DATA_PIPELINE


def test_an_unclassifiable_brief_abstains():
    assert specified_shape({"name": "x", "features": [{"id": "a.b", "description": "do a thing"}]}) == UNKNOWN


# --- what was actually built -------------------------------------------------

def test_argparse_subcommands_read_as_cli():
    code = {"files": {"tool.py": (
        "import argparse\n"
        "p = argparse.ArgumentParser()\n"
        "subs = p.add_subparsers()\n"
        "subs.add_parser('init')\n"
        "subs.add_parser('add')\n"
    )}}
    assert detect_shape(code).shape == CLI


def test_express_routes_read_as_web_service():
    code = {"files": {"server.ts": (
        "const app = express()\n"
        "app.get('/courses', handler)\n"
        "app.post('/auth/login', handler)\n"
        "app.listen(3000)\n"
    )}}
    assert detect_shape(code).shape == WEB_SERVICE


def test_etl_package_reads_as_pipeline():
    code = {"files": {
        "pipeline/ingest.py": "def ingest(path):\n    return []\n",
        "pipeline/load.py": "def load(rows):\n    pass\n",
        "runner.py": "def run_pipeline():\n    pass\n",
    }}
    assert detect_shape(code).shape == DATA_PIPELINE


def test_an_empty_codebase_is_unknown_not_a_guess():
    assert detect_shape({"files": {}}).shape == UNKNOWN


def test_packaging_files_alone_do_not_decide_a_shape():
    # A requirements.txt naming a web framework is not a web service.
    code = {"files": {"requirements.txt": "fastapi\nuvicorn\n", "README.md": "# app"}}
    assert detect_shape(code).shape == UNKNOWN


# --- the comparison ----------------------------------------------------------

def test_matching_shapes_are_not_a_mismatch():
    code = {"files": {"tool.py": "import argparse\nsubs.add_parser('init')\n"}}
    assert shape_mismatch(CLI_SPEC, code)["mismatch"] is False


def test_cli_brief_answered_with_a_pipeline_is_a_mismatch():
    """Smoke test reproducing the run_001 replit_agent x internal_tool_cli
    behaviour. Not validation — this capture motivated the work."""
    code = {"files": {
        "pipeline/ingest.py": "def ingest(p):\n    return []\n",
        "pipeline/load.py": "def load(rows):\n    pass\n",
        "pipeline/runner.py": "def run_pipeline():\n    pass\n",
        "pipeline/scheduler.py": "import schedule\nschedule.every().day\n",
    }}
    out = shape_mismatch(CLI_SPEC, code)
    assert out["mismatch"] is True
    assert out["specified_shape"] == CLI
    assert out["built_shape"] == DATA_PIPELINE
    assert out["evidence"]


def test_a_substitution_with_no_extra_surface_is_still_caught():
    """The case the hallucination count cannot see.

    An agent that ships the wrong artefact and adds nothing scores zero
    off-specification features, because it did not add — it replaced. Shape
    detection is what separates that from genuine compliance.
    """
    code = {"files": {
        "pipeline.py": "def run_pipeline():\n    pass\n",
        "scheduler.py": "import schedule\nschedule.every().hour\n",
    }}
    out = shape_mismatch(CLI_SPEC, code)
    assert out["mismatch"] is True


def test_an_unresolved_verdict_is_reported_not_forced():
    # One weak signal each way: the detector should decline to call it.
    code = {"files": {"m.py": "import sys\nprint(sys.argv)\n"}}
    out = shape_mismatch(CLI_SPEC, code)
    assert out["confident"] is False
    assert out["mismatch"] is False


# --- the item_16 boundary ----------------------------------------------------

def test_capability_and_scaffolding_are_reported_separately():
    """The κ study found raters split on whether shipped scaffolding counts.

    The protocol does not settle it, so neither does this: both sides are
    surfaced and the caller declares which it counts.
    """
    code = {"files": {
        "pipeline/ingest.py": "def ingest(): pass",
        "lib/api-client-react/index.ts": "export function useHealthCheck() {}",
        "lib/db/pool.ts": "export const pool = createPool()",
        "package.json": "{}",
    }}
    out = classify_surface(code)
    assert "pipeline/ingest.py" in out["capability"]
    assert "lib/db/pool.ts" in out["scaffolding"]
    assert "lib/api-client-react/index.ts" in out["scaffolding"]
    # Packaging is neither.
    assert "package.json" not in out["capability"] + out["scaffolding"]
