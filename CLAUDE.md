# meeting-scribe

Local pipeline that records mic + desktop audio during a meeting, transcribes
both tracks, diarizes other speakers, and writes a summary + transcript into
the Obsidian vault.

## Stack

- **uv** for project + dependency management (Python 3.12)
- **typer** CLI exposing `start` and `stop` subcommands
- **ffmpeg** + PipeWire (via the pulse compat layer) for audio capture
- **faster-whisper** (`large-v3`, CUDA float16) for transcription
- **pyannote.audio 3.1** for speaker diarization on the desktop track
- **`claude -p`** (headless Claude Code) for the post-meeting summary

## Module layout

```
src/meeting_scribe/
  config.py      paths, model names, env loading
  audio.py       start/stop ffmpeg capture, session state file
  transcribe.py  faster-whisper wrapper (lazy model load)
  diarize.py     pyannote pipeline wrapper (lazy + CUDA)
  merge.py       overlap-based speaker assignment, stream merge
  summarize.py   subprocess wrapper around `claude -p`
  pipeline.py    orchestrates the post-stop processing
  cli.py         typer app + entry point
```

## Commands

```sh
uv run meeting-scribe start "weekly sync"   # begin recording
uv run meeting-scribe stop                  # end + process + write to vault
```

## Output

One markdown file per meeting at:

```
/home/howis/Documents/online-personal/Personal/Meetings/YYYY-MM-DD-<slug>.md
```

With a `# Summary` (from `claude -p`) and `# Transcript` (timestamped, speaker-labeled).
Raw audio is kept under `~/.local/state/meeting-scribe/audio/<session-id>/`.

## Setup (one-time)

1. Install `ffmpeg` and `pactl` (likely already present):
   `yay -S ffmpeg libpulse`
2. Accept gated models on HuggingFace while logged in:
   - `huggingface.co/pyannote/speaker-diarization-3.1`
   - `huggingface.co/pyannote/segmentation-3.0`
3. Create a HF token (Read scope, or fine-grained with
   "Read access to contents of all public gated repos").
4. Put it in `.env` at the project root:
   ```
   HF_TOKEN=hf_...
   ```
5. `uv sync` to install deps.

## Speaker labeling convention

- Mic track is labeled **"You"** unconditionally — captured from your own input.
- Desktop track is diarized; raw `SPEAKER_00`, `SPEAKER_01`, ... are remapped
  to **"Other 1"**, **"Other 2"**, ... in order of first appearance.

## Decisions log

- **Two-stream capture** (mic + desktop monitor) instead of one mixed stream:
  free self-vs-other split, halves the diarization problem.
- **Pre-record blank slug fallback**: `start` accepts an optional slug and
  defaults to "untitled" so a missing argument doesn't block recording.
- **Headless Claude Code** for summarization (Max plan, no API key).
  Subprocess pipes the transcript via stdin to `claude -p <prompt>`.
- **Lazy model load** in `transcribe.py` and `diarize.py` so `start` is fast;
  models only spin up when `stop` runs.
