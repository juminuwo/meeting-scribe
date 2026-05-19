from meeting_scribe.summarize import TEMPLATES, _build_prompt, summarize


def test_build_prompt_includes_default_sections():
    prompt = _build_prompt("default", participants=["You"])
    for title, _ in TEMPLATES["default"]:
        assert f"## {title}" in prompt


def test_build_prompt_includes_1on1_sections():
    prompt = _build_prompt("1on1", participants=["You", "Other 1"])
    expected = {title for title, _ in TEMPLATES["1on1"]}
    for title in expected:
        assert f"## {title}" in prompt
    # Default-only section that 1on1 does not have
    assert "## Open questions" not in prompt


def test_build_prompt_lists_participants():
    prompt = _build_prompt("default", participants=["You", "Other 1", "Other 2"])
    assert "Participants in this meeting: You, Other 1, Other 2" in prompt


def test_build_prompt_handles_empty_participants():
    prompt = _build_prompt("default", participants=[])
    assert "Participants in this meeting: Unknown" in prompt


def test_build_prompt_unknown_template_falls_back_to_default():
    prompt = _build_prompt("nope-not-a-template", participants=["You"])
    for title, _ in TEMPLATES["default"]:
        assert f"## {title}" in prompt


def test_build_prompt_bans_overview_section_in_rules():
    prompt = _build_prompt("default", participants=["You"])
    # Belt-and-braces: the rules block must explicitly forbid auto-Overview,
    # otherwise LLMs tend to add it back even with the section list.
    assert "Overview" in prompt
    assert "no Overview" in prompt or "no Overview, Introduction" in prompt


def test_build_prompt_includes_format_rules():
    prompt = _build_prompt("default", participants=["You"])
    assert "Format rules:" in prompt
    assert "markdown only" in prompt


def test_summarize_uses_codex_output_last_message(monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        output_path = cmd[cmd.index("--output-last-message") + 1]
        with open(output_path, "w") as f:
            f.write("## Decisions\n- Use Codex\n")
        return subprocess_result(returncode=0, stdout="hook noise", stderr="")

    monkeypatch.setattr("subprocess.run", fake_run)

    summary = summarize("[00:00:01] **You:** use codex", participants=["You"])

    assert summary == "## Decisions\n- Use Codex"
    cmd, kwargs = calls[0]
    assert cmd[:2] == ["codex", "exec"]
    assert "--output-last-message" in cmd
    assert "--ephemeral" in cmd
    assert kwargs["input"] == "[00:00:01] **You:** use codex"
    assert kwargs["capture_output"] is True


def subprocess_result(returncode: int, stdout: str, stderr: str):
    class Result:
        pass

    result = Result()
    result.returncode = returncode
    result.stdout = stdout
    result.stderr = stderr
    return result
