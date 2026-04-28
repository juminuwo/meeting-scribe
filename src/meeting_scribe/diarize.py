from pathlib import Path

import torch
from pyannote.audio import Pipeline

from .config import DIARIZATION_MODEL, HF_TOKEN

_pipeline: Pipeline | None = None


def _get_pipeline() -> Pipeline:
    global _pipeline
    if _pipeline is None:
        if not HF_TOKEN:
            raise RuntimeError(
                "HF_TOKEN missing. Add it to .env in the project root "
                "(see CLAUDE.md for HuggingFace setup steps)."
            )
        _pipeline = Pipeline.from_pretrained(DIARIZATION_MODEL, token=HF_TOKEN)
        if torch.cuda.is_available():
            _pipeline.to(torch.device("cuda"))
    return _pipeline


def diarize(audio_path: Path) -> list[dict]:
    pipeline = _get_pipeline()
    result = pipeline(str(audio_path))
    annotation = result.exclusive_speaker_diarization
    return [
        {"start": float(turn.start), "end": float(turn.end), "speaker": speaker}
        for turn, _, speaker in annotation.itertracks(yield_label=True)
    ]
