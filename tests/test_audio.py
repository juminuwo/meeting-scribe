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


@pytest.fixture
def crash_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Simulated state dir with current.json + crashed/, no real ffmpeg."""
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    crashed_dir = state_dir / "crashed"
    session_file = state_dir / "current.json"
    monkeypatch.setattr(audio, "SESSION_FILE", session_file)
    monkeypatch.setattr(audio, "CRASHED_DIR", crashed_dir)
    monkeypatch.setattr(audio, "_wait_for_exit", lambda pid, timeout=5.0: None)

    # Track which PIDs the test marks as alive.
    alive: set[int] = set()

    def fake_kill(pid: int, sig: int) -> None:
        if sig == 0 and pid not in alive:
            raise ProcessLookupError(pid)
        if sig != 0 and pid not in alive:
            raise ProcessLookupError(pid)

    monkeypatch.setattr(audio.os, "kill", fake_kill)

    def write_session(session_id: str, mic_pid: int, desktop_pid: int) -> dict:
        meta = {
            "id": session_id,
            "slug": "test",
            "template": "default",
            "started_at": 1714485000,
            "mic_pid": mic_pid,
            "desktop_pid": desktop_pid,
            "mic_path": str(state_dir / "audio" / session_id / "mic.wav"),
            "desktop_path": str(state_dir / "audio" / session_id / "desktop.wav"),
            "session_dir": str(state_dir / "audio" / session_id),
        }
        session_file.write_text(json.dumps(meta))
        return meta

    return {
        "state_dir": state_dir,
        "session_file": session_file,
        "crashed_dir": crashed_dir,
        "alive": alive,
        "write_session": write_session,
    }


def test_session_status_idle_when_no_state_file(crash_state):
    state, session = audio.session_status()
    assert state == "idle"
    assert session is None


def test_session_status_recording_when_both_pids_alive(crash_state):
    crash_state["write_session"]("2026-04-30-100000", mic_pid=111, desktop_pid=222)
    crash_state["alive"].update({111, 222})
    state, session = audio.session_status()
    assert state == "recording"
    assert session["id"] == "2026-04-30-100000"


def test_session_status_crashed_when_mic_dead(crash_state):
    crash_state["write_session"]("2026-04-30-110000", mic_pid=111, desktop_pid=222)
    crash_state["alive"].add(222)  # only desktop alive
    state, _ = audio.session_status()
    assert state == "crashed"


def test_session_status_crashed_when_desktop_dead(crash_state):
    crash_state["write_session"]("2026-04-30-120000", mic_pid=111, desktop_pid=222)
    crash_state["alive"].add(111)
    state, _ = audio.session_status()
    assert state == "crashed"


def test_session_status_crashed_when_both_dead(crash_state):
    crash_state["write_session"]("2026-04-30-130000", mic_pid=111, desktop_pid=222)
    state, _ = audio.session_status()
    assert state == "crashed"


def test_move_to_crashed_clears_session_file_and_writes_crashed(crash_state):
    meta = crash_state["write_session"](
        "2026-04-30-140000", mic_pid=111, desktop_pid=222
    )
    audio._move_to_crashed(meta)
    assert not crash_state["session_file"].exists()
    crashed_path = crash_state["crashed_dir"] / "2026-04-30-140000.json"
    assert crashed_path.exists()
    assert json.loads(crashed_path.read_text())["id"] == "2026-04-30-140000"


def test_list_crashed_returns_oldest_first(crash_state):
    crash_state["crashed_dir"].mkdir(parents=True, exist_ok=True)
    for sid in ("2026-04-30-090000", "2026-04-30-100000", "2026-04-30-080000"):
        (crash_state["crashed_dir"] / f"{sid}.json").write_text(
            json.dumps({"id": sid, "slug": sid})
        )
    out = audio.list_crashed()
    assert [s["id"] for s in out] == [
        "2026-04-30-080000",
        "2026-04-30-090000",
        "2026-04-30-100000",
    ]


def test_list_crashed_empty_when_dir_missing(crash_state):
    assert audio.list_crashed() == []


def test_pop_crashed_removes_file(crash_state):
    crash_state["crashed_dir"].mkdir(parents=True, exist_ok=True)
    path = crash_state["crashed_dir"] / "2026-04-30-150000.json"
    path.write_text("{}")
    audio.pop_crashed("2026-04-30-150000")
    assert not path.exists()


def test_pop_crashed_silent_when_missing(crash_state):
    audio.pop_crashed("does-not-exist")
