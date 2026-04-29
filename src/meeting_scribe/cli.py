import time

import questionary
import typer

from . import audio, pipeline, wizard
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


@app.command()
def setup() -> None:
    """Interactive configuration wizard — writes to .env."""
    wizard.run()


def main() -> None:
    app()


if __name__ == "__main__":
    main()
