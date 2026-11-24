"""The Lagos field report: `auditor scan .` on a SuiteCRM-derived CRM.

The scan printed `Security 2.40 OK` beside nine HIGH dynamic-code-execution
findings, every one of which was in code the audited team had not written, and
set `worst_band: critical` off a duplication figure that was mostly the
project's own build layout.

FINDING_005, 006 and 007 are fixed and pinned here. FINDING_008 is open, and
the last test in this file pins the fact that it is still open, so closing it
has to be deliberate.

The paths are the real ones from the report. Contents are synthetic.
"""
from __future__ import annotations

import pathlib

import pytest

from auditor.adapters._shared import load_codebase
from auditor.analyzers import provenance as prov
from auditor.core.calibration import band_for, floor_for
from auditor.core.scan import scan_directory

EVAL = "function go(s){ return eval(s); }\n"
OWN_TS = "export class Modal {\n  render(h: string) { this.el.innerHTML = h; }\n}\n"


def _crm(tmp_path: pathlib.Path) -> pathlib.Path:
    """A tree shaped like the one in the report."""
    root = tmp_path / "SparkrCRM"

    def w(rel: str, text: str) -> None:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    # vendored libraries, in ordinary directories -- nothing is called `vendor`
    w("public/legacy/include/javascript/jquery/jquery.json-2.3.js", EVAL * 3)
    w("public/legacy/include/javascript/jquery/markitup/jquery.markitup.js", EVAL * 3)
    w("public/legacy/include/SuiteGraphs/rgraph/libraries/RGraph.common.core.js", EVAL * 3)
    w("public/legacy/modules/AOR_Charts/lib/pChart/imagemap.js", EVAL * 3)
    w("public/legacy/modules/AOR_Reports/js/Chart.js", EVAL * 3)
    # build output
    w("public/legacy/modules/jjwg_Maps/javascript/markerclusterer_packed.js",
      "var a=1;" * 400 + "eval(x);\n")
    w("public/legacy/include/javascript/jquery/jquery-min.js",
      "!function(){" + "var b=2;" * 300 + "}();\n")
    # the team's own code
    w("core/app/core/src/lib/components/modal/classic-modal.component.ts", OWN_TS)
    w("core/app/core/src/lib/fields/update-email-signature.action.ts", OWN_TS)
    # the dual tree SuiteCRM ships: FINDING_008, still open
    w("public/legacy/include/javascript/include.js", OWN_TS.replace("export ", ""))
    w("public/legacy/jssource/src_files/include/javascript/include.js",
      OWN_TS.replace("export ", ""))
    return root


# --- FINDING_006: whose code is this -------------------------------------

@pytest.mark.parametrize("path,kind", [
    ("public/legacy/include/SuiteGraphs/rgraph/libraries/RGraph.common.core.js", prov.VENDORED),
    ("public/legacy/include/javascript/jquery/jquery.json-2.3.js", prov.VENDORED),
    ("public/legacy/include/javascript/jquery/markitup/jquery.markitup.js", prov.VENDORED),
    ("public/legacy/modules/AOR_Charts/lib/pChart/imagemap.js", prov.VENDORED),
    ("public/legacy/modules/AOR_Reports/js/Chart.js", prov.VENDORED),
    ("public/legacy/jssource/src_files/include/SugarCharts/Jit/FlashCanvas/flashcanvas.js",
     prov.VENDORED),
    ("public/legacy/modules/jjwg_Maps/javascript/markerclusterer_packed.js", prov.GENERATED),
    ("public/legacy/include/javascript/jquery/jquery-min.js", prov.GENERATED),
    ("public/legacy/include/javascript/jquery/bootstrap.min.js", prov.GENERATED),
    # the team's own, and the ninth HIGH, which is upstream source not a library
    ("public/legacy/modules/FP_events/jsclass_scheduler.js", prov.FIRST_PARTY),
    ("core/app/core/src/lib/components/modal/classic-modal.component.ts", prov.FIRST_PARTY),
])
def test_the_real_paths_from_the_report_are_attributed(path, kind):
    assert prov.classify(path) == kind


@pytest.mark.parametrize("path", [
    "src/lib/billing/charge.ts",
    "app/libs/my_own_helper.js",
    "lib/index.js",
    "core/app/core/src/lib/fields/update-email-signature.action.ts",
    "modules/chartutils/helpers.js",
    "src/charting_service.py",
])
def test_a_projects_own_code_is_never_taken_for_a_library(path):
    """Hiding a real finding is the costlier mistake, so `lib` and `libs` are
    not signals and a name must match a library at a word boundary."""
    assert prov.classify(path) == prov.FIRST_PARTY


def test_minification_is_detected_by_shape_as_well_as_by_name():
    """A build artefact renamed by a later step is still a build artefact."""
    assert prov.classify("app/widget.js", "x=1;" * 500) == prov.GENERATED
    assert prov.classify("app/widget.js", "const a = 1;\nconst b = 2;\n") == prov.FIRST_PARTY


def test_a_long_data_line_is_not_minification():
    """A handful of long lines is a data table; a high median is minification."""
    src = "export const T = [\n" + "  1,\n" * 50 + "];\nconst blob = '" + "d" * 300 + "';\n"
    assert prov.classify("app/table.js", src) == prov.FIRST_PARTY


def test_the_scan_measures_the_teams_code_and_names_the_rest(tmp_path):
    cb = load_codebase(_crm(tmp_path), respect_ignores=True)
    not_mine = cb.get("not_authored", {})
    assert len(not_mine) == 7, not_mine
    assert set(not_mine.values()) == {prov.VENDORED, prov.GENERATED}
    # named, not dropped: the report has to be able to say what was set aside
    assert any("pChart" in p for p in not_mine)
    assert all(p not in cb["files"] for p in not_mine)


def test_the_experiment_path_is_untouched(tmp_path):
    """The published figures walked what they walked. `respect_ignores` off is
    the experiment path and must see every file, exactly as before."""
    root = _crm(tmp_path)
    raw = load_codebase(root, respect_ignores=False)
    assert "not_authored" not in raw
    assert len(raw["files"]) > len(load_codebase(root, respect_ignores=True)["files"])


def test_no_high_finding_is_charged_to_the_team_for_a_vendored_library(tmp_path):
    """The symptom: nine HIGH findings, none of them the team's code."""
    result = scan_directory(_crm(tmp_path))
    sec = next(o for o in result.outcomes if o.name == "security_density")
    highs = [d for d in (sec.details or []) if d.startswith("HIGH")]
    assert highs == [], highs


# --- FINDING_005: a density cannot speak for a severity -------------------

def test_the_old_thresholds_could_not_fail():
    """Documentary. 50 per kLOC is one finding every twenty lines, so the band
    was green on every project it was ever pointed at."""
    assert band_for("security_density", 2.4034) == "good"
    assert band_for("security_density", 49.9) == "good"


def test_a_high_finding_cannot_read_good():
    assert floor_for("good", {"HIGH": 9, "MEDIUM": 694, "LOW": 16}) == "critical"
    assert floor_for("good", {"HIGH": 1}) == "critical"


def test_one_high_finding_decides_the_colour_however_much_good_code_surrounds_it():
    """The published rule, pinned as a test.

    Stated in public on 23 November 2026: *the single worst problem decides the
    colour. One serious, unresolved problem turns the whole thing red, however
    much good code sits around it.* A promise made to a room is a specification
    this file now holds the instrument to. The density is deliberately varied
    across the whole green range to show that none of it can soften a HIGH.
    """
    for density in (0.0, 0.01, 2.4034, 49.9):
        assert band_for("security_density", density) == "good"
        assert floor_for(band_for("security_density", density), {"HIGH": 1}) \
            == "critical", density


def test_the_floor_is_not_a_claim_that_the_finding_is_exploitable():
    """Red is what to do next, not a verdict on the finding.

    The instrument cannot tell an exploitable `eval` from a false positive --
    FINDING_010 is one of its own false positives -- so the severity tally and
    the findings list travel beside the band for a human to read. Banding it
    red and handing over the evidence is honest; banding it comfortable and
    handing over the same evidence is not.
    """
    assert floor_for("good", {"HIGH": 1}) == "critical"
    # And it is still only the worst *present* severity that moves anything.
    assert floor_for("good", {"HIGH": 0}) == "good"


def test_a_medium_finding_reads_amber_and_never_green():
    """The owner's rule of 23 November 2026: a small problem is amber, never green.

    This replaces `test_mediums_and_lows_do_not_move_the_band`, which pinned the
    0.6.7 to 0.6.10 decision that MEDIUM left the band alone (694 mediums were
    in the FINDING_005 report). That decision is deliberately reversed in
    0.6.11; the trade-off, that many real projects now read amber, is accepted.
    """
    assert floor_for("good", {"MEDIUM": 1}) == "warn"
    assert floor_for("good", {"MEDIUM": 694, "LOW": 16}) == "warn"
    for density in (0.0, 0.01, 2.4034, 49.9):
        assert floor_for(band_for("security_density", density), {"MEDIUM": 1}) \
            == "warn", density


def test_a_medium_stops_at_amber_and_red_still_belongs_to_high():
    assert floor_for("good", {"MEDIUM": 694}) != "critical"
    assert floor_for("warn", {"MEDIUM": 3}) == "warn"
    assert floor_for("good", {"HIGH": 1, "MEDIUM": 694}) == "critical"


def test_lows_do_not_move_the_band():
    """LOW is unchanged: it never moves the band."""
    assert floor_for("good", {"LOW": 40}) == "good"
    assert floor_for("good", {"LOW": 1}) == "good"
    assert floor_for("good", {"MEDIUM": 0, "LOW": 16}) == "good"


def test_the_floor_never_lowers_a_band():
    assert floor_for("critical", {"HIGH": 1}) == "critical"
    assert floor_for("critical", {"MEDIUM": 694}) == "critical"
    assert floor_for("critical", {"LOW": 2}) == "critical"
    assert floor_for("warn", {"LOW": 2}) == "warn"
    assert floor_for("warn", None) == "warn"


def test_a_high_finding_in_the_teams_own_code_turns_it_red(tmp_path):
    """End to end, at a density that bands `good` on its own."""
    root = tmp_path / "svc"
    (root / "src").mkdir(parents=True)
    for i in range(12):
        (root / "src" / f"mod{i}.ts").write_text(
            f"export function f{i}() {{\n"
            + "".join(f"  const v{j} = {j};\n" for j in range(120)) + "  return 1;\n}\n")
    (root / "src" / "danger.ts").write_text(
        "export function run(s: string){ return eval(s); }\n")

    sec = next(o for o in scan_directory(root).outcomes
               if o.name == "security_density")
    assert band_for("security_density", sec.value) == "good", "density alone says good"
    assert sec.band == "critical", "the HIGH finding must decide the colour"
    assert sec.diagnostics and sec.diagnostics["severity"].get("HIGH") == 1


# --- FINDING_008: still open, and that must stay deliberate ---------------

def test_the_duplicated_source_tree_is_still_counted(tmp_path):
    """FINDING_008 is open. Both copies of `include.js` are the project's own
    files and both are still measured, which is what inflates duplication on
    any repository shipping built assets beside their source.

    When this is fixed, this test fails. That is the point: closing it needs an
    erratum, because it changes a published figure."""
    cb = load_codebase(_crm(tmp_path), respect_ignores=True)
    both = [p for p in cb["files"] if p.endswith("include/javascript/include.js")]
    assert len(both) == 2, both
    assert cb["files"][both[0]] == cb["files"][both[1]], "bytewise identical"


def test_finding_008_is_declared_open_to_every_receipt():
    from auditor.receipts import bundle
    assert "FINDING_008" in [d["id"] for d in bundle.open_defects()]
