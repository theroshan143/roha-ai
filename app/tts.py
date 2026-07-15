import logging
import os
from typing import Optional


class TTSManager:
    def __init__(self, voice_gender: str = "female"):
        self.enabled = True
        self.engine = None
        try:
            import pyttsx3
        except Exception:
            logging.warning("pyttsx3 not installed; TTS disabled")
            self.enabled = False
            return

        try:
            self.engine = pyttsx3.init()
            self.set_voice(voice_gender)
        except Exception as e:
            logging.warning("Failed to initialize TTS engine: %s", e)
            self.enabled = False

    def set_voice(self, gender: str):
        if not self.engine:
            return
        try:
            voices = self.engine.getProperty("voices")
            # prefer voices with 'female' or common female names
            preferred = None
            for v in voices:
                name = (v.name or "").lower()
                if gender.lower() in name or "zira" in name or "sara" in name or "frau" in name:
                    preferred = v
                    break

            if not preferred and voices:
                # fallback: choose one whose gender attr exists
                preferred = voices[0]

            if preferred:
                self.engine.setProperty("voice", preferred.id)
        except Exception:
            logging.debug("Could not set voice; using default")

    def speak(self, text: str) -> None:
        if not self.enabled or not self.engine:
            return
        try:
            self.engine.say(text)
            self.engine.runAndWait()
        except Exception as e:
            logging.warning("TTS speak failed: %s", e)


def create_default_tts() -> Optional[TTSManager]:
    if os.getenv("VOICE_ENABLED", "false").lower() not in ("1", "true", "yes"):
        return None
    gender = os.getenv("VOICE_GENDER", "female")
    return TTSManager(voice_gender=gender)
