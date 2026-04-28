import re
from datetime import date
from pathlib import Path

from . import diarize, merge, summarize, transcribe
from .config import VAULT_DIR


def _format_timestamp(seconds: float) -> str:
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _format_transcript(segments: list[dict]) -> str:
    return "\n\n".join(
        f"[{_format_timestamp(s['start'])}] **{s['speaker']}:** {s['text']}"
        for s in segments
    )


def _slugify(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9\s-]", "", text.lower())
    cleaned = re.sub(r"\s+", "-", cleaned).strip("-")
    return cleaned[:60] or "untitled"


def process(session: dict) -> Path:
    mic_path = Path(session["mic_path"])
    desktop_path = Path(session["desktop_path"])

    print("Transcribing mic track...")
    mic_segments = transcribe.transcribe(mic_path)
    print(f"  {len(mic_segments)} segments")

    print("Transcribing desktop track...")
    desktop_segments = transcribe.transcribe(desktop_path)
    print(f"  {len(desktop_segments)} segments")

    if desktop_segments:
        print("Diarizing desktop track...")
        diarization = diarize.diarize(desktop_path)
        print(f"  {len(diarization)} speaker turns")
        desktop_segments = merge.assign_speakers(desktop_segments, diarization)
        desktop_segments = merge.remap_speakers(desktop_segments)

    combined = merge.merge_streams(mic_segments, desktop_segments)
    transcript_text = _format_transcript(combined)

    template = session.get("template", "default")
    participants = sorted({s["speaker"] for s in combined})
    print(f"Summarizing via `claude -p` (template: {template})...")
    summary = summarize.summarize(
        transcript_text, template=template, participants=participants
    )

    today = date.today().isoformat()
    slug = _slugify(session["slug"])
    out_path = VAULT_DIR / f"{today}-{slug}.md"
    VAULT_DIR.mkdir(parents=True, exist_ok=True)

    out_path.write_text(
        f"---\n"
        f"date: {today}\n"
        f"source: meeting-scribe\n"
        f"audio: {session['session_dir']}\n"
        f"---\n\n"
        f"# Summary\n\n{summary}\n\n"
        f"# Transcript\n\n{transcript_text}\n"
    )
    print(f"\nWrote {out_path}")
    return out_path
