# FINDING_007 — minified and packed files were analysed and cited by line

**Status:** fixed 23 November 2026, in 0.6.7, on the scan path only. Pinned by
`tests/test_finding_005_to_008.py`.
**Found:** 23 November 2026, same field report as FINDING_005.
**Module:** `auditor/analyzers/provenance.py`

## What happened

Findings were reported at locations a reader can do nothing with:

    HIGH   JS101 CWE-95  .../jjwg_Maps/javascript/markerclusterer_packed.js:1
    MEDIUM JS102 CWE-79  .../include/javascript/jquery/jquery-min.js:2
    MEDIUM JS102 CWE-79  .../include/javascript/jquery/bootstrap.min.js:6
    MEDIUM JS102 CWE-79  .../jjwg_Maps/DataTables/media/js/jquery.dataTables.min.js:22

`markerclusterer_packed.js:1` is line 1 of a file with one line. The citation
points at the whole library. Every one of these is a build artefact whose
source lives elsewhere.

Two separate harms:

- **The citation is useless.** A finding is only worth reporting if somebody
  can go and look. "Line 2 of a 90,000-character line" is not a location.
- **Minification trips the heuristics by construction.** Packers rewrite code
  into forms — string concatenation into `eval`, dense property assignment —
  that match the patterns a source scanner looks for. The findings are
  artefacts of the packer rather than properties of the authored code.

## The fix

`provenance.classify` returns `generated` for build output, detected two ways
so a renamed artefact is still caught:

- **By name:** `.min.`, `-min.`, `.packed.`, `_packed.`, `.bundle.`, `.dist.`,
  `.compiled.`, `.prod.`
- **By shape:** any line over 1,000 characters, or a median line length over
  200 across more than three lines. Those are lengths no author produces.

Checked before the vendored test, because a minified copy of a library is
generated before it is vendored, and the unusable line numbers are the reason
a reader can act on neither.

Counted and named in `codebase["not_authored"]` rather than dropped silently.
