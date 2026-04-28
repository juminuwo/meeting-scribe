from meeting_scribe.summarize import TEMPLATES, _build_prompt


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
    # otherwise Claude tends to add it back even with the section list.
    assert "Overview" in prompt
    assert "no Overview" in prompt or "no Overview, Introduction" in prompt


def test_build_prompt_includes_format_rules():
    prompt = _build_prompt("default", participants=["You"])
    assert "Format rules:" in prompt
    assert "markdown only" in prompt
