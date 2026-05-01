import json
import time
from pathlib import Path

import questionary
import typer

from . import audio, wizard
from .summarize import TEMPLATES

app = typer.Typer(
    help="Record, transcribe, diarize, and summarize meetings — locally.",
    no_args_is_help=True,
)


def _pick_template_interactively() -> str:
    choice = questionary.select(
        "Meeting type:",
        choices=list(TEMPLATES.keys()),
        default="default",
    ).ask()
    if choice is None:
        raise typer.Exit(1)
    return choice


@app.command()
def start(
    slug: str = typer.Argument(
        None,
        help="Short label for the meeting (used in the output filename). "
        "Defaults to the current HHMM, so the output file becomes "
        "YYYY-MM-DD-HHMM.md.",
    ),
    template: str = typer.Option(
        None,
        "--template",
        "-t",
        help=f"Meeting template ({', '.join(TEMPLATES)}). "
        "If omitted, you'll be prompted interactively.",
    ),
) -> None:
    """Begin recording mic + desktop audio."""
    if not slug:
        slug = time.strftime("%H%M")
    if template is None:
        template = _pick_template_interactively()
    elif template not in TEMPLATES:
        raise typer.BadParameter(
            f"Unknown template '{template}'. Valid: {', '.join(TEMPLATES)}"
        )
    session = audio.start(slug, template=template)
    typer.echo(f"Recording started: {session['id']} ({slug}, template={template})")
    typer.echo(f"  mic     -> {session['mic_path']}")
    typer.echo(f"  desktop -> {session['desktop_path']}")
    typer.echo("Run `meeting-scribe stop` when done.")


@app.command()
def stop() -> None:
    """Stop recording, then transcribe + diarize + summarize."""
    from . import pipeline

    session = audio.stop()
    typer.echo(f"Recording stopped: {session['id']}")
    pipeline.process(session)


@app.command()
def cancel() -> None:
    """Abort an in-progress recording and discard the captured audio."""
    session = audio.cancel()
    typer.echo(f"Recording cancelled and discarded: {session['id']}")


@app.command()
def process(
    session_id: str = typer.Argument(
        None,
        help="Session id (folder name under ~/.local/state/meeting-scribe/audio/). Defaults to latest.",
    ),
    slug: str = typer.Option(
        None, "--slug", help="Override the slug used for the output filename."
    ),
    template: str = typer.Option(
        None,
        "--template",
        "-t",
        help=f"Override the template for this re-process ({', '.join(TEMPLATES)}).",
    ),
) -> None:
    """Re-run transcribe + diarize + summarize against a previously recorded session."""
    from . import pipeline

    session = audio.load_session(session_id)
    if slug:
        session["slug"] = slug
    if template is not None:
        if template not in TEMPLATES:
            raise typer.BadParameter(
                f"Unknown template '{template}'. Valid: {', '.join(TEMPLATES)}"
            )
        session["template"] = template
    typer.echo(
        f"Processing session: {session['id']} ({session.get('slug')}, "
        f"template={session.get('template', 'default')})"
    )
    pipeline.process(session)


def _crashed_duration_seconds(session: dict) -> int:
    """Approximate crashed-recording duration from the mic WAV's mtime."""
    mic_path = Path(session.get("mic_path", ""))
    started_at = session.get("started_at")
    if not mic_path.exists() or started_at is None:
        return 0
    return max(0, int(mic_path.stat().st_mtime - started_at))


def _crashed_summary(session: dict) -> dict:
    return {
        "id": session["id"],
        "slug": session.get("slug", session["id"]),
        "template": session.get("template", "default"),
        "started_at": session.get("started_at", 0),
        "duration_seconds": _crashed_duration_seconds(session),
    }


@app.command()
def status() -> None:
    """Print whether a recording is active and how many crashed sessions are queued."""
    state, session = audio.session_status()
    crashed = audio.list_crashed()
    typer.echo(f"state: {state}")
    if session is not None:
        typer.echo(f"  session: {session['id']} ({session.get('slug')})")
    typer.echo(f"crashed: {len(crashed)}")
    for s in crashed:
        summary = _crashed_summary(s)
        mins = summary["duration_seconds"] // 60
        typer.echo(f"  {summary['id']} — {summary['slug']} (~{mins}m)")


@app.command()
def crashed(
    json_output: bool = typer.Option(
        False, "--json", help="Emit the list as JSON for tooling (i3blocks)."
    ),
) -> None:
    """List crashed recordings waiting to be recovered."""
    sessions = audio.list_crashed()
    summaries = [_crashed_summary(s) for s in sessions]
    if json_output:
        typer.echo(json.dumps(summaries))
        return
    if not summaries:
        typer.echo("No crashed sessions.")
        return
    for s in summaries:
        mins = s["duration_seconds"] // 60
        typer.echo(f"{s['id']} — {s['slug']} (template={s['template']}, ~{mins}m)")


@app.command()
def recover(
    session_id: str = typer.Argument(
        None, help="Crashed session id. Omit with --all to process every crashed session."
    ),
    all_: bool = typer.Option(
        False, "--all", help="Process every queued crashed session."
    ),
) -> None:
    """Run transcribe + diarize + summarize against crashed recording(s)."""
    from . import pipeline

    if all_ and session_id:
        raise typer.BadParameter("Pass either a session id or --all, not both.")
    if not all_ and not session_id:
        raise typer.BadParameter("Pass a session id or --all.")

    if all_:
        sessions = audio.list_crashed()
        if not sessions:
            typer.echo("No crashed sessions.")
            return
        targets = sessions
    else:
        targets = [s for s in audio.list_crashed() if s["id"] == session_id]
        if not targets:
            raise typer.BadParameter(f"No crashed session with id '{session_id}'.")

    failures = 0
    for session in targets:
        typer.echo(
            f"Recovering {session['id']} ({session.get('slug')}, "
            f"template={session.get('template', 'default')})"
        )
        try:
            pipeline.process(session)
        except Exception as e:
            failures += 1
            typer.echo(f"  failed: {e}; leaving in queue")
            continue
        audio.pop_crashed(session["id"])

    if failures:
        raise typer.Exit(1)


@app.command()
def setup() -> None:
    """Interactive configuration wizard — writes to .env."""
    wizard.run()


def main() -> None:
    app()


if __name__ == "__main__":
    main()
