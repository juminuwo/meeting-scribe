import subprocess

PROMPT = """You are summarizing a meeting transcript.

Output sections, in order, omitting any that have no content:

## Overview
2-3 sentences on what the meeting was about.

## Decisions
Bulleted list of decisions reached.

## Action items
Bulleted list. Each item: who is doing it, what, by when (if mentioned).

## Open questions
Bulleted list of unresolved questions or follow-ups.

Be concise. Skip filler. Use markdown only — no preamble."""


def summarize(transcript: str) -> str:
    result = subprocess.run(
        ["claude", "-p", PROMPT],
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
