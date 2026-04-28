from meeting_scribe.merge import assign_speakers, merge_streams, remap_speakers


def test_assign_speakers_picks_max_overlap():
    segments = [{"start": 1.0, "end": 4.0, "text": "hello"}]
    diarization = [
        {"start": 0.0, "end": 2.0, "speaker": "SPEAKER_00"},
        {"start": 2.0, "end": 5.0, "speaker": "SPEAKER_01"},
    ]
    out = assign_speakers(segments, diarization)
    assert out[0]["speaker"] == "SPEAKER_01"


def test_assign_speakers_no_overlap_yields_unknown():
    segments = [{"start": 10.0, "end": 11.0, "text": "hi"}]
    diarization = [{"start": 0.0, "end": 1.0, "speaker": "SPEAKER_00"}]
    out = assign_speakers(segments, diarization)
    assert out[0]["speaker"] == "Unknown"


def test_assign_speakers_preserves_segment_fields():
    segments = [{"start": 0.0, "end": 1.0, "text": "hi"}]
    diarization = [{"start": 0.0, "end": 1.0, "speaker": "SPEAKER_00"}]
    out = assign_speakers(segments, diarization)
    assert out[0]["text"] == "hi"
    assert out[0]["start"] == 0.0
    assert out[0]["end"] == 1.0


def test_remap_speakers_assigns_in_first_appearance_order():
    segments = [
        {"start": 0.0, "end": 1.0, "text": "a", "speaker": "SPEAKER_03"},
        {"start": 1.0, "end": 2.0, "text": "b", "speaker": "SPEAKER_00"},
        {"start": 2.0, "end": 3.0, "text": "c", "speaker": "SPEAKER_03"},
    ]
    out = remap_speakers(segments)
    assert [s["speaker"] for s in out] == ["Other 1", "Other 2", "Other 1"]


def test_remap_speakers_handles_empty_input():
    assert remap_speakers([]) == []


def test_merge_streams_labels_mic_as_you_and_sorts():
    mic = [{"start": 2.0, "end": 3.0, "text": "mic-mid"}]
    desktop = [
        {"start": 0.0, "end": 1.0, "text": "d-first", "speaker": "Other 1"},
        {"start": 5.0, "end": 6.0, "text": "d-last", "speaker": "Other 1"},
    ]
    out = merge_streams(mic, desktop)
    assert [s["text"] for s in out] == ["d-first", "mic-mid", "d-last"]
    you_segment = next(s for s in out if s["text"] == "mic-mid")
    assert you_segment["speaker"] == "You"


def test_merge_streams_does_not_mutate_inputs():
    mic = [{"start": 0.0, "end": 1.0, "text": "hi"}]
    desktop = []
    merge_streams(mic, desktop)
    assert "speaker" not in mic[0]
