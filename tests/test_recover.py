import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from meeting_scribe import audio, cli, pipeline


@pytest.fixture
def crashed_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    crashed_dir = tmp_path / "crashed"
    crashed_dir.mkdir()
    monkeypatch.setattr(audio, "CRASHED_DIR", crashed_dir)

    def write(session_id: str) -> dict:
        meta = {
            "id": session_id,
            "slug": f"slug-{session_id}",
            "template": "default",
            "started_at": 1714485000,
            "mic_path": str(tmp_path / session_id / "mic.wav"),
            "desktop_path": str(tmp_path / session_id / "desktop.wav"),
            "session_dir": str(tmp_path / session_id),
        }
        (crashed_dir / f"{session_id}.json").write_text(json.dumps(meta))
        return meta

    return {"dir": crashed_dir, "write": write}


def test_recover_one_calls_pipeline_and_pops(
    crashed_state, monkeypatch: pytest.MonkeyPatch
):
    crashed_state["write"]("2026-04-30-100000")
    crashed_state["write"]("2026-04-30-110000")
    seen: list[str] = []
    monkeypatch.setattr(pipeline, "process", lambda s: seen.append(s["id"]))

    result = CliRunner().invoke(cli.app, ["recover", "2026-04-30-100000"])
    assert result.exit_code == 0, result.output
    assert seen == ["2026-04-30-100000"]
    assert not (crashed_state["dir"] / "2026-04-30-100000.json").exists()
    assert (crashed_state["dir"] / "2026-04-30-110000.json").exists()


def test_recover_all_processes_every_crashed(
    crashed_state, monkeypatch: pytest.MonkeyPatch
):
    crashed_state["write"]("2026-04-30-100000")
    crashed_state["write"]("2026-04-30-110000")
    seen: list[str] = []
    monkeypatch.setattr(pipeline, "process", lambda s: seen.append(s["id"]))

    result = CliRunner().invoke(cli.app, ["recover", "--all"])
    assert result.exit_code == 0, result.output
    assert sorted(seen) == ["2026-04-30-100000", "2026-04-30-110000"]
    assert list(crashed_state["dir"].iterdir()) == []


def test_recover_pipeline_failure_keeps_in_queue(
    crashed_state, monkeypatch: pytest.MonkeyPatch
):
    crashed_state["write"]("2026-04-30-100000")

    def fail(_session):
        raise RuntimeError("boom")

    monkeypatch.setattr(pipeline, "process", fail)

    result = CliRunner().invoke(cli.app, ["recover", "--all"])
    assert result.exit_code == 1
    assert (crashed_state["dir"] / "2026-04-30-100000.json").exists()


def test_recover_unknown_id_errors(crashed_state):
    result = CliRunner().invoke(cli.app, ["recover", "nope"])
    assert result.exit_code != 0
    assert "No crashed session" in result.output


def test_recover_requires_id_or_all(crashed_state):
    result = CliRunner().invoke(cli.app, ["recover"])
    assert result.exit_code != 0


def test_crashed_command_json_output(crashed_state):
    crashed_state["write"]("2026-04-30-100000")
    result = CliRunner().invoke(cli.app, ["crashed", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload[0]["id"] == "2026-04-30-100000"
    assert payload[0]["slug"] == "slug-2026-04-30-100000"
    assert "duration_seconds" in payload[0]


def test_crashed_command_empty_json(crashed_state):
    result = CliRunner().invoke(cli.app, ["crashed", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.output) == []
