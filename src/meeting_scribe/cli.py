import time

import typer

from . import audio, pipeline

app = typer.Typer(
    help="Record, transcribe, diarize, and summarize meetings — locally.",
    no_args_is_help=True,
)


@app.command()
def start(
    slug: str = typer.Argument(
        None,
        help="Short label for the meeting (used in the output filename). "
        "Defaults to the current HHMM, so the output file becomes "
        "YYYY-MM-DD-HHMM.md.",
    ),
) -> None:
    """Begin recording mic + desktop audio."""
    if not slug:
        slug = time.strftime("%H%M")
    session = audio.start(slug)
    typer.echo(f"Recording started: {session['id']} ({slug})")
    typer.echo(f"  mic     -> {session['mic_path']}")
    typer.echo(f"  desktop -> {session['desktop_path']}")
    typer.echo("Run `meeting-scribe stop` when done.")


@app.command()
def stop() -> None:
    """Stop recording, then transcribe + diarize + summarize."""
    session = audio.stop()
    typer.echo(f"Recording stopped: {session['id']}")
    pipeline.process(session)


@app.command()
def process(
    session_id: str = typer.Argument(
        None,
        help="Session id (folder name under ~/.local/state/meeting-scribe/audio/). Defaults to latest.",
    ),
    slug: str = typer.Option(
        None, "--slug", help="Override the slug used for the output filename."
    ),
) -> None:
    """Re-run transcribe + diarize + summarize against a previously recorded session."""
    session = audio.load_session(session_id)
    if slug:
        session["slug"] = slug
    typer.echo(f"Processing session: {session['id']} ({session.get('slug')})")
    pipeline.process(session)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
