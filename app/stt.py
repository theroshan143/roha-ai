import logging
from functools import lru_cache
from typing import Optional

from app.config import WHISPER_MODEL


@lru_cache(maxsize=1)
def _get_whisper_model():
    try:
        from faster_whisper import WhisperModel
    except Exception as e:
        logging.exception("faster_whisper not available: %s", e)
        raise
    logging.info("Loading Whisper model: %s", WHISPER_MODEL)
    return WhisperModel(WHISPER_MODEL)


def transcribe_audio(audio_path: str) -> str:
    """Transcribe audio at path and return cleaned text. Returns empty string on failure."""
    try:
        model = _get_whisper_model()
        segments, info = model.transcribe(audio_path, language="en", beam_size=5)
        text = " ".join(getattr(s, "text", "") for s in segments).strip()
        return text
    except Exception:
        logging.exception("Transcription failed for %s", audio_path)
        return ""