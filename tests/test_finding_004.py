"""FINDING_004: the fidelity path read its own detector vocabulary.

Each test here pins one of the three repairs the finding required, and each
fails on the code as it shipped in 0.6.3. Synthetic fixtures only.
"""
from __future__ import annotations

from auditor.analyzers import definitions as defs
from auditor.analyzers import fidelity
from auditor.analyzers.literals import mask_for


def _codebase(**files):
    return {"files": dict(files), "unreadable": []}


# ------------------------------------------------- 1. identifiers, not text

DOCUMENTED_BUT_NOT_BUILT = '''
"""A module that documents a detector.

It looks for routes written as @app.get("/orders") and for subcommands
registered as add_parser("export").
"""
import re

PATTERN = re.compile(r"""@\\w+\\.(get|post)\\(\\s*["\']([^"\']+)["\']""")
# @app.delete("/commented-out")
'''

REALLY_BUILT = '''
from fastapi import FastAPI
app = FastAPI()

@app.get("/orders")
def list_orders():
    return []
'''


def test_a_route_in_a_docstring_is_not_a_route():
    index = defs.index(_codebase(**{"detector.py": DOCUMENTED_BUT_NOT_BUILT}))
    assert [d.name for d in index if d.kind == "route"] == []
    assert [d.name for d in index if d.kind == "command"] == []


def test_a_route_in_a_comment_is_not_a_route():
    index = defs.index(_codebase(**{"detector.py": DOCUMENTED_BUT_NOT_BUILT}))
    assert "/commented-out" not in {d.name for d in index}


def test_a_real_route_is_still_found():
    """The mask must not cost us every route: a path IS written in a string."""
    index = defs.index(_codebase(**{"api.py": REALLY_BUILT}))
    routes = [d for d in index if d.kind == "route"]
    assert [(d.method, d.name) for d in routes] == [("GET", "/orders")]


def test_a_route_in_a_js_comment_is_not_a_route():
    js = '\n'.join([
        '// app.get("/docs-example")',
        '/* router.post("/block-comment") */',
        'const usage = `app.put("/template")`;',
        'app.get("/live", h);',
    ])
    index = defs.index(_codebase(**{"server.js": js}))
    assert [d.name for d in index if d.kind == "route"] == ["/live"]


def test_a_file_that_will_not_tokenise_is_still_masked():
    """A captured file with a syntax error still has docstrings in it."""
    broken = 'def ok(:\n    """registered via add_parser("ghost")"""\n'
    index = defs.index(_codebase(**{"broken.py": broken}))
    assert "ghost" not in {d.name for d in index}


def test_mask_leaves_code_between_f_string_braces_alone():
    src = 'x = f"see {helper()} here"\ndef helper():\n    pass\n'
    mask = mask_for("a.py", src)
    assert mask.covers(src.index("see"))
    assert not mask.covers(src.index("helper()"))


# ------------------------------------- 2. one feature, one piece of evidence

SPEC_TWO_AUTH = {
    "name": "portal",
    "features": [
        {"id": "auth.register", "description": "Users can register"},
        {"id": "auth.login", "description": "Users can log in"},
    ],
}

ONE_AUTH_ROUTE = '''
from fastapi import FastAPI
app = FastAPI()

@app.post("/auth/register")
def register(email, password):
    return {}
'''


def test_two_features_cannot_cite_one_line():
    report = fidelity.assess(SPEC_TWO_AUTH, _codebase(**{"api.py": ONE_AUTH_ROUTE}))
    cited = [v.where for v in report.verdicts if v.where]
    assert len(cited) == len(set(cited)), "one line was the evidence for two features"


def test_the_second_feature_is_withheld_not_credited():
    report = fidelity.assess(SPEC_TWO_AUTH, _codebase(**{"api.py": ONE_AUTH_ROUTE}))
    assert len(report.delivered) == 1
    assert len(report.ambiguous) == 1
    held = report.ambiguous[0]
    assert "already cited for" in held.reason()
    assert held.status not in (fidelity.DELIVERED, fidelity.NOT_FOUND)


def test_a_withheld_feature_is_neither_delivered_nor_missing():
    report = fidelity.assess(SPEC_TWO_AUTH, _codebase(**{"api.py": ONE_AUTH_ROUTE}))
    ids = {v.feature_id for v in report.delivered} | {v.feature_id for v in report.missing}
    assert "auth.login" not in ids
    assert report.completeness == 50.0
    assert "withheld" in report.headline


def test_supporting_words_choose_between_two_candidates():
    """`register` and `login` both match on `auth`; the suffix must decide."""
    both = ONE_AUTH_ROUTE + '''

@app.post("/auth/login")
def login(email, password):
    return {}
'''
    report = fidelity.assess(SPEC_TWO_AUTH, _codebase(**{"api.py": both}))
    by_id = {v.feature_id: v for v in report.verdicts}
    assert by_id["auth.register"].evidence == "route POST /auth/register"
    assert by_id["auth.login"].evidence == "route POST /auth/login"
    assert len(report.delivered) == 2


def test_a_feature_with_one_option_is_served_before_one_with_two():
    """Allocating in spec order starved the feature that had no alternative."""
    spec = {
        "name": "portal",
        "features": [
            {"id": "auth.login", "description": "Log in"},
            {"id": "auth.register", "description": "Register"},
        ],
    }
    code = '''
from fastapi import FastAPI
app = FastAPI()

@app.post("/auth/register")
def register():
    return {}
'''
    report = fidelity.assess(spec, _codebase(**{"api.py": code}))
    by_id = {v.feature_id: v for v in report.verdicts}
    assert by_id["auth.register"].status == fidelity.DELIVERED
    assert by_id["auth.login"].status == fidelity.AMBIGUOUS


# ------------------------------------------ 3. a contradiction is a defect

SPEC_CLAIMS = {
    "name": "claims",
    "features": [
        {"id": "submit.claim", "description": "Submit a claim"},
    ],
}

ONLY_A_GETTER = '''
from flask import Flask
app = Flask(__name__)

@app.get("/claims")
def read_claims():
    return []
'''


def test_missing_and_unrequested_cannot_both_be_reported():
    """`submit.claim` implies POST, so GET /claims does not credit it. The old
    reading then printed the feature as `not found` and the same route as
    `not asked for`, in one table, which cannot both be true."""
    report = fidelity.assess(SPEC_CLAIMS, _codebase(**{"api.py": ONLY_A_GETTER}))
    assert report.missing == []
    assert report.extras == []
    assert len(report.ambiguous) == 1
    reason = report.ambiguous[0].reason()
    assert "both cannot be true" in reason
    assert "/claims" in reason


def test_an_unrelated_extra_is_still_reported():
    """Withholding the contradiction must not silence genuine scope drift."""
    code = ONLY_A_GETTER + '''

@app.get("/weather")
def weather():
    return {}
'''
    report = fidelity.assess(SPEC_CLAIMS, _codebase(**{"api.py": code}))
    assert [e.name for e in report.extras] == ["/weather"]


def test_method_evidence_is_still_used_to_credit():
    """ignore_method is for detecting incoherence, never for crediting."""
    posting = ONLY_A_GETTER.replace("app.get", "app.post").replace("read_", "submit_")
    report = fidelity.assess(SPEC_CLAIMS, _codebase(**{"api.py": posting}))
    assert len(report.delivered) == 1
    assert report.ambiguous == []


# -------------------------------------------- the instrument on itself

def test_the_instrument_does_not_report_its_own_vocabulary():
    """The symptom in the finding, on the real files that produced it."""
    from pathlib import Path

    files = {}
    for name in ("auditor/analyzers/definitions.py",
                 "auditor/analyzers/manifest_deriver.py"):
        files[name] = Path(name).read_text(encoding="utf-8")
    index = defs.index(_codebase(**files))
    reported = {d.name for d in index if d.is_surface}
    assert reported & {"add", "export", "/path", "name"} == set()


# ----------------------------------------------- the readings leave the module

def test_json_output_explains_a_withheld_verdict(tmp_path):
    """A withheld verdict a consumer cannot explain is no better than a wrong
    one. The terminal table and the live page both carried the reason; JSON
    did not, which is the output an integration actually reads."""
    import json
    from click.testing import CliRunner
    from auditor.core.cli import main

    (tmp_path / "service.py").write_text(ONE_AUTH_ROUTE)
    (tmp_path / "spec.yaml").write_text(
        "name: Portal\n"
        "features:\n"
        "  - id: auth.register\n    description: Users can register\n"
        "  - id: auth.login\n    description: Users can log in\n"
    )
    res = CliRunner().invoke(main, ["scan", str(tmp_path), "--spec",
                                   str(tmp_path / "spec.yaml"), "--json"])
    assert res.exit_code == 0, res.output
    fid = json.loads(res.output)["fidelity"]
    assert fid["withheld"] == ["auth.login"]
    held = next(v for v in fid["features"] if v["status"] == "ambiguous")
    assert "already cited for" in held["reason"]
