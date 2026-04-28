def assign_speakers(segments: list[dict], diarization: list[dict]) -> list[dict]:
    out = []
    for seg in segments:
        best_speaker = None
        best_overlap = 0.0
        for turn in diarization:
            overlap = max(
                0.0, min(seg["end"], turn["end"]) - max(seg["start"], turn["start"])
            )
            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = turn["speaker"]
        out.append({**seg, "speaker": best_speaker or "Unknown"})
    return out


def remap_speakers(segments: list[dict]) -> list[dict]:
    mapping: dict[str, str] = {}
    out = []
    for seg in segments:
        raw = seg["speaker"]
        if raw not in mapping:
            mapping[raw] = f"Other {len(mapping) + 1}"
        out.append({**seg, "speaker": mapping[raw]})
    return out


def merge_streams(
    mic_segments: list[dict], desktop_segments: list[dict]
) -> list[dict]:
    mic = [{**s, "speaker": "You"} for s in mic_segments]
    combined = mic + desktop_segments
    combined.sort(key=lambda s: s["start"])
    return combined
