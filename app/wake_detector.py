import logging
from typing import Optional

from app.microphone import record_wake_audio
from app.stt import transcribe_audio

WAKE_WORDS = (
    "hey roha",
    "roha",
    "hello roha",
    "hi roha",
)


def wait_for_wake_word(stop_event: Optional[object] = None):
    print("\n👂 Listening for wake word...")

    while True:
        if stop_event is not None and getattr(stop_event, "is_set", lambda: False)():
            return None

        audio_path = record_wake_audio()
        if stop_event is not None and getattr(stop_event, "is_set", lambda: False)():
            return None

        raw_text = ""
        try:
            raw_text = transcribe_audio(audio_path)
        except Exception:
            logging.exception("Transcription failed during wake detection")
            raw_text = ""

        if not raw_text:
            continue

        text = raw_text.lower().strip()

        if not text:
            continue

        print(f"Heard: {text}")

        if any(word in text for word in WAKE_WORDS):
            print("✅ Wake word detected!")
            return text