# meeting-scribe

Local pipeline: records mic + desktop audio, transcribes both tracks with
faster-whisper on CUDA, diarizes the desktop track with pyannote, and writes
a summary (via headless `claude -p`) + speaker-labeled transcript into the
Obsidian vault.

## Stack

- **uv** for project + dependency management (Python 3.12)
- **typer** CLI: `start` / `stop` / `process` / `setup`
- **questionary** for the interactive template picker and setup wizard
- **ffmpeg** + PipeWire (via the pulse compat layer) for audio capture
- **faster-whisper** (default `large-v3`, CUDA float16) for transcription
- **pyannote.audio 3.1** for speaker diarization on the desktop track
- **`claude -p`** (headless Claude Code, Max plan) for the post-meeting summary

## Module layout

```
src/meeting_scribe/
  __init__.py       imports _cuda_preload before anything else
  _cuda_preload.py  preload bundled cu13 .so files for torch JIT NVRTC
  config.py         paths, model names, env loading
  audio.py          ffmpeg capture, session state, load_session()
  transcribe.py     faster-whisper wrapper (lazy model load)
  diarize.py        pyannote pipeline wrapper (lazy + CUDA)
  merge.py          overlap-based speaker assignment, stream merge
  summarize.py      TEMPLATES + _build_prompt + claude -p subprocess
  pipeline.py       post-stop orchestrator (transcribe → diarize → summarize)
  wizard.py         interactive `setup` flow
  cli.py            typer app + entry point
```

## Commands

```sh
meeting-scribe setup                  # interactive config wizard, writes .env
meeting-scribe start                  # interactive template picker, slug = HHMM
meeting-scribe start --template 1on1  # skip the picker
meeting-scribe stop                   # finish + run pipeline + write to vault
meeting-scribe process [session-id]   # rerun pipeline against existing audio
meeting-scribe process -t 1on1        # re-summarize latest under a different template
```

`meeting-scribe` is also installed globally as `~/.local/bin/meeting-scribe`
(a tiny wrapper that exports `~/.local/bin` onto PATH then `exec uv run`s the
project — necessary because i3blocks/cron/systemd inherit a stripped PATH).

## Configuration (.env at project root)

| Key                              | Purpose                                        | Default                                   |
|----------------------------------|------------------------------------------------|-------------------------------------------|
| `HF_TOKEN`                       | HuggingFace read token (pyannote gated repos)  | required                                  |
| `MEETING_SCRIBE_VAULT_DIR`       | Where meeting markdown is written              | `~/Documents/Meetings`                    |
| `MEETING_SCRIBE_MIC_SOURCE`      | PulseAudio source name for the mic             | USB C-Media constant (override on others) |
| `MEETING_SCRIBE_WHISPER_MODEL`   | faster-whisper model id                        | `large-v3`                                |
| `MEETING_SCRIBE_WHISPER_DEVICE`  | `cuda` or `cpu`                                | `cuda`                                    |
| `MEETING_SCRIBE_WHISPER_COMPUTE` | `float16` / `float32` / `int8` / `int8_float16`| `float16`                                 |

`meeting-scribe setup` prompts for these, auto-detects mic devices via
`pactl`, and suggests Whisper settings based on detected VRAM.

## Output

Per meeting:

- Markdown: `<VAULT_DIR>/YYYY-MM-DD-<slug>.md` with `# Summary` + `# Transcript`
- Audio archive: `~/.local/state/meeting-scribe/audio/<session-id>/{mic,desktop}.wav`
- Session metadata: `<session-dir>/session.json` (slug, template, paths)

## Speaker labeling

- Mic track is labeled **"You"** unconditionally (captured from the mic device,
  so by definition you are the speaker).
- Desktop track is diarized; raw `SPEAKER_00`, `SPEAKER_01`, ... are remapped
  to **"Other 1"**, **"Other 2"**, ... in order of first appearance.
- Diarization uses `DiarizeOutput.exclusive_speaker_diarization` (the
  non-overlapping variant pyannote provides for downstream transcription).

## Templates

Defined in `summarize.TEMPLATES`. Two ship today:

- `default` — Decisions / Action items / Open questions
- `1on1` — Updates / Wins & challenges / Goals & progress / Feedback / Action items

The system prompt enforces: markdown only, no preamble, no auto-Overview/
Introduction/Participants section, h2 headings in template order, skip empty
sections instead of writing "None." filler. Pattern is loosely modeled on
Hyprnote's `enhance.system.md.jinja` (one prompt + per-template section list
injected; we just have fewer templates).

## Tests

```sh
uv run pytest -q
```

Cover pure-logic modules: `merge`, `pipeline` helpers, `audio.load_session`,
`summarize._build_prompt`, `wizard._parse_mic_sources` / `_suggest_whisper`.
The heavy modules (`transcribe`, `diarize`, the actual `claude -p` call) are
intentionally not tested — they need real models or the live CLI.

## i3blocks integration

The status-bar block lives in `endeavouros-dotfiles`, not in this repo:

- Block script: `~/.config/i3/scripts/meeting-scribe-block`
- i3blocks config entry: `[meeting_scribe]` in `~/.config/i3/i3blocks.conf` (signal 14)
- State file: `~/.local/state/meeting-scribe/state` (`idle | recording | processing`)
- Block log: `~/.local/state/meeting-scribe/block.log`

Right-click cycles state-aware menus (rofi/dmenu) to start (template picker)
or stop a recording. Glyphs: 🎙 / 🔴 / ⏳.

## Decisions log

- **Two-stream capture** (mic + desktop monitor) instead of one mixed stream:
  free self-vs-other split, halves the diarization problem.
- **Lazy model load** in `transcribe`/`diarize` so `start` returns fast;
  whisper + pyannote only initialize when `stop` runs.
- **Headless Claude Code** for summarization (Max plan, no API key). The
  transcript is piped via stdin to `claude -p <prompt>`.
- **Default slug = HHMM** (not "untitled"). Output file already prepends the
  date, so the slug only needs to disambiguate within a day.
- **Explicit `MIC_SOURCE`** instead of `pulse:default` — the system default
  source on Linux desktops is unreliably set to a sink monitor (recording the
  speakers) instead of a real mic. Discovered the hard way: the first smoke
  test produced two identical desktop-audio tracks.
- **`_cuda_preload` module**: torch 2.11+cu130 ships NVRTC under
  `nvidia/cu13/lib/` but doesn't add it to the loader's search path. JIT
  kernels then fail with `libnvrtc-builtins.so.13.0 not found`. Preloading
  the cu13 .so files with `RTLD_GLOBAL` at package import fixes it.
- **Per-session `session.json`** alongside the active `current.json`. The
  active pointer is consumed by `stop`, but the per-session file persists so
  `process` can re-run the pipeline against captured audio without
  re-recording.
- **`exclusive_speaker_diarization`** instead of `speaker_diarization` from
  pyannote's `DiarizeOutput`: the non-overlapping variant is what the
  pyannote authors specifically recommend for downstream transcription
  merging — exactly our use case.

## Common gotchas

- **Three HF gates**, not two: `pyannote/speaker-diarization-3.1`,
  `pyannote/segmentation-3.0`, **and** `pyannote/speaker-diarization-community-1`.
  All three need to be accepted while logged into HuggingFace before the
  pipeline can download weights.
- **i3blocks reload**: SIGUSR1 only re-runs existing blocks; new blocks
  require a full i3blocks restart (`pkill i3blocks` and let i3 respawn, or
  `$mod+Shift+r` to restart i3 in place).
- **PATH in non-interactive contexts** (i3blocks, cron, systemd) does not
  include `~/.local/bin`. The global wrapper at `~/.local/bin/meeting-scribe`
  exports it before invoking `uv run` so `uv` and `claude` both resolve.
