import logging
import os
import threading
import queue
from typing import Optional, Tuple


class TTSManager:
    """Threaded TTS manager: enqueues text and speaks in a background thread."""

    def __init__(self, voice_gender: str = "female"):
        self.enabled = True
        self.engine = None
        self._queue = queue.Queue()
        self._worker = None
        self._ready = threading.Event()
        # start background worker which will create the engine on the worker thread
        self._worker = threading.Thread(target=self._worker_loop, args=(voice_gender,), daemon=True)
        self._worker.start()
        # wait briefly for the engine to be ready; do not block indefinitely
        if not self._ready.wait(timeout=5):
            logging.warning("TTS engine did not initialize within timeout; TTS may be unavailable")

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

    def _speak_with_fresh_engine(self, text: str, voice_gender: str):
        import pyttsx3

        engine = pyttsx3.init()
        self.engine = engine
        try:
            self.set_voice(voice_gender)
        except Exception:
            logging.debug("Failed to set TTS voice on fresh engine")

        try:
            logging.info("TTS speaking (chars=%d)", len(text))
            engine.say(text)
            engine.runAndWait()
            logging.info("TTS finished speaking")
        finally:
            try:
                engine.stop()
            except Exception:
                pass
            self.engine = None

    def _worker_loop(self, voice_gender: str):
        # Initialize pyttsx3 on this thread to respect COM STA requirements on Windows
        try:
            import pyttsx3
        except Exception:
            logging.warning("pyttsx3 not installed; TTS disabled")
            self.enabled = False
            self._ready.set()
            return

        try:
            self.engine = pyttsx3.init()
            try:
                self.set_voice(voice_gender)
            except Exception:
                logging.debug("Failed to set TTS voice on worker thread")
            logging.info("TTS engine ready on worker thread")
            self._ready.set()
        except Exception as e:
            logging.warning("Failed to initialize TTS engine on worker thread: %s", e)
            self.enabled = False
            self._ready.set()
            return

        logging.info("TTS worker loop starting")
        while True:
            item: Optional[Tuple[Optional[str], Optional[threading.Event]]] = None
            text = None
            done_event = None
            try:
                logging.debug("TTS worker waiting for item (queue size=%d)", self._queue.qsize())
                item = self._queue.get()
                logging.debug("TTS worker dequeued item")
                if isinstance(item, tuple):
                    text, done_event = item
                else:
                    text = item
                if text is None:
                    logging.info("TTS worker received shutdown signal")
                    break
                try:
                    self._speak_with_fresh_engine(text, voice_gender)
                except Exception as e:
                    logging.warning("TTS speak failed during worker: %s", e)
            except Exception as e:
                logging.exception("Unexpected error in TTS worker loop: %s", e)
            finally:
                if done_event:
                    done_event.set()
                try:
                    self._queue.task_done()
                except Exception:
                    pass

    def status(self) -> dict:
        """Return diagnostic status for the TTS manager."""
        return {
            "enabled": bool(self.enabled),
            "engine": bool(self.engine),
            "worker_alive": bool(self._worker and self._worker.is_alive()),
            "queue_size": self._queue.qsize() if hasattr(self, "_queue") else 0,
        }

    def speak(self, text: str) -> None:
        if not self.enabled:
            logging.info("TTS not enabled or engine missing; skip speak")
            return
        try:
            # enqueue text and wait until the worker has actually spoken it
            done_event = threading.Event()
            self._queue.put((text, done_event))
            logging.info("TTS enqueued %d chars (queue size=%d)", len(text), self._queue.qsize())
            if not done_event.wait(timeout=60):
                logging.warning("TTS speak timed out waiting for worker to finish")
        except Exception as e:
            logging.warning("Failed to enqueue TTS text: %s", e)

    def shutdown(self):
        try:
            self._queue.put((None, None))
            if self._worker:
                self._worker.join(timeout=2)
        except Exception:
            pass


def create_default_tts() -> Optional[TTSManager]:
    if os.getenv("VOICE_ENABLED", "false").lower() not in ("1", "true", "yes"):
        logging.info("VOICE_ENABLED is false; not creating TTS")
        return None
    gender = os.getenv("VOICE_GENDER", "female")
    t = TTSManager(voice_gender=gender)
    if not getattr(t, "enabled", False):
        logging.warning("TTSManager created but not enabled; falling back to no TTS")
        return None
    return t
