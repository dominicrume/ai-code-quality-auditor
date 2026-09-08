"""Flask dashboard for the experiment CSV output.

Stage 3.5 — NOT in the dissertation scope. The CSV report is the
authoritative published artefact; this is a visual inspection layer.

Run:
    PYTHONPATH=. python -m auditor.dashboard.app
    # open http://127.0.0.1:5050

(Port 5000 is avoided because macOS AirPlay Receiver hijacks it and
returns HTTP 403; AUDITOR_PORT overrides the default if needed.)
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

from flask import Flask, abort, jsonify, render_template

from auditor.core.calibration import BANDS
from auditor.remediation.engine import remediate

import os

ROOT = Path(os.environ.get("AUDITOR_ROOT", Path.cwd())).resolve()
REPORTS_DIR = ROOT / "data" / "reports"

# Each metric's polarity: True = lower is better.
METRIC_LOWER_BETTER = {
    "security_density": True,
    "complexity_mean": True,
    "duplication_pct": True,
    "hallucinations": True,
    "correction_freq": True,
}

# Calibrated interpretation for partner-facing charts. Declared once in
# auditor/core/calibration.py so the CLI, dashboard and mobile client cannot
# drift apart and report three different verdicts for the same number.
METRIC_CALIBRATION = BANDS

# Short human descriptions surfaced in the UI.
METRIC_BLURB = {
    "security_density": "Security findings per 1,000 lines of Python, expressed as a governance-relevant density signal.",
    "complexity_mean":  "Average structural complexity per function, indicating how maintainable the code is likely to be.",
    "duplication_pct":  "Share of code that appears in repeated 6-line patterns, signalling maintainability debt.",
    "hallucinations":   "Features implemented outside the approved specification, creating delivery and compliance risk.",
    "correction_freq":  "Frequency of corrective edits during the session, indicating how much rework the workflow required.",
}

# Explicit interpretation guidance for the charts and the adoption story.
METRIC_GUIDANCE = {
    "security_density": {
        "axis": "Decision guidance: lower is better. Values at or below 50 are manageable; 50 to 100 signals rising governance risk; above 100 is a clear concern.",
        "adoption": "Adoption implication: tools that produce frequent security issues should not be rolled out broadly without remediation and review.",
    },
    "complexity_mean": {
        "axis": "Decision guidance: lower is better. Values at or below 3 are broadly sustainable; 3 to 6 signals rising maintainability risk; above 6 is likely to become brittle in production.",
        "adoption": "Adoption implication: code that is structurally complex is harder to maintain, review, and govern at scale.",
    },
    "duplication_pct": {
        "axis": "Decision guidance: lower is better. Values at or below 5 are healthy; 5 to 10 suggests avoidable copy-and-paste debt; above 10 is a strong sign of maintainability problems.",
        "adoption": "Adoption implication: high duplication increases the chance of inconsistent fixes and makes long-term stewardship harder.",
    },
    "hallucinations": {
        "axis": "Decision guidance: lower is better. Zero is ideal; 1 to 3 indicates scope drift and trust risk; above 3 is a serious control failure.",
        "adoption": "Adoption implication: a tool that ships features outside the spec creates procedural and compliance risk, even when it appears productive.",
    },
    "correction_freq": {
        "axis": "Decision guidance: lower is better. Values at or below 10 are efficient; 10 to 25 indicates repeated editing effort; above 25 suggests a poor interaction loop for real-world use.",
        "adoption": "Adoption implication: high correction frequency points to friction that can erode developer trust and slow delivery.",
    },
}

app = Flask(__name__)


def _describe_spec_context(provenance: dict | None) -> str:
    """Return a compact, human-readable spec summary for the report header."""
    if not provenance:
        return "unknown"
    if provenance.get("spec"):
        return provenance["spec"]
    spec_files = provenance.get("spec_files") or []
    if not spec_files:
        return "unknown"
    cleaned = [Path(item).stem.replace("_", " ") for item in spec_files if item]
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) <= 3:
        return ", ".join(cleaned)
    return f"{len(cleaned)} spec files"


def _is_multi_condition_report(csv_path: Path) -> bool:
    """True only for long-format CSVs with >= 2 conditions. Hides single-spec
    human captures and wide comparison tables from the index for a clean view."""
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if not {"metric", "condition", "value"} <= set(reader.fieldnames or []):
                return False
            conditions = {r["condition"] for r in reader if r.get("condition")}
        return len(conditions) >= 2
    except Exception:
        return False


def _list_reports() -> list[dict]:
    if not REPORTS_DIR.exists():
        return []
    out = []
    for csv_path in sorted(REPORTS_DIR.glob("*.csv")):
        if not _is_multi_condition_report(csv_path):
            continue
        prov_path = REPORTS_DIR / f"{csv_path.stem}.provenance.json"
        prov = json.loads(prov_path.read_text()) if prov_path.exists() else {}
        out.append({
            "run_id": csv_path.stem,
            "csv": csv_path.name,
            "kind": prov.get("kind", "unknown"),
            "is_pilot": prov.get("kind") == "pilot",
            "is_dissertation_result": prov.get("is_dissertation_result", False),
            "generated_at": prov.get("generated_at"),
            "spec": prov.get("spec"),
        })
    return out


def _read_csv_rows(run_id: str) -> list[dict]:
    csv_path = REPORTS_DIR / f"{run_id}.csv"
    if not csv_path.exists():
        abort(404)
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        header = set(reader.fieldnames or [])
        required = {"metric", "condition", "value"}
        missing = required - header
        if missing:
            abort(400, description=f"Missing columns: {', '.join(sorted(missing))}")
        rows = []
        for r in reader:
            try:
                r["value"] = float(r["value"])
                rows.append(r)
            except (TypeError, ValueError):
                pass
    return rows


def _compute_pivot_and_units(rows: list[dict]) -> tuple[dict, dict]:
    agg: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    units: dict[str, str] = {}
    for r in rows:
        agg[r["metric"]][r["condition"]].append(r["value"])
        units[r["metric"]] = r.get("unit", "")
    pivot: dict[str, dict[str, float]] = {
        m: {c: sum(v) / len(v) for c, v in conds.items()}
        for m, conds in agg.items()
    }
    return pivot, units


def _compute_normalized_scores(pivot: dict, conditions: list[str], metrics: list[str]) -> dict:
    norm: dict[str, dict[str, float]] = {}
    for metric in metrics:
        cfg = METRIC_CALIBRATION.get(metric, {"ideal": 0.0, "warning": 1.0, "critical": 2.0})
        ideal, critical = cfg["ideal"], cfg["critical"]
        norm[metric] = {}
        for c in conditions:
            v = pivot[metric].get(c, 0.0)
            if not METRIC_LOWER_BETTER.get(metric, True):
                if v <= ideal: score = 1.0
                elif v >= critical: score = 0.0
                else: score = 1.0 - ((v - ideal) / (critical - ideal))
            else:
                if v <= ideal: score = 1.0
                elif v >= critical: score = 0.0
                else: score = max(0.0, 1.0 - ((v - ideal) / max(critical - ideal, 1e-6)))
            norm[metric][c] = round(score, 4)
    return norm


def _compute_ranks(pivot: dict, conditions: list[str], metrics: list[str]) -> dict:
    ranks: dict[str, dict[str, int]] = {}
    for metric in metrics:
        ordered = sorted(conditions, key=lambda c: pivot[metric].get(c, 0.0), reverse=not METRIC_LOWER_BETTER.get(metric, True))
        rank_map: dict[str, int] = {}
        prev_value, rank = None, 0
        for i, c in enumerate(ordered, start=1):
            v = pivot[metric].get(c, 0.0)
            if v != prev_value:
                rank = i
                prev_value = v
            rank_map[c] = rank
        ranks[metric] = rank_map
    return ranks


def _build_leaderboard(ranks: dict, conditions: list[str], metrics: list[str]) -> list[dict]:
    leaderboard = []
    for c in conditions:
        total = sum(ranks[m][c] for m in metrics)
        leaderboard.append({
            "condition": c,
            "rank_sum": total,
            "avg_rank": round(total / max(len(metrics), 1), 2),
            "wins": sum(1 for m in metrics if ranks[m][c] == 1),
        })
    leaderboard.sort(key=lambda x: x["rank_sum"])
    for i, row in enumerate(leaderboard, start=1):
        row["overall_rank"] = i
    return leaderboard


def _build_summary(pivot: dict, units: dict, conditions: list[str], metrics: list[str]) -> list[dict]:
    summary = []
    for metric in metrics:
        items = [(c, pivot[metric].get(c, 0.0)) for c in conditions]
        items.sort(key=lambda x: x[1], reverse=not METRIC_LOWER_BETTER.get(metric, True))
        summary.append({
            "metric": metric, "unit": units.get(metric, ""), "blurb": METRIC_BLURB.get(metric, ""),
            "best_condition": items[0][0], "best_value": items[0][1],
            "worst_condition": items[-1][0], "worst_value": items[-1][1],
            "values": {c: pivot[metric].get(c, 0.0) for c in conditions},
        })
    return summary


def _determine_banner(rows: list[dict], conditions: list[str], provenance: dict | None) -> tuple[str, str, dict]:
    reps_per_condition: dict[str, int] = {}
    for cond in conditions:
        cond_rows = [r for r in rows if r["condition"] == cond]
        counts = defaultdict(int)
        for r in cond_rows: counts[r["metric"]] += 1
        reps_per_condition[cond] = min(counts.values()) if counts else 0
    min_n = min(reps_per_condition.values()) if reps_per_condition else 0
    declared_kind = (provenance or {}).get("kind", "unknown")
    if min_n >= 5 or declared_kind == "main_study":
        return "dissertation", f"Dissertation result. N = {min_n} runs per condition (across {len(conditions)} conditions).", reps_per_condition
    if declared_kind == "pilot" or min_n < 5:
        return "pilot", f"Pilot data — N = {min_n} run(s) per condition. Dissertation threshold is N ≥ 5 per protocol §4.", reps_per_condition
    return "unknown", "Provenance unknown — see provenance metadata at the foot of this report.", reps_per_condition


def _load_report(run_id: str) -> dict:
    rows = _read_csv_rows(run_id)
    pivot, units = _compute_pivot_and_units(rows)
    conditions = sorted({r["condition"] for r in rows})
    metrics = sorted(pivot)
    
    norm = _compute_normalized_scores(pivot, conditions, metrics)
    ranks = _compute_ranks(pivot, conditions, metrics)
    leaderboard = _build_leaderboard(ranks, conditions, metrics)
    summary = _build_summary(pivot, units, conditions, metrics)

    prov_path = REPORTS_DIR / f"{run_id}.provenance.json"
    provenance = json.loads(prov_path.read_text()) if prov_path.exists() else None
    
    banner_kind, banner_text, reps_per_condition = _determine_banner(rows, conditions, provenance)

    return {
        "run_id": run_id, "rows": rows, "pivot": {m: pivot[m] for m in metrics}, "norm": norm,
        "ranks": ranks, "summary": summary, "leaderboard": leaderboard, "units": units,
        "blurbs": METRIC_BLURB, "metric_guidance": METRIC_GUIDANCE, "conditions": conditions,
        "metrics": metrics, "provenance": provenance, "spec_summary": _describe_spec_context(provenance),
        "banner_kind": banner_kind, "banner_text": banner_text, "reps_per_condition": reps_per_condition,
    }


# ---- HTML routes -----------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html", reports=_list_reports())


@app.route("/report/<run_id>")
def report(run_id: str):
    return render_template("report.html", **_load_report(run_id))


# ---- Pilot waitlist --------------------------------------------------------
# Visa-safe: collects email addresses for a future commercial cohort. No
# payment is taken; no commercial service is offered now. Submissions
# persist to data/waitlist.jsonl, gitignored, retrievable via `fly ssh
# console` or by emailing them to the operator on submit (best-effort).

import os
from datetime import datetime, timezone
from flask import request

WAITLIST_PATH = ROOT / "data" / "waitlist.jsonl"


def _persist_waitlist(entry: dict) -> None:
    WAITLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with WAITLIST_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def _notify_operator(entry: dict) -> None:
    """Best-effort email to the operator. Silently swallows any error so
    the form submission still succeeds for the user."""
    try:
        import smtplib
        from email.message import EmailMessage
        host = os.environ.get("SMTP_HOST")
        if not host:
            return
        msg = EmailMessage()
        msg["Subject"] = f"[auditor waitlist] {entry.get('company','?')} — {entry.get('name','?')}"
        msg["From"] = os.environ.get("SMTP_FROM", "noreply@auditor.local")
        msg["To"] = os.environ.get("OPERATOR_EMAIL", "admin@veritaport.co.uk")
        msg.set_content(json.dumps(entry, indent=2))
        with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", "587"))) as s:
            s.starttls()
            s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
            s.send_message(msg)
    except Exception:
        pass


@app.route("/pilot", methods=["GET", "POST"])
def pilot():
    if request.method == "POST":
        entry = {
            "name":    (request.form.get("name") or "").strip()[:120],
            "email":   (request.form.get("email") or "").strip()[:200],
            "company": (request.form.get("company") or "").strip()[:200],
            "role":    (request.form.get("role") or "").strip()[:200],
            "context": (request.form.get("context") or "").strip()[:2000],
            "ip":      request.headers.get("Fly-Client-IP") or request.remote_addr or "",
            "ua":      (request.user_agent.string or "")[:300],
            "ts":      datetime.now(timezone.utc).isoformat(),
        }
        if entry["email"] and entry["name"] and entry["company"]:
            _persist_waitlist(entry)
            _notify_operator(entry)
        return render_template("pilot.html", submitted=True)
    return render_template("pilot.html", submitted=False)


@app.route("/pilot/admin")
def pilot_admin():
    """Operator-only view. Protected by a single env token so the URL alone
    isn't enough — `?key=<WAITLIST_ADMIN_KEY>` is required."""
    key = request.args.get("key", "")
    expected = os.environ.get("WAITLIST_ADMIN_KEY", "")
    if not expected or key != expected:
        return ("unauthorised", 401)
    if not WAITLIST_PATH.exists():
        return jsonify({"entries": [], "count": 0})
    entries = [json.loads(line) for line in WAITLIST_PATH.read_text().splitlines() if line.strip()]
    return jsonify({"entries": entries, "count": len(entries)})


# ---- JSON API --------------------------------------------------------------

@app.route("/api/reports")
def api_reports():
    return jsonify(_list_reports())


@app.route("/api/report/<run_id>")
def api_report(run_id: str):
    data = _load_report(run_id)
    # rows is large; the SPA can request it separately if needed.
    data = {k: v for k, v in data.items() if k != "rows"}
    return jsonify(data)


@app.route("/api/scan", methods=["POST"])
def api_scan():
    """Trigger a headless scan of a directory."""
    data = request.get_json() or {}
    target_path = data.get("path", ".")
    spec_path = data.get("spec", None)

    from auditor.core.scan import scan_directory
    import yaml

    spec_data = None
    if spec_path:
        p = Path(spec_path)
        if p.exists():
            spec_data = yaml.safe_load(p.read_text())

    result = scan_directory(Path(target_path), spec_data)
    
    return jsonify({
        "status": "success",
        "path": str(result.path),
        "files": result.file_count,
        "total_loc": result.total_loc,
        "python_files": result.python_files,
        "spec": result.spec_name,
        "coverage_note": result.coverage_note,
        "metrics": {
            o.name: ({"value": o.value, "unit": o.unit, "band": o.band, "details": getattr(o, "details", None)}
                     if o.applicable else {"skipped": o.skipped_reason})
            for o in result.outcomes
        },
    })


@app.route("/api/remediate", methods=["POST"])
def api_remediate():
    """Trigger the remediation engine."""
    results = remediate(apply=True)
    return jsonify({"status": "success", "results": results})


@app.route("/api/drift/acknowledge", methods=["POST"])
def api_drift_acknowledge():
    """Dynamically add the feature to .auditor/spec.yaml"""
    from flask import request
    import yaml
    
    data = request.get_json() or {}
    item = data.get("item")
    if not item:
        return jsonify({"status": "error", "message": "No item provided"}), 400

    spec_path = ROOT / ".auditor" / "spec.yaml"
    if not spec_path.exists():
        return jsonify({"status": "error", "message": "spec.yaml not found"}), 404

    spec = yaml.safe_load(spec_path.read_text())
    
    features = spec.setdefault("features", [])
    # Only add if not exists
    if not any(f.get("id") == f"feature.{item}" for f in features):
        features.append({
            "id": f"feature.{item}",
            "description": f"User explicitly acknowledged: {item}"
        })
        spec_path.write_text(yaml.dump(spec, sort_keys=False))

    return jsonify({"status": "success", "message": f"Acknowledged {item}"})


@app.route("/api/drift/strip", methods=["POST"])
def api_drift_strip():
    """Strip the endpoint out of the codebase using the AST parser"""
    from flask import request
    from auditor.remediation.ast_stripper import strip_hallucinated_endpoint
    
    data = request.get_json() or {}
    item = data.get("item")
    if not item:
        return jsonify({"status": "error", "message": "No item provided"}), 400

    success = strip_hallucinated_endpoint(ROOT, item)
    if success:
        return jsonify({"status": "success", "message": f"Stripped {item}"})
    else:
        return jsonify({"status": "error", "message": f"Could not find or strip {item}"}), 404


if __name__ == "__main__":
    # Avoid macOS AirPlay's port 5000 (HTTP 403 hijack). Override via env.
    port = int(os.environ.get("AUDITOR_PORT", "5050"))
    app.run(host="127.0.0.1", port=port, debug=False)
