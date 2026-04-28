from meeting_scribe.pipeline import _format_timestamp, _format_transcript, _slugify


def test_slugify_lowercases_and_dasherizes():
    assert _slugify("Weekly Sync Meeting") == "weekly-sync-meeting"


def test_slugify_strips_punctuation():
    assert _slugify("Q1 review: planning!") == "q1-review-planning"


def test_slugify_empty_input_falls_back():
    assert _slugify("") == "untitled"
    assert _slugify("   !!!  ") == "untitled"


def test_slugify_truncates_long_input():
    long_input = "a" * 100
    out = _slugify(long_input)
    assert len(out) == 60


def test_format_timestamp_zero():
    assert _format_timestamp(0) == "00:00:00"


def test_format_timestamp_seconds_minutes_hours():
    assert _format_timestamp(5) == "00:00:05"
    assert _format_timestamp(65) == "00:01:05"
    assert _format_timestamp(3661) == "01:01:01"


def test_format_timestamp_truncates_fractional():
    assert _format_timestamp(1.9) == "00:00:01"


def test_format_transcript_renders_speaker_lines():
    segments = [
        {"start": 0.0, "end": 1.0, "speaker": "You", "text": "hi"},
        {"start": 65.0, "end": 70.0, "speaker": "Other 1", "text": "hello"},
    ]
    out = _format_transcript(segments)
    assert "[00:00:00] **You:** hi" in out
    assert "[00:01:05] **Other 1:** hello" in out


def test_format_transcript_empty():
    assert _format_transcript([]) == ""
