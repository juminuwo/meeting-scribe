import subprocess

TEMPLATES: dict[str, list[tuple[str, str]]] = {
    "default": [
        ("Decisions", "Bulleted list of decisions reached during the meeting."),
        (
            "Action items",
            "Each item: who is doing it, what they're doing, by when (if mentioned).",
        ),
        ("Open questions", "Bulleted list of unresolved questions or follow-ups."),
    ],
    "1on1": [
        ("Updates", "What each person has been working on since the last sync."),
        ("Wins & challenges", "Things going well and obstacles raised."),
        ("Goals & progress", "Progress on stated goals; new goals proposed."),
        ("Feedback", "Feedback shared in either direction."),
        (
            "Action items",
            "Each item: who, what, by when (if mentioned).",
        ),
    ],
}

_FORMAT_RULES = (
    "Format rules:\n"
    '- Output is markdown only. No preamble, no commentary, no "Here\'s the summary" intro.\n'
    "- Use ## (h2) for section headings, exactly as listed below, in the order listed.\n"
    '- Skip a heading entirely if its section has no real content. Do not write "None." filler.\n'
    "- Do not invent extra sections (no Overview, Introduction, or Participants section) "
    "unless one is listed below.\n"
    '- Quote names exactly as they appear in the transcript ("You", "Other 1", etc.).'
)


def _build_prompt(template: str, participants: list[str]) -> str:
    sections = TEMPLATES.get(template, TEMPLATES["default"])
    section_block = "\n\n".join(
        f"## {title}\n{description}" for title, description in sections
    )
    participants_line = ", ".join(participants) if participants else "Unknown"
    return (
        "Summarize the following meeting transcript.\n\n"
        f"{_FORMAT_RULES}\n\n"
        f"Participants in this meeting: {participants_line}.\n\n"
        "Sections to fill, in order:\n\n"
        f"{section_block}"
    )


def summarize(
    transcript: str,
    template: str = "default",
    participants: list[str] | None = None,
) -> str:
    prompt = _build_prompt(template, participants or [])
    result = subprocess.run(
        ["claude", "-p", prompt],
        input=transcript,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"`claude -p` failed (exit {result.returncode}):\n{result.stderr}"
        )
    return result.stdout.strip()
