# FINDING_008 — a project's duplicated source tree is counted as duplication

**Status:** OPEN. Recorded 23 November 2026 and disclosed in every receipt
until it is closed. Partially mitigated in 0.6.7 by FINDING_006, which removes
the vendored share of the inflation; the dual-tree share remains.
**Found:** 23 November 2026, same field report as FINDING_005.
**Module:** `auditor/analyzers/duplication_analyzer.py`

## What happens

The scan reported:

    Duplication  32.82  RISK  86363 lines

and that single reading set `worst_band: critical` for the entire audit. It is
the headline a reader takes away, and it is substantially an artefact of the
project's build layout.

SuiteCRM ships its JavaScript twice, which is its normal and documented
structure:

    public/legacy/include/javascript/include.js            the deployed copy
    public/legacy/jssource/src_files/include/javascript/include.js   its source

The same pairing appears for `MySugar.js`, `SubPanelTiles.js`, `jit.js`,
`jsclass_scheduler.js`, `report_additionals.js`, `sugar_3.js`, `ajaxUI.js`,
`importWizard.js`, `Cal.js` and many more. The tool read both trees and
reported one tree as a duplicate of the other.

That is not duplicated work. It is one authored file and a build step's copy
of it, and telling a team to "review duplication hotspots and refactor" is
telling them to delete their own build output.

The same reading inflates the security count: findings in `include.js` and in
`jssource/src_files/.../include.js` are the same finding, counted twice.

## Why this is not fixed yet

The honest repair is to count bytewise-identical files once. That is a change
to the value of a metric whose figures are published in the dissertation, so it
needs an erratum and a deliberate decision rather than a quiet edit. Unlike
FINDING_006, it cannot be confined to the scan path without the duplication
analyser learning about provenance, which is a larger change than this defect
alone justifies.

## What a fix has to do

1. **Count an authored file once.** Two paths with the same content digest are
   one piece of work. This is generic: it needs no knowledge of SuiteCRM, and
   it fixes every build layout that keeps source beside output.
2. **Say what it collapsed.** A duplication figure that silently dropped half
   the tree is as unreadable as one that double-counted it. The count of
   collapsed copies belongs in the reading.
3. **Leave the security count alone.** A vulnerability present in two deployed
   files is two files to fix. Deduplication is correct for *duplication* and
   wrong for *security*, and the two must not share the rule.

## Until then

A duplication figure on any repository that ships built assets beside their
source may be substantially overstated, and it can set the worst band for an
entire audit on its own. Read the duplicated paths before quoting the
percentage. Disclosed in every receipt through `instrument_open_defects`.
