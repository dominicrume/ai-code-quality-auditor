"""Two field reports, 23 November 2026.

One from an external user: `auditor scan .` crashed with FileNotFoundError because
bandit was invoked as a bare command and a virtual environment's bin directory
is not on PATH unless it has been activated. One from the Lagos AI summit, on
Windows PowerShell: `auditor` was not a recognised command.

The same report also raised a MEDIUM B310 in `core/share.py`. That was a false positive
for the reason he gave, and it was the right line for a different reason.
"""
from __future__ import annotations

import subprocess
import sys

import pytest

from auditor.analyzers import security_analyzer as sec
from auditor.core import share


# --- FINDING_009: bandit was invoked through PATH -------------------------

def test_bandit_is_invoked_through_the_running_interpreter(monkeypatch, tmp_path):
    """`env/bin/pip install` then `env/bin/auditor scan .` is a correct and
    documented installation, and it crashed the whole scan."""
    (tmp_path / "a.py").write_text("x = 1\n")
    seen: dict = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="{}", stderr="")

    monkeypatch.setattr(sec.subprocess, "run", fake_run)
    sec._run_bandit(tmp_path)
    assert seen["cmd"][:3] == [sys.executable, "-m", "bandit"], seen["cmd"]
    assert seen["cmd"][0] != "bandit", "a bare name is resolved through PATH"


def test_a_missing_bandit_does_not_crash_the_scan(monkeypatch, tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n")

    def gone(cmd, **kw):
        raise FileNotFoundError(2, "No such file or directory", cmd[0])

    monkeypatch.setattr(sec.subprocess, "run", gone)
    results, unparsed = sec._run_bandit(tmp_path)
    assert results == []
    assert unparsed is sec._UNAVAILABLE


def test_a_silent_nonzero_exit_is_also_treated_as_unavailable(monkeypatch, tmp_path):
    """`python -m bandit` with the module absent exits non-zero and says
    nothing on stdout. Same situation, different route."""
    (tmp_path / "a.py").write_text("x = 1\n")
    monkeypatch.setattr(
        sec.subprocess, "run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, stdout="", stderr="no module"))
    _, unparsed = sec._run_bandit(tmp_path)
    assert unparsed is sec._UNAVAILABLE


def test_without_bandit_python_is_declared_unread_not_clean(monkeypatch):
    """The failure this instrument exists to catch is a density of 0.00 over
    code nothing read. Every Python line must be reported as unread."""
    monkeypatch.setattr(sec, "_run_bandit", lambda d: ([], sec._UNAVAILABLE))
    codebase = {"files": {"a.py": "import os\nos.system('x')\n" * 20,
                          "b.ts": "export const x = 1;\n"}}
    score = sec.analyze(codebase, [], {})
    assert score.unparsed == ["a.py"]
    assert score.diagnostics and "unavailable" in score.diagnostics
    assert "bandit" in score.diagnostics["unavailable"]
    assert score.coverage is not None and score.coverage < 1.0


def test_the_javascript_reading_survives_a_missing_bandit(monkeypatch):
    """A tool that dies on the whole scan because one analyser is missing has
    turned a partial answer into no answer."""
    monkeypatch.setattr(sec, "_run_bandit", lambda d: ([], sec._UNAVAILABLE))
    codebase = {"files": {"a.py": "x = 1\n",
                          "b.ts": "export function go(s){ return eval(s); }\n"}}
    score = sec.analyze(codebase, [], {})
    assert score.count == 1
    assert score.diagnostics["severity"].get("HIGH") == 1


# --- the Windows report: the escape hatch exists, say so ------------------

def test_python_dash_m_auditor_is_a_working_entry_point():
    """A PowerShell user got CommandNotFoundException. The console script is
    installed into an environment's bin directory, which is routinely not on
    PATH. `python -m auditor` always resolves, and must keep working."""
    out = subprocess.run([sys.executable, "-m", "auditor", "--help"],
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    assert "scan" in out.stdout


# --- FINDING_010: the https promise, across redirects ---------------------

@pytest.mark.parametrize("bad", [
    "file:///etc/passwd", "FILE:///etc/passwd", "http://example.com",
    "ftp://example.com", "gopher://x", " https://evil", "https:/x", "",
])
def test_send_refuses_every_scheme_but_https(bad):
    """The report said `urlopen` accepts any scheme including `file:`. It
    does not: this guard runs nine lines above the call. The finding was a
    false positive, and the tool reported it without seeing the guard."""
    with pytest.raises(ValueError, match="https"):
        share.send(bad, {"a": 1}, opener=lambda u, b: "SENT")


def test_send_accepts_https():
    assert share.send("https://ok.example", {"a": 1},
                      opener=lambda u, b: "SENT") == "SENT"


def test_a_redirect_off_https_is_refused():
    """The real defect at that line. `urlopen` follows redirects, and Python's
    handler permits the new location to be http or ftp. A server could answer
    302 and move this POST onto a cleartext connection, defeating the exact
    promise the docstring makes."""
    import http.server
    import threading
    import urllib.error
    import urllib.request

    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            self.send_response(302)
            self.send_header("Location", "http://example.invalid/collected")
            self.end_headers()

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{srv.server_address[1]}/", data=b"{}", method="POST")
        with pytest.raises(urllib.error.HTTPError, match="away from https"):
            share._https_only_opener().open(req, timeout=10)
    finally:
        srv.shutdown()
        srv.server_close()
