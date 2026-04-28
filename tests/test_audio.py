import json
from pathlib import Path

import pytest

from meeting_scribe import audio


@pytest.fixture
def audio_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    d = tmp_path / "audio"
    d.mkdir()
    monkeypatch.setattr(audio, "AUDIO_DIR", d)
    return d


def _make_session_dir(audio_dir: Path, session_id: str) -> Path:
    session_dir = audio_dir / session_id
    session_dir.mkdir()
    (session_dir / "mic.wav").write_bytes(b"")
    (session_dir / "desktop.wav").write_bytes(b"")
    return session_dir


def test_load_session_reads_metadata_when_present(audio_dir: Path):
    session_dir = _make_session_dir(audio_dir, "2026-04-28-100000")
    metadata = {
        "id": "2026-04-28-100000",
        "slug": "weekly-sync",
        "mic_path": str(session_dir / "mic.wav"),
        "desktop_path": str(session_dir / "desktop.wav"),
        "session_dir": str(session_dir),
    }
    (session_dir / "session.json").write_text(json.dumps(metadata))

    out = audio.load_session("2026-04-28-100000")
    assert out["slug"] == "weekly-sync"


def test_load_session_reconstructs_when_metadata_missing(audio_dir: Path):
    session_dir = _make_session_dir(audio_dir, "2026-04-28-110000")
    out = audio.load_session("2026-04-28-110000")
    assert out["id"] == "2026-04-28-110000"
    assert out["slug"] == "2026-04-28-110000"
    assert out["mic_path"] == str(session_dir / "mic.wav")
    assert out["desktop_path"] == str(session_dir / "desktop.wav")


def test_load_session_default_picks_latest_by_name(audio_dir: Path):
    _make_session_dir(audio_dir, "2026-04-28-100000")
    _make_session_dir(audio_dir, "2026-04-28-220000")
    _make_session_dir(audio_dir, "2026-04-28-150000")

    out = audio.load_session()
    assert out["id"] == "2026-04-28-220000"


def test_load_session_unknown_id_raises(audio_dir: Path):
    with pytest.raises(RuntimeError, match="Session not found"):
        audio.load_session("does-not-exist")


def test_load_session_no_sessions_raises(audio_dir: Path):
    with pytest.raises(RuntimeError, match="No sessions found"):
        audio.load_session()
