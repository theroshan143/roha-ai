from app.microphone import record_wake_audio
from app.stt import transcribe_audio
import logging

WAKE_WORDS = (
    "hey roha",
    "roha",
    "hello roha",
    "hi roha",
)


def wait_for_wake_word():
    print("\n👂 Listening for wake word...")

    while True:
        audio_path = record_wake_audio()
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
            return