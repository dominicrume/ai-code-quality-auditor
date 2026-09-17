"""Command-line entry.

  auditor run        --spec X --workflow Y --run-id R   [--captures-root]
  auditor experiment --spec X --run-id Y                [--captures-root --reports-dir]

`run` audits a single condition; `experiment` audits all five and emits the
combined CSV report. Both commands rely on a captures directory laid out as
``<captures-root>/<run-id>/<condition>/`` — produced by capture-time invocations
of the adapters (see human_control_recorder.py and the per-vendor capture
flow in docs/METHODOLOGY.md).
"""
import time
from pathlib import Path

import click

from auditor.core import history
from auditor.core.experiment import build_default_adapters, run_experiment
from auditor.core.runner import run_audit


def _version() -> str:
    try:
        from importlib.metadata import version
        return version("ai-code-quality-auditor")
    except Exception:
        return "unknown"

CONDITIONS = ["human_control", "claude_code", "cursor_agent", "antigravity", "replit_agent"]


@click.group()
def main():
    """AI Code Quality Auditor.

    \b
    Start here:       auditor live
    Audit a folder:   auditor scan .
    Watch a folder:   auditor watch .
    Your own history: auditor history        (local only; auditor forget deletes it)
    Share aggregates: auditor share          (off unless you run it)
    Run the study:    auditor experiment --run-label main_001 --reps 10
    """


def _free_port(preferred: int, attempts: int = 20) -> int:
    """The preferred port, or the next free one.

    A port collision is not a decision a user should have to make; the tool
    knows how to find a free one and the URL is printed either way.
    """
    import socket

    for candidate in range(preferred, preferred + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", candidate))
                return candidate
            except OSError:
                continue
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))  # let the OS choose
        return sock.getsockname()[1]


@main.command("live")
@click.argument("path", type=click.Path(exists=True, file_okay=False, path_type=Path),
                default=".")
@click.option("--port", default=7777, show_default=True, type=int)
@click.option("--no-open", is_flag=True, help="Don't open a browser automatically.")
@click.option("--interval", default=1.0, show_default=True, type=float,
              help="Seconds between change checks.")
def live_cmd(path: Path, port: int, no_open: bool, interval: float):
    """Open a live audit dashboard for a folder. Start here.

    \b
      auditor live            audit this folder, live, in your browser

    Watches the folder and updates as code changes — yours or an agent's.
    Type what you asked the agent to build and scope-drift checking turns
    on. Ctrl+C to stop.
    """
    import logging
    import threading
    import webbrowser

    import flask.cli

    from auditor.live.server import LiveSession, create_app

    # A local audit tool is not a deployment. The dev-server banner and the
    # per-request log are noise that reads as an error to a first-time user.
    flask.cli.show_server_banner = lambda *a, **k: None
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    port = _free_port(port)
    session = LiveSession(path, interval=interval)
    app = create_app(session)  # starts the watcher

    url = f"http://127.0.0.1:{port}"
    empty = session.latest.file_count == 0
    click.echo()
    click.echo(f"  Live audit  {session.project}")
    click.echo(f"  {url}")
    if empty:
        click.echo("  Empty folder — start building and results appear automatically.")
    else:
        click.echo(f"  {session.latest.file_count} files · "
                   f"{session.latest.total_loc} lines")
    click.echo("  Ctrl+C to stop")
    click.echo()

    if not no_open:
        threading.Timer(0.7, lambda: webbrowser.open(url)).start()

    try:
        app.run(host="127.0.0.1", port=port, threaded=True,
                debug=False, use_reloader=False)
    except KeyboardInterrupt:
        pass
    finally:
        session.stop()
        click.echo("stopped")


BAND_STYLE = {"good": "green", "warn": "yellow", "critical": "red"}
BAND_MARK = {"good": "OK", "warn": "WARN", "critical": "RISK"}


@main.command("scan")
@click.argument("path", type=click.Path(exists=True, file_okay=False, path_type=Path),
                default=".")
@click.option("--spec", type=click.Path(exists=True, dir_okay=False, path_type=Path),
              default=None,
              help="Spec YAML declaring what was asked for. Enables the scope-drift check.")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of a table.")
@click.option("--fail-on", type=click.Choice(["never", "warn", "critical"]),
              default="never", show_default=True,
              help="Exit non-zero at this severity, for CI gating.")
@click.option("--decision-record", type=click.Path(dir_okay=False, path_type=Path),
              default=None, help="Write immutable JSON snapshot of findings to this file.")
@click.option("--no-history", is_flag=True,
              help="Do not record this scan in your local history.")
def scan_cmd(path: Path, spec: Path | None, as_json: bool, fail_on: str,
             decision_record: Path | None, no_history: bool):
    """Audit a directory in place — no session, no setup.

    \b
      auditor scan .                       audit the current folder
      auditor scan ./src --spec spec.yaml  include the scope-drift check
      auditor scan . --fail-on critical    gate a CI pipeline
      auditor scan . --decision-record out.json  write audit to disk
    """
    import json as _json

    import yaml
    from rich.console import Console
    from rich.table import Table

    from auditor.core.scan import scan_directory

    spec_data = yaml.safe_load(spec.read_text()) if spec else None
    result = scan_directory(path, spec_data)

    # Recorded on this machine, in the user's own home, and sent nowhere. `auditor history`
    # reads it back, `auditor forget` deletes it, AUDITOR_NO_HISTORY=1 switches it off.
    recorded = None
    if not no_history:
        try:
            recorded = history.append(result, _version())
        except OSError:
            recorded = None          # a read-only home is not a reason to fail an audit

    payload = {
        "path": str(result.path),
        "files": result.file_count,
        "total_loc": result.total_loc,
        "python_files": result.python_files,
        "spec": result.spec_name,
        "coverage_note": result.coverage_note,
        "metrics": {
            o.name: ({"value": o.value, "unit": o.unit, "band": o.band,
                      "coverage": o.coverage, "languages": o.languages,
                      "details": getattr(o, "details", None)}
                     if o.applicable else {"skipped": o.skipped_reason})
            for o in result.outcomes
        },
    }

    if decision_record:
        decision_record.parent.mkdir(parents=True, exist_ok=True)
        decision_record.write_text(_json.dumps(payload, indent=2))

    if as_json:
        click.echo(_json.dumps(payload, indent=2))
    else:
        console = Console()
        console.print()
        console.print(f"[bold]{result.path}[/bold]")
        console.print(
            f"[dim]{result.file_count} files · {result.total_loc} lines · "
            f"{result.readable_files} analysable"
            + (f" · spec: {result.spec_name}" if result.spec_name else "")
            + "[/dim]\n"
        )

        table = Table(show_edge=False, header_style="dim", pad_edge=False)
        table.add_column("")
        table.add_column("Check")
        table.add_column("Value", justify="right")
        table.add_column("")
        for o in result.outcomes:
            if o.applicable:
                style = BAND_STYLE[o.band]
                mark = f"[{style}]{BAND_MARK[o.band]}[/{style}]"
                if o.caveat:
                    mark += f"  [dim]{o.caveat}[/dim]"
                table.add_row(f"[{style}]●[/{style}]", o.label,
                              f"{o.value:.2f}", mark)
            else:
                table.add_row("[dim]○[/dim]", f"[dim]{o.label}[/dim]",
                              "[dim]n/a[/dim]", f"[dim]{o.skipped_reason}[/dim]")
        console.print(table)

        # A single serious finding never moves a density band, so name it.
        security = next((o for o in result.outcomes if o.name == "security_density"
                         and o.applicable and o.details), None)
        if security:
            from rich.markup import escape
            console.print(f"\n[yellow]Security findings to review[/yellow] "
                          f"[dim]({escape(security.details[0])})[/dim]")
            for line in security.details[1:]:
                console.print(f"  • {escape(line)}")

        if result.coverage_note:
            console.print(f"\n[yellow]Coverage:[/yellow] {result.coverage_note}")
        if recorded:
            console.print("[dim]saved to your local history · auditor history · auditor forget[/dim]")
        console.print()

    thresholds = {"never": None, "warn": ("warn", "critical"), "critical": ("critical",)}
    trigger = thresholds[fail_on]
    if trigger and result.worst_band in trigger:
        raise SystemExit(1)


def _render_scan_table(console, result):
    """Shared table renderer for `scan` and `watch`."""
    from rich.table import Table

    table = Table(show_edge=False, header_style="dim", pad_edge=False)
    table.add_column("")
    table.add_column("Check")
    table.add_column("Value", justify="right")
    table.add_column("")
    for o in result.outcomes:
        if o.applicable:
            style = BAND_STYLE[o.band]
            table.add_row(f"[{style}]●[/{style}]", o.label,
                          f"{o.value:.2f}", f"[{style}]{BAND_MARK[o.band]}[/{style}]")
        else:
            table.add_row("[dim]○[/dim]", f"[dim]{o.label}[/dim]",
                          "[dim]n/a[/dim]", f"[dim]{o.skipped_reason}[/dim]")
    console.print(table)


@main.command("watch")
@click.argument("path", type=click.Path(exists=True, file_okay=False, path_type=Path),
                default=".")
@click.option("--spec", type=click.Path(exists=True, dir_okay=False, path_type=Path),
              default=None,
              help="Spec YAML declaring what was asked for. Enables live scope-drift.")
@click.option("--interval", default=1.0, show_default=True, type=float,
              help="Seconds between change checks.")
def watch_cmd(path: Path, spec: Path | None, interval: float):
    """Re-audit continuously as the code changes.

    \b
      auditor watch .                       watch the current folder
      auditor watch . --spec spec.yaml      see scope drift appear live

    Leave this running while an agent works. Ctrl+C to stop.
    """
    import yaml
    from rich.console import Console

    from auditor.core.scan import scan_directory
    from auditor.core.watch import watch_directory

    console = Console()
    spec_data = yaml.safe_load(spec.read_text()) if spec else None
    baseline = scan_directory(path, spec_data)

    console.print()
    console.print(f"[bold]Watching {Path(path).resolve()}[/bold]")
    console.print(
        f"[dim]{baseline.file_count} files · {baseline.total_loc} lines"
        + (f" · spec: {baseline.spec_name}" if baseline.spec_name else " · no spec")
        + " · Ctrl+C to stop[/dim]\n"
    )
    _render_scan_table(console, baseline)
    if baseline.coverage_note:
        console.print(f"\n[yellow]Coverage:[/yellow] {baseline.coverage_note}")
    console.print("\n[dim]— waiting for changes —[/dim]")

    try:
        for event in watch_directory(path, spec_data, interval=interval):
            stamp = time.strftime("%H:%M:%S")
            shown = ", ".join(event.changed_files[:3])
            if len(event.changed_files) > 3:
                shown += f" +{len(event.changed_files) - 3} more"
            console.print(f"\n[dim]{stamp}[/dim]  [cyan]{shown}[/cyan]")

            if not event.deltas:
                console.print("  [dim]no change to any metric[/dim]")
                continue

            for d in event.deltas:
                if d.became_measurable:
                    style = BAND_STYLE[d.after_band]
                    console.print(
                        f"  [{style}]▲[/{style}] {d.label} now measurable — "
                        f"[{style}]{d.after:.2f} {BAND_MARK[d.after_band]}[/{style}]"
                    )
                elif d.became_unmeasurable:
                    console.print(f"  [dim]○ {d.label} no longer measurable[/dim]")
                else:
                    arrow = "↑" if d.direction == "worse" else "↓"
                    style = BAND_STYLE[d.after_band] if d.after_band else "white"
                    line = (f"  [{style}]{arrow}[/{style}] {d.label} "
                            f"{d.before:.2f} → [{style}]{d.after:.2f}[/{style}]")
                    if d.changed_band:
                        line += (f"  [{style}]{BAND_MARK[d.before_band]}"
                                 f" → {BAND_MARK[d.after_band]}[/{style}]")
                    console.print(line)

            if event.notable:
                console.print("  [yellow]↳ threshold crossed — worth a look[/yellow]")
    except KeyboardInterrupt:
        console.print("\n[dim]stopped[/dim]\n")


@main.command("run")
@click.option("--spec", required=True, help="Path to spec YAML.")
@click.option("--workflow", required=True, type=click.Choice(CONDITIONS))
@click.option("--run-id", required=True, help="Run identifier (locates the captures dir).")
@click.option("--captures-root", default="data/raw", show_default=True,
              help="Root holding <run-id>/<workflow>/ captured artefacts.")
def run_cmd(spec: str, workflow: str, run_id: str, captures_root: str):
    """Audit one condition and print the AuditResult as JSON."""
    adapters = build_default_adapters(run_id, Path(captures_root))
    adapter = next(a for a in adapters if a.name == workflow)
    result = run_audit(spec, adapter)
    click.echo(result.model_dump_json(indent=2))


@main.command("experiment")
@click.option("--spec", default=None,
              help="Path to one spec YAML (pilot mode only). Ignored if --reps is set.")
@click.option("--run-id", default=None,
              help="Pilot mode: identifier locating <captures-root>/<run-id>/.")
@click.option("--run-label", default=None,
              help="Main-study mode: label for the orchestrated batch.")
@click.option("--reps", default=None, type=int,
              help="Main-study mode: repetitions per (condition × spec). "
                   "Triggers the full pre-registered orchestrator. "
                   "Use --reps 10 for the default dissertation design.")
@click.option("--seed", default=42, show_default=True, type=int,
              help="RNG seed for the run-order shuffle (main-study mode).")
@click.option("--skip", multiple=True,
              help="Conditions to skip in main-study mode "
                   "(e.g. --skip replit_agent --skip antigravity).")
@click.option("--captures-root", default="data/raw", show_default=True,
              help="Pilot mode: root holding pre-captured <run-id>/<condition>/.")
@click.option("--reports-dir", default="data/reports", show_default=True,
              help="Pilot mode: directory the immutable CSV report is written to.")
def experiment_cmd(spec, run_id, run_label, reps, seed, skip,
                   captures_root, reports_dir):
    """Run an experiment and emit a CSV.

    Two modes:

    \b
    PILOT MODE — score pre-captured artefacts (legacy):
        auditor experiment --spec specs/X.yaml --run-id pilot_001

    \b
    MAIN-STUDY MODE — orchestrate the full pre-registered design:
        auditor experiment --reps 10 --run-label main_001
    """
    if reps is not None:
        from auditor.core.study import run_study
        if not run_label:
            raise click.UsageError("--run-label is required with --reps")
        out = run_study(reps=reps, run_label=run_label, seed=seed,
                        skip=tuple(skip), log=click.echo)
        click.echo(f"wrote {out}")
        return
    if not (spec and run_id):
        raise click.UsageError(
            "pilot mode needs --spec and --run-id; main-study mode needs --reps and --run-label")
    adapters = build_default_adapters(run_id, Path(captures_root))
    out = run_experiment(spec, run_id, adapters, reports_dir=reports_dir)
    click.echo(f"wrote {out}")


@main.command("history")
@click.option("--project", default=None,
              help="One folder only: its id, or the folder's name as you would type it.")
@click.option("--limit", default=20, show_default=True, type=int, help="Most recent N scans.")
@click.option("--json", "as_json", is_flag=True, help="Emit the rows as JSON.")
@click.option("--where", is_flag=True, help="Print where the file lives, and stop.")
def history_cmd(project: str | None, limit: int, as_json: bool, where: bool):
    """Every scan this machine has recorded. Local only: none of it has been sent anywhere.

    \b
      auditor history                 the last 20 scans
      auditor history --project src   one folder, with the change between scans
      auditor history --where         the file's location, to read or delete by hand
    """
    import json as _json

    from rich.console import Console
    from rich.table import Table

    console = Console()
    if where:
        click.echo(history.history_path())
        return

    rows = history.trend(project) if project else history.rows()
    if not rows:
        console.print("\n[dim]No scans recorded yet. Run:[/dim] auditor scan .\n")
        return
    rows = rows[-limit:]
    if as_json:
        click.echo(_json.dumps(rows, indent=2))
        return

    table = Table(show_edge=False, header_style="dim", pad_edge=False)
    for column in ("When", "Project", "Files", "Lines", "Security", "Complexity",
                   "Duplication", "Scope drift"):
        table.add_column(column, justify="right" if column not in ("When", "Project") else "left")
    for row in rows:
        metrics = row.get("metrics") or {}

        def cell(name: str) -> str:
            got = metrics.get(name) or {}
            if got.get("value") is None:
                return "[dim]n/a[/dim]"
            moved = (row.get("delta") or {}).get(name)
            arrow = ""
            if isinstance(moved, (int, float)) and abs(moved) >= 0.005:
                arrow = f" [dim]{'+' if moved > 0 else ''}{moved:.2f}[/dim]"
            return f"{got['value']:.2f}{arrow}"

        table.add_row(
            str(row.get("at", ""))[:16].replace("T", " "),
            Path(str(row.get("path", ""))).name or str(row.get("project", ""))[:8],
            str(row.get("files", "")), str(row.get("loc", "")),
            cell("security_density"), cell("complexity_mean"),
            cell("duplication_pct"), cell("hallucinations"))
    console.print()
    console.print(table)
    console.print(f"\n[dim]{len(history.rows())} scan(s) recorded in {history.history_path()}[/dim]")
    console.print("[dim]Nothing has left this machine. `auditor share` is the only thing that "
                  "sends, and only when you run it.[/dim]\n")


@main.command("forget")
@click.option("--project", default=None, help="Delete one folder's rows: its id or its name.")
@click.option("--all", "all_", is_flag=True, help="Delete the whole history and the random ids.")
@click.option("--yes", is_flag=True, help="Skip the confirmation.")
def forget_cmd(project: str | None, all_: bool, yes: bool):
    """Delete recorded scans. Your machine, your file, your decision.

    \b
      auditor forget --project src    remove one folder's rows
      auditor forget --all            remove everything, including the random ids
    """
    if not project and not all_:
        raise click.UsageError("choose --project <name> or --all")
    target = "every recorded scan and the random ids" if all_ else f"the rows for {project!r}"
    if not yes and not click.confirm(f"Delete {target}?"):
        click.echo("Nothing was deleted.")
        return
    removed = history.forget(None if all_ else project)
    click.echo(f"Deleted {removed} row(s).")


@main.command("share")
@click.option("--to", default=None, help="An https:// endpoint. Without it nothing is sent.")
@click.option("--since", default=None, help="Only scans on or after this date (YYYY-MM-DD).")
@click.option("--yes", is_flag=True, help="Send it. Without this the payload is only shown.")
@click.option("--json", "as_json", is_flag=True, help="Print the payload as raw JSON.")
def share_cmd(to: str | None, since: str | None, yes: bool, as_json: bool):
    """Show, and only if you ask, send aggregate readings. Off unless you run it.

    Metric values, counts and language mix leave. A path, a folder name, a specification name,
    a file name or a line of code never does. The payload is printed first, every time.

    \b
      auditor share                          see exactly what would be sent
      auditor share --to https://... --yes   send it
    """
    import json as _json

    from rich.console import Console

    from auditor.core import share as share_mod

    console = Console()
    rows = history.rows()
    if not rows:
        console.print("\n[dim]No scans recorded, so there is nothing to share.[/dim]\n")
        return

    payload = share_mod.build(rows, history.identity()["install"], since)
    leaked = share_mod.leaks(payload, rows)
    if leaked:                       # a widened allowlist must never quietly start sending names
        console.print(f"\n[red]Refused:[/red] the payload would include {', '.join(leaked)}.\n")
        raise SystemExit(1)

    if as_json:
        click.echo(_json.dumps(payload, indent=2))
    else:
        console.print(f"\n[bold]This is everything that would be sent[/bold] "
                      f"[dim]({payload['scans']} scan(s), {payload['projects']} project(s))[/dim]")
        console.print_json(_json.dumps(payload))
        console.print("[dim]No path, no folder name, no specification name, no code.[/dim]")

    def note(message: str) -> None:
        # stderr, so `auditor share --json` pipes cleanly into another tool
        click.echo(message, err=True) if as_json else console.print(f"\n[dim]{message}[/dim]\n")

    if not to:
        note("Nothing was sent. Add --to https://<endpoint> --yes to send it.")
        return
    if not yes:
        note(f"Nothing was sent. Add --yes to send this to {to}.")
        return
    try:
        status = share_mod.send(to, payload)
    except Exception as exc:                          # noqa: BLE001 - the reason is for the user
        console.print(f"\n[red]Not sent:[/red] {exc}\n")
        raise SystemExit(1) from exc
    console.print(f"\n[green]Sent[/green] {payload['scans']} scan(s) to {to} ({status}).\n")
