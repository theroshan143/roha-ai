import logging
import os
import threading
import queue
from typing import Optional


class TTSManager:
    """Threaded TTS manager: enqueues text and speaks in a background thread."""

    def __init__(self, voice_gender: str = "female"):
        self.enabled = True
        self.engine = None
        self._queue = queue.Queue()
        self._worker = None
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
            return

        # start background worker
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()

    def set_voice(self, gender: str):
        if not self.engine:
            return
        try:
            voices = self.engine.getProperty("voices")
            preferred = None
            for v in voices:
                name = (v.name or "").lower()
                if gender.lower() in name or "zira" in name or "sara" in name or "frau" in name:
                    preferred = v
                    break

            if not preferred and voices:
                preferred = voices[0]

            if preferred:
                try:
                    self.engine.setProperty("voice", preferred.id)
                except Exception:
                    logging.debug("Could not set voice id; using default")
        except Exception:
            logging.debug("Could not enumerate voices; using default")

    def _worker_loop(self):
        while True:
            try:
                text = self._queue.get()
                if text is None:
                    break
                if not self.engine:
                    continue
                try:
                    logging.debug("TTS speaking: %s", text[:120])
                    self.engine.say(text)
                    self.engine.runAndWait()
                    logging.debug("TTS finished speaking")
                except Exception as e:
                    logging.warning("TTS speak failed during worker: %s", e)
            finally:
                self._queue.task_done()

    def speak(self, text: str) -> None:
        if not self.enabled or not self.engine:
            logging.debug("TTS not enabled or engine missing; skip speak")
            return
        try:
            # enqueue text for background playback
            self._queue.put(text)
        except Exception as e:
            logging.warning("Failed to enqueue TTS text: %s", e)

    def shutdown(self):
        try:
            self._queue.put(None)
            if self._worker:
                self._worker.join(timeout=2)
        except Exception:
            pass


def create_default_tts() -> Optional[TTSManager]:
    if os.getenv("VOICE_ENABLED", "false").lower() not in ("1", "true", "yes"):
        return None
    gender = os.getenv("VOICE_GENDER", "female")
    return TTSManager(voice_gender=gender)
