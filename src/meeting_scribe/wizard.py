"""Interactive `meeting-scribe setup` wizard.

Reads existing values from .env (if any), prompts for each setting with the
current value as default, and writes selections back to .env. Anything the
user doesn't touch is left as-is — this is non-destructive and re-runnable.
"""

import shutil
import subprocess
from pathlib import Path

import questionary
import typer
from dotenv import dotenv_values, set_key

from . import config

ENV_PATH = config.PROJECT_DIR / ".env"

WHISPER_MODELS = ["tiny", "base", "small", "medium", "large-v3", "distil-large-v3"]
WHISPER_COMPUTES = ["float16", "float32", "int8", "int8_float16"]


def _parse_mic_sources(pactl_output: str) -> list[str]:
    """Filter `pactl list short sources` output to real input devices.

    Drops monitor sources (sink loopbacks); they record what's playing through
    speakers, not what's spoken into a mic.
    """
    out = []
    for line in pactl_output.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        name = parts[1]
        if ".monitor" in name:
            continue
        out.append(name)
    return out


def _suggest_whisper(vram_gb: float | None) -> tuple[str, str]:
    """Pick a sensible (model, compute) pair given detected VRAM."""
    if vram_gb is None:
        return ("medium", "int8")
    if vram_gb >= 6:
        return ("large-v3", "float16")
    if vram_gb >= 4:
        return ("large-v3", "int8")
    return ("small", "int8")


def _list_mic_sources() -> list[str]:
    if not shutil.which("pactl"):
        return []
    result = subprocess.run(
        ["pactl", "list", "short", "sources"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    return _parse_mic_sources(result.stdout)


def _detect_vram_gb() -> float | None:
    if not shutil.which("nvidia-smi"):
        return None
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        first = result.stdout.strip().splitlines()[0]
        return float(first) / 1024
    except (subprocess.CalledProcessError, ValueError, IndexError):
        return None


def _ask_text(prompt: str, default: str) -> str:
    answer = questionary.text(prompt, default=default).ask()
    if answer is None:
        raise typer.Exit(1)
    return answer.strip()


def _ask_select(prompt: str, choices: list[str], default: str) -> str:
    if default not in choices:
        default = choices[0]
    answer = questionary.select(prompt, choices=choices, default=default).ask()
    if answer is None:
        raise typer.Exit(1)
    return answer


def run() -> None:
    typer.echo("=== meeting-scribe setup ===\n")
    ENV_PATH.touch(exist_ok=True)
    current = dotenv_values(ENV_PATH)

    # 1. Vault path
    default_vault = current.get("MEETING_SCRIBE_VAULT_DIR") or str(config.VAULT_DIR)
    vault = _ask_text("Vault path (where meeting markdown files land):", default_vault)
    set_key(str(ENV_PATH), "MEETING_SCRIBE_VAULT_DIR", vault)

    # 2. Mic source
    sources = _list_mic_sources()
    if not sources:
        typer.echo(
            "  No real input devices detected via pactl. "
            "Skipping mic prompt — set MEETING_SCRIBE_MIC_SOURCE manually later."
        )
    else:
        default_mic = current.get("MEETING_SCRIBE_MIC_SOURCE") or config.MIC_SOURCE
        mic = _ask_select("Microphone source:", sources, default_mic)
        set_key(str(ENV_PATH), "MEETING_SCRIBE_MIC_SOURCE", mic)

    # 3. Whisper model + compute (with VRAM-based suggestion)
    vram = _detect_vram_gb()
    suggested_model, suggested_compute = _suggest_whisper(vram)
    if vram is not None:
        typer.echo(
            f"\n  Detected ~{vram:.1f} GB VRAM. "
            f"Suggested Whisper: {suggested_model} ({suggested_compute}).\n"
        )
    else:
        typer.echo(
            "\n  No NVIDIA GPU detected. "
            f"Suggested Whisper: {suggested_model} ({suggested_compute}).\n"
        )

    default_model = current.get("MEETING_SCRIBE_WHISPER_MODEL") or suggested_model
    model = _ask_select("Whisper model:", WHISPER_MODELS, default_model)
    set_key(str(ENV_PATH), "MEETING_SCRIBE_WHISPER_MODEL", model)

    default_compute = (
        current.get("MEETING_SCRIBE_WHISPER_COMPUTE") or suggested_compute
    )
    compute = _ask_select("Whisper compute type:", WHISPER_COMPUTES, default_compute)
    set_key(str(ENV_PATH), "MEETING_SCRIBE_WHISPER_COMPUTE", compute)

    # 4. HuggingFace token (only ask if missing)
    if not current.get("HF_TOKEN"):
        token = questionary.password(
            "HuggingFace token (read scope; needed for pyannote diarization):"
        ).ask()
        if token is None:
            raise typer.Exit(1)
        if token:
            set_key(str(ENV_PATH), "HF_TOKEN", token)
    else:
        typer.echo("  HF_TOKEN already set — leaving as-is. Edit .env to change.")

    typer.echo(f"\nWrote {ENV_PATH}")
    typer.echo(
        "Vault directory will be created on first recording if it doesn't exist."
    )
