from pathlib import Path

from faster_whisper import WhisperModel

from .config import WHISPER_COMPUTE, WHISPER_DEVICE, WHISPER_MODEL

_model: WhisperModel | None = None


def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        _model = WhisperModel(
            WHISPER_MODEL, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE
        )
    return _model


def transcribe(audio_path: Path) -> list[dict]:
    model = _get_model()
    segments, _info = model.transcribe(
        str(audio_path),
        vad_filter=True,
        word_timestamps=False,
    )
    return [
        {"start": float(s.start), "end": float(s.end), "text": s.text.strip()}
        for s in segments
        if s.text and s.text.strip()
    ]
