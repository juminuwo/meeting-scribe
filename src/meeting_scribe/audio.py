import json
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path

from .config import (
    AUDIO_DIR,
    CRASHED_DIR,
    MIC_SOURCE,
    SAMPLE_RATE,
    SESSION_FILE,
    STATE_DIR,
)


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


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def session_status() -> tuple[str, dict | None]:
    """Return ("idle"|"recording"|"crashed", session_or_None).

    A session is "crashed" when current.json exists but at least one of its
    ffmpeg PIDs is no longer running — i.e. the recording stopped without
    the user invoking `stop`.
    """
    if not SESSION_FILE.exists():
        return "idle", None
    session = json.loads(SESSION_FILE.read_text())
    mic_alive = _pid_alive(session.get("mic_pid", -1))
    desktop_alive = _pid_alive(session.get("desktop_pid", -1))
    if mic_alive and desktop_alive:
        return "recording", session
    return "crashed", session


def _move_to_crashed(session: dict) -> Path:
    """Kill any survivor ffmpeg, move current.json into crashed/, return new path."""
    for key in ("mic_pid", "desktop_pid"):
        try:
            os.kill(session[key], signal.SIGINT)
        except (ProcessLookupError, KeyError):
            pass
    for key in ("mic_pid", "desktop_pid"):
        try:
            _wait_for_exit(session[key])
        except KeyError:
            pass

    CRASHED_DIR.mkdir(parents=True, exist_ok=True)
    crashed_path = CRASHED_DIR / f"{session['id']}.json"
    crashed_path.write_text(json.dumps(session, indent=2))
    if SESSION_FILE.exists():
        SESSION_FILE.unlink()
    return crashed_path


def list_crashed() -> list[dict]:
    """All crashed session metadata, oldest first."""
    if not CRASHED_DIR.is_dir():
        return []
    out = []
    for path in sorted(CRASHED_DIR.iterdir()):
        if path.suffix != ".json":
            continue
        out.append(json.loads(path.read_text()))
    return out


def pop_crashed(session_id: str) -> None:
    path = CRASHED_DIR / f"{session_id}.json"
    if path.exists():
        path.unlink()


def start(slug: str, template: str = "default") -> dict:
    status, session = session_status()
    if status == "recording":
        raise RuntimeError(
            f"Recording already in progress (state file: {SESSION_FILE}). "
            "Run `meeting-scribe stop` first."
        )
    if status == "crashed" and session is not None:
        _move_to_crashed(session)

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


def cancel() -> dict:
    """Discard an in-progress recording: kill ffmpeg, drop the audio + state."""
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

    session_dir = Path(session["session_dir"])
    if session_dir.is_dir():
        shutil.rmtree(session_dir)

    SESSION_FILE.unlink()
    session["cancelled_at"] = time.time()
    return session
