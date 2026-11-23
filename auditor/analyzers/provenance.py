"""Who wrote this file: the project, a library it vendored, or a build step.

Why this exists
---------------
A scan of a SuiteCRM-derived CRM at a Lagos summit reported nine HIGH
dynamic-code-execution findings. Eight were in third-party libraries the team
had vendored (RGraph, a jQuery plugin, markItUp, FlashCanvas, pChart,
Chart.js, Google's MarkerClusterer) and the ninth was upstream SuiteCRM. **None
was written by the team being audited**, and the report's first recommendation
was to go and validate all nine, which sends an engineer to audit jQuery.

`adapters/_shared.VENDOR_DIRS` already existed to prevent exactly this, and its
own comment names the failure mode: *counting them is how a tool reports 83%
duplication on a repository whose own source is barely duplicated*. It matches
**directory names** -- `vendor`, `third_party`, `node_modules`. Real projects of
this age vendor into ordinary paths: `include/javascript/jquery/`,
`modules/AOR_Charts/lib/pChart/`. The guard was built and it misses the
commonest layout there is.

Not exclusion. Attribution.
---------------------------
The repair is deliberately **not** to drop these files. Silently dropping
findings is the same class of error as silently counting them: both change a
number without telling the reader. Files are classified, metrics about the
project's code are computed over the project's code, and everything else is
reported separately and by name.

Three kinds:

``first_party``  the project's own source. The only thing a headline number
                 should ever describe.
``vendored``     a library the project redistributes but does not maintain.
                 Real findings here are real, and they belong to an upgrade
                 decision rather than to a code review.
``generated``    minified or packed output. Its line numbers point into a file
                 with one line, so a finding in it is not actionable at all,
                 and minification trips source heuristics by construction.

On being wrong
--------------
Misclassifying the project's own file as vendored hides a real finding, which
is the costlier mistake. So every rule here needs a positive signal: a known
library's name, a build-output filename, or line lengths no human writes.
A directory called `lib` or `libs` is **not** a signal. Plenty of projects keep
their own code there, and `modules/AOR_Charts/lib/pChart/` is caught by
`pchart`, which is the name of the library, not by `lib`.
"""
from __future__ import annotations

import re
from statistics import median

FIRST_PARTY = "first_party"
VENDORED = "vendored"
GENERATED = "generated"


# Build output. The name is the statement: somebody ran a tool over source that
# lives elsewhere, and this is what came out.
_GENERATED_NAME = re.compile(
    r"""(?ix)
    (?: [.\-_] (?: min | pack(?:ed)? | bundle | dist | compiled | prod ) )
    (?: \.[a-z0-9]+ )* $
    """
)

# Libraries seen vendored into ordinary directories. A stem matches when the
# name is followed by nothing, a digit, or a separator, so `jquery`,
# `jquery-3.6.0` and `jquery.json-2.3` all match and `jquerylike_helpers` does
# not.
_LIBRARIES = (
    "jquery", "zepto", "prototype", "mootools", "yui", "dojo", "underscore",
    "lodash", "moment", "backbone", "knockout", "angular", "react", "vue",
    "ember", "d3", "three", "raphael", "rgraph", "highcharts", "chart",
    "chartjs", "pchart", "flot", "jit", "flashcanvas", "markerclusterer",
    "modernizr", "html5shiv", "respond", "bootstrap", "popper", "tether",
    "select2", "datatables", "markitup", "ckeditor", "tinymce", "codemirror",
    "ace", "swiper", "slick", "fancybox", "colorpicker", "qtip", "jqtree",
    "tree.jquery", "requirejs", "systemjs", "polyfill", "es5-shim", "json2",
    "sizzle", "normalize", "jquery-ui", "jqueryui",
)
_LIBRARY_STEM = re.compile(
    r"(?i)^(?:" + "|".join(re.escape(n) for n in _LIBRARIES) + r")(?:[.\-_0-9]|$)"
)

# A path segment that *is* a library's name says the whole directory is theirs.
_LIBRARY_DIRS = frozenset(n.lower() for n in _LIBRARIES) | {
    "libraries", "vendor", "vendored", "third_party", "thirdparty",
    "externals", "bower_components", "jspm_packages",
}

# Minified code has line lengths no author produces. Checked on the content so
# a library renamed by a build step is still caught.
_LONGEST_HUMAN_LINE = 1000
_HUMAN_MEDIAN_LINE = 200


def _looks_minified(content: str) -> bool:
    lines = content.splitlines() or [content]
    if not lines:
        return False
    longest = max(len(line) for line in lines)
    if longest > _LONGEST_HUMAN_LINE:
        return True
    # A handful of long lines is a data table. A high *median* is minification.
    return len(lines) > 3 and median(len(line) for line in lines) > _HUMAN_MEDIAN_LINE


def classify(path: str, content: str = "") -> str:
    """Who wrote this file. See the module docstring for the three kinds."""
    parts = [p for p in path.replace("\\", "/").split("/") if p]
    if not parts:
        return FIRST_PARTY
    name = parts[-1]
    stem = name.split(".")[0]

    # Build output, by name or by shape. Checked first: a minified copy of a
    # library is generated before it is vendored, and the line numbers are the
    # reason a reader can do nothing with it either way.
    if _GENERATED_NAME.search(name) or (content and _looks_minified(content)):
        return GENERATED

    if any(p.lower() in _LIBRARY_DIRS for p in parts[:-1]):
        return VENDORED
    if _LIBRARY_STEM.match(name) or _LIBRARY_STEM.match(stem):
        return VENDORED
    return FIRST_PARTY


def classify_all(files: dict[str, str]) -> dict[str, str]:
    """``{path: kind}`` for a codebase's files."""
    return {path: classify(path, content) for path, content in files.items()}


def split(files: dict[str, str]) -> tuple[dict[str, str], dict[str, str]]:
    """``(first_party, not_first_party)``.

    A headline number is computed over the first half. The second half is
    reported, by name and by count, and never silently dropped.
    """
    kinds = classify_all(files)
    mine = {p: c for p, c in files.items() if kinds[p] == FIRST_PARTY}
    theirs = {p: c for p, c in files.items() if kinds[p] != FIRST_PARTY}
    return mine, theirs
