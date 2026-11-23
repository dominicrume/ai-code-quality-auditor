# FINDING_010 — `send()` promised https and would follow a redirect off it

**Status:** fixed 23 November 2026, in 0.6.8. Pinned by
`tests/test_finding_009_and_010.py`.
**Found:** 23 November 2026, from an external user's report. The reported defect
was a false positive; looking into it found a real one at the same line.
**Module:** `auditor/core/share.py`

## What was reported

The tool's own scan of itself raised:

    MEDIUM B310 CWE-22  core/share.py:97
    urlopen accepts any URL scheme, including file:/, which could read local files.

## That part is a false positive

Nine lines above the call:

    if not str(url).lower().startswith("https://"):
        raise ValueError("the destination must be https://")

`file:`, `http:`, `ftp:`, `gopher:` and a leading-space `" https://"` are all
refused, and that is now pinned by a test. Bandit flags `urlopen` wherever it
cannot prove the scheme, and it cannot follow a guard in an enclosing function.

Worth stating plainly, because it is this project's own subject matter: **a
careful reader took a static finding at face value and reported code that was
already correct.** That is the cost of an unqualified finding, and it is the
same shape as FINDING_006, where nine HIGH findings were charged to a team that
had not written the code. There it reported somebody else's code as yours; here
it reported correct code as broken.

## The real defect, at the same line

`urlopen` follows redirects. Python's `HTTPRedirectHandler` permits the new
location to be `http`, `https` or `ftp` — it blocks `file:` and little else.

So a server could answer this POST with `302 Location: http://…` and the
payload would be re-sent over cleartext. The function's docstring says *"Refuses
anything but https, so a root cannot travel in the clear."* The check ran once,
on the URL the caller passed, and the promise did not survive the first
redirect.

Only the initial scheme was ever validated. That is the hole, it is narrower
than the one reported, and it is real.

## The fix

`_https_only_opener()` builds an opener whose redirect handler refuses any new
location that is not `https://`, and `send` uses it instead of the module-level
`urlopen`. Verified against a local server that answers the POST with a 302 to
`http://`, which is now refused rather than followed.

## The credit

The reported cause was wrong and the reported line was right. A report that
points at the correct line for the wrong reason is still a good report, and
this one found a defect that no test in this repository was looking for.
