import json
import os
import signal
import subprocess
import time
from pathlib import Path

from .config import AUDIO_DIR, MIC_SOURCE, SAMPLE_RATE, SESSION_FILE, STATE_DIR


def get_default_sink() -> str:
    result = subprocess.run(
        ["pactl", "get-default-sink"], capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def _spawn_ffmpeg(source: str, out_path: Path, channels: int) -> subprocess.Popen:
    return subprocess.Popen(
        [
            "ffmpeg",
            "-loglevel", "error",
            "-f", "pulse",
            "-i", source,
            "-ac", str(channels),
            "-ar", str(SAMPLE_RATE),
            "-y",
            str(out_path),
        ],
        stdin=subprocess.DEVNULL,
    )


def start(slug: str, template: str = "default") -> dict:
    if SESSION_FILE.exists():
        raise RuntimeError(
            f"Recording already in progress (state file: {SESSION_FILE}). "
            "Run `meeting-scribe stop` first, or delete the file if it's stale."
        )

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    session_id = time.strftime("%Y-%m-%d-%H%M%S")
    session_dir = AUDIO_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    mic_path = session_dir / "mic.wav"
    desktop_path = session_dir / "desktop.wav"

    monitor = f"{get_default_sink()}.monitor"

    mic_proc = _spawn_ffmpeg(MIC_SOURCE, mic_path, channels=1)
    desktop_proc = _spawn_ffmpeg(monitor, desktop_path, channels=2)

    session = {
        "id": session_id,
        "slug": slug,
        "template": template,
        "started_at": time.time(),
        "mic_pid": mic_proc.pid,
        "desktop_pid": desktop_proc.pid,
        "mic_path": str(mic_path),
        "desktop_path": str(desktop_path),
        "session_dir": str(session_dir),
    }
    payload = json.dumps(session, indent=2)
    SESSION_FILE.write_text(payload)
    (session_dir / "session.json").write_text(payload)
    return session


def load_session(session_id: str | None = None) -> dict:
    if session_id is None:
        candidates = sorted(
            (p for p in AUDIO_DIR.iterdir() if p.is_dir()),
            key=lambda p: p.name,
            reverse=True,
        )
        if not candidates:
            raise RuntimeError(f"No sessions found under {AUDIO_DIR}")
        session_dir = candidates[0]
        session_id = session_dir.name
    else:
        session_dir = AUDIO_DIR / session_id
        if not session_dir.is_dir():
            raise RuntimeError(f"Session not found: {session_dir}")

    metadata_file = session_dir / "session.json"
    if metadata_file.exists():
        return json.loads(metadata_file.read_text())

    return {
        "id": session_id,
        "slug": session_id,
        "mic_path": str(session_dir / "mic.wav"),
        "desktop_path": str(session_dir / "desktop.wav"),
        "session_dir": str(session_dir),
    }


def _wait_for_exit(pid: int, timeout: float = 5.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.1)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def stop() -> dict:
    if not SESSION_FILE.exists():
        raise RuntimeError("No recording in progress.")

    session = json.loads(SESSION_FILE.read_text())

    for key in ("mic_pid", "desktop_pid"):
        try:
            os.kill(session[key], signal.SIGINT)
        except ProcessLookupError:
            pass

    for key in ("mic_pid", "desktop_pid"):
        _wait_for_exit(session[key])

    SESSION_FILE.unlink()
    session["stopped_at"] = time.time()
    return session
