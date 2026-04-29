# meeting-scribe

Local, open-source meeting-notes pipeline for Linux: records mic + desktop
audio, transcribes both tracks, separates speakers, and drops a summarized
markdown file into your Obsidian vault. Everything runs on your own
hardware — transcription with faster-whisper on CUDA, speaker diarization
with pyannote, summary via Claude Code in headless mode.

```text
┌──────────┐  ┌────────────┐  ┌────────────┐  ┌──────────┐
│  mic.wav │─▶│  whisper   │─▶│   speaker  │─▶│ markdown │
│ desk.wav │  │ transcribe │  │  alignment │  │  + claude│
└──────────┘  └────────────┘  └────────────┘  │   summary│
     ▲             ▲                           └──────────┘
     │             │                                ▲
  ffmpeg +      pyannote                            │
   PipeWire    (desktop only)                Obsidian vault
```

## What it does

- **Captures two streams** independently: your mic and the desktop audio
  monitor. Free self-vs-other split, no acoustic-echo work.
- **Transcribes both** with faster-whisper (`large-v3` by default).
- **Diarizes the desktop track** with pyannote 3.1, so multiple remote
  participants are separated into "Other 1", "Other 2", etc.
- **Summarizes** by piping the merged transcript to `claude -p` with a
  template-driven prompt (default or 1:1).
- **Writes one markdown file** per meeting to your vault, with frontmatter,
  the summary, and the full timestamped transcript.

## Requirements

- Linux with PipeWire (the PulseAudio compat layer is fine)
- NVIDIA GPU with ≥4 GB VRAM, recent driver, CUDA-capable wheels
- `ffmpeg`, `pactl` on PATH
- [`uv`](https://docs.astral.sh/uv/) for Python project management
- [Claude Code](https://docs.claude.com/en/docs/claude-code/overview) on PATH
  (`claude -p` is what generates the summary; works with a Max plan, no API
  key required)
- A HuggingFace account with read-token access to the gated pyannote models

## Install

```sh
git clone <this-repo> ~/git/meeting-scribe
cd ~/git/meeting-scribe
uv sync
```

### Accept the HuggingFace gates (one-time, three repos)

While logged into huggingface.co, click "Agree and access repository" on each:

1. https://huggingface.co/pyannote/speaker-diarization-3.1
2. https://huggingface.co/pyannote/segmentation-3.0
3. https://huggingface.co/pyannote/speaker-diarization-community-1

### Run the setup wizard

```sh
uv run meeting-scribe setup
```

The wizard prompts for vault path, mic source (auto-detected), Whisper model
(suggested based on detected VRAM), Whisper compute type, and a HuggingFace
token if `.env` doesn't already have one. All values land in `.env`.

### Optional: install globally

```sh
cat > ~/.local/bin/meeting-scribe <<'EOF'
#!/usr/bin/env bash
export PATH="$HOME/.local/bin:$PATH"
exec uv run --project ~/git/meeting-scribe meeting-scribe "$@"
EOF
chmod +x ~/.local/bin/meeting-scribe
```

The `PATH` export matters for non-interactive callers (i3blocks, cron) that
don't see `~/.local/bin` in their inherited environment.

## Usage

```sh
meeting-scribe start              # arrow-key picker for template, slug = HHMM
meeting-scribe start --template 1on1
meeting-scribe start "weekly sync" -t default
meeting-scribe stop               # ends recording, runs the full pipeline
meeting-scribe cancel             # abort in-progress recording, discard the audio
meeting-scribe process            # re-run pipeline against the latest session
meeting-scribe process <id> -t 1on1   # re-summarize a specific session under another template
```

Output filename: `<vault>/YYYY-MM-DD-<slug>.md`. The audio is archived under
`~/.local/state/meeting-scribe/audio/<session-id>/`.

## Templates

Two ship today:

| Template  | Sections                                                            |
|-----------|---------------------------------------------------------------------|
| `default` | Decisions · Action items · Open questions                            |
| `1on1`    | Updates · Wins & challenges · Goals & progress · Feedback · Action items |

To add a new one, edit `TEMPLATES` in `src/meeting_scribe/summarize.py`.
Each template is a list of `(section title, section description)` tuples;
the prompt builder injects them into the user message and Claude renders
them as h2 sections in order. The system rules (no preamble, no auto-
Overview, skip empty sections instead of writing "None." filler) apply
across all templates.

## Configuration

All runtime knobs live in `.env`. The wizard is the friendly way to set them,
but you can also edit by hand:

```ini
HF_TOKEN=hf_...
MEETING_SCRIBE_VAULT_DIR=/home/you/Documents/Meetings
MEETING_SCRIBE_MIC_SOURCE=alsa_input.usb-...
MEETING_SCRIBE_WHISPER_MODEL=large-v3
MEETING_SCRIBE_WHISPER_DEVICE=cuda
MEETING_SCRIBE_WHISPER_COMPUTE=float16
```

`MIC_SOURCE` matters: the PulseAudio default source on most Linux desktops
points at a sink monitor (recording your speakers, not your mic). Use
`pactl list short sources` to find a real `alsa_input.*` entry, or just run
`meeting-scribe setup` which filters monitor sources for you.

## i3blocks status-bar integration (optional)

A separate block script lives in the dotfiles repo. It shows 🎙 when idle,
🔴 while recording, ⏳ while the pipeline runs. Right-click cycles through
state-aware rofi/dmenu menus to start (with template picker), stop, or cancel
a recording. State file: `~/.local/state/meeting-scribe/state`.

## Project layout

```
src/meeting_scribe/
  config.py         env-driven config + paths
  audio.py          ffmpeg capture + session state
  transcribe.py     faster-whisper wrapper
  diarize.py        pyannote wrapper
  merge.py          speaker assignment + stream merge
  summarize.py      TEMPLATES + claude -p subprocess
  pipeline.py       post-stop orchestrator
  wizard.py         `setup` interactive flow
  cli.py            typer app
  _cuda_preload.py  torch JIT NVRTC fix (preload bundled cu13 .so files)
tests/              pure-logic unit tests
```

## Tests

```sh
uv run pytest -q
```

35 tests across `merge`, `pipeline` helpers, `audio.load_session`,
`summarize._build_prompt`, and `wizard._parse_mic_sources`/
`_suggest_whisper`. The heavy paths (transcription, diarization, the live
`claude -p` call) are deliberately not unit-tested.

## Troubleshooting

| Symptom                                                          | Fix                                                                                       |
|------------------------------------------------------------------|-------------------------------------------------------------------------------------------|
| `Library libcublas.so.12 is not found`                           | `uv add nvidia-cublas-cu12 'nvidia-cudnn-cu12>=9,<10'`                                    |
| `libnvrtc-builtins.so.13.0 is not found`                         | Already handled by `_cuda_preload`; if you removed it, the cu13 libs need to be on `LD_LIBRARY_PATH` |
| `GatedRepoError` on a pyannote model                             | Accept the user agreement on huggingface.co for that specific repo                        |
| Mic track contains desktop audio instead of your voice           | `MIC_SOURCE` is set to a `.monitor` source. Re-run `meeting-scribe setup` and pick an `alsa_input.*` |
| `i3blocks: meeting-scribe ... uv: not found`                     | Use the global wrapper at `~/.local/bin/meeting-scribe` that exports `PATH` before exec    |
| `meeting-scribe stop` fails after a successful start             | The session metadata is on disk; run `meeting-scribe process` to re-run the pipeline      |

## License

No license declared. If you fork or share publicly, add one.
