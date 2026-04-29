import json
from pathlib import Path

import pytest

from meeting_scribe import audio


@pytest.fixture
def fake_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    """Set up a session-on-disk with no real ffmpeg processes.

    Monkeypatches the active SESSION_FILE and silences the kill/wait helpers
    so cancel() exercises the file/dir cleanup path without touching real PIDs.
    """
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    session_dir = state_dir / "audio" / "2026-04-29-100000"
    session_dir.mkdir(parents=True)
    (session_dir / "mic.wav").write_bytes(b"fake")
    (session_dir / "desktop.wav").write_bytes(b"fake")
    (session_dir / "session.json").write_text("{}")

    session_file = state_dir / "current.json"
    session_meta = {
        "id": "2026-04-29-100000",
        "slug": "test",
        "template": "default",
        "mic_pid": 999999,
        "desktop_pid": 999998,
        "mic_path": str(session_dir / "mic.wav"),
        "desktop_path": str(session_dir / "desktop.wav"),
        "session_dir": str(session_dir),
    }
    session_file.write_text(json.dumps(session_meta))

    monkeypatch.setattr(audio, "SESSION_FILE", session_file)
    monkeypatch.setattr(audio, "_wait_for_exit", lambda pid, timeout=5.0: None)

    def fake_kill(pid: int, sig: int) -> None:
        # Pretend processes always exited cleanly; never actually signal.
        raise ProcessLookupError(pid)

    monkeypatch.setattr(audio.os, "kill", fake_kill)
    return session_meta


def test_cancel_removes_session_file(fake_session: dict):
    audio.cancel()
    assert not audio.SESSION_FILE.exists()


def test_cancel_removes_audio_directory(fake_session: dict):
    audio.cancel()
    assert not Path(fake_session["session_dir"]).exists()


def test_cancel_returns_session_with_cancelled_at(fake_session: dict):
    out = audio.cancel()
    assert out["id"] == fake_session["id"]
    assert "cancelled_at" in out


def test_cancel_when_no_session_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(audio, "SESSION_FILE", tmp_path / "nope.json")
    with pytest.raises(RuntimeError, match="No recording in progress"):
        audio.cancel()
