import logging
import os
import threading
import queue
from typing import Optional, Tuple, List, Dict


def _load_pyttsx3():
    import pyttsx3

    return pyttsx3


def list_available_voices() -> List[Dict[str, str]]:
    """Return the voices exposed by pyttsx3 on this machine."""
    try:
        pyttsx3 = _load_pyttsx3()
    except Exception:
        logging.warning("pyttsx3 not installed; cannot list voices")
        return []

    engine = None
    try:
        engine = pyttsx3.init()
        voices = engine.getProperty("voices") or []
        results: List[Dict[str, str]] = []
        for index, voice in enumerate(voices):
            results.append(
                {
                    "index": str(index),
                    "id": str(getattr(voice, "id", "") or ""),
                    "name": str(getattr(voice, "name", "") or f"Voice {index}"),
                }
            )
        return results
    except Exception as exc:
        logging.warning("Failed to list voices: %s", exc)
        return []
    finally:
        try:
            if engine:
                engine.stop()
        except Exception:
            pass


def preview_voice(voice_id: str, sample_text: str) -> bool:
    """Speak a short sample using a specific voice id."""
    completed = threading.Event()
    result = {"ok": False}

    def worker():
        try:
            pyttsx3 = _load_pyttsx3()
        except Exception:
            logging.warning("pyttsx3 not installed; cannot preview voice")
            completed.set()
            return

        engine = None
        try:
            engine = pyttsx3.init()
            if voice_id:
                engine.setProperty("voice", voice_id)
            logging.info("Previewing voice: %s", voice_id)
            engine.say(sample_text)
            engine.runAndWait()
            result["ok"] = True
        except Exception as exc:
            logging.warning("Failed to preview voice: %s", exc)
        finally:
            try:
                if engine:
                    engine.stop()
            except Exception:
                pass
            completed.set()

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    completed.wait(timeout=60)
    return bool(result["ok"])


def get_voice_style(style: str) -> Dict[str, object]:
    normalized = (style or "casual").strip().lower()
    presets = {
        "professional": {
            "rate": 170,
            "sample": "Good afternoon. I am Roha, ready to help with your request.",
        },
        "casual": {
            "rate": 205,
            "sample": "Hey, I’m Roha. Let’s keep it simple and get this done.",
        },
    }
    return presets.get(normalized, presets["casual"])


def get_voice_rate() -> int:
    """Return the speaking rate from the environment, falling back to the casual preset."""
    raw_rate = os.getenv("VOICE_RATE", "").strip()
    if raw_rate:
        try:
            return int(raw_rate)
        except ValueError:
            logging.warning("Invalid VOICE_RATE value %r; using default rate", raw_rate)
    return int(get_voice_style("casual").get("rate", 205))


def find_zira_voice_id() -> Optional[str]:
    """Return the best matching Zira voice id on this machine, if present."""
    voices = list_available_voices()
    for voice in voices:
        name = (voice.get("name") or "").lower()
        if "zira" in name:
            return voice.get("id") or None
    return None


class TTSManager:
    """Threaded TTS manager: enqueues text and speaks in a background thread."""

    def __init__(self, voice_gender: str = "female", voice_id: Optional[str] = None, voice_style: str = "professional"):
        self.enabled = True
        self.engine = None
        self.voice_gender = voice_gender
        self.voice_id = voice_id
        self.voice_style = voice_style
        self._queue = queue.Queue()
        self._worker = None
        self._ready = threading.Event()
        # start background worker which will create the engine on the worker thread
        self._worker = threading.Thread(target=self._worker_loop, args=(voice_gender, voice_id, voice_style), daemon=True)
        self._worker.start()
        # wait briefly for the engine to be ready; do not block indefinitely
        if not self._ready.wait(timeout=5):
            logging.warning("TTS engine did not initialize within timeout; TTS may be unavailable")

    def set_voice(self, gender: str, voice_id: Optional[str] = None):
        if not self.engine:
            return
        try:
            voices = self.engine.getProperty("voices")
            preferred = None

            if voice_id:
                for v in voices:
                    if getattr(v, "id", None) == voice_id:
                        preferred = v
                        break

            if not preferred:
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

    def set_style(self, style: str):
        if not self.engine:
            return
        try:
            rate = get_voice_rate() if os.getenv("VOICE_RATE", "").strip() else int(get_voice_style(style).get("rate", 170))
            self.engine.setProperty("rate", rate)
        except Exception:
            logging.debug("Could not apply voice style; using default rate")

    def _apply_voice_config(self, gender: str, voice_id: Optional[str], voice_style: str):
        self.set_voice(gender, voice_id)
        self.set_style(voice_style)

    def _speak_with_fresh_engine(self, text: str, voice_gender: str, voice_id: Optional[str], voice_style: str):
        pyttsx3 = _load_pyttsx3()

        engine = pyttsx3.init()
        self.engine = engine
        try:
            self._apply_voice_config(voice_gender, voice_id, voice_style)
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

    def _worker_loop(self, voice_gender: str, voice_id: Optional[str], voice_style: str):
        # Initialize pyttsx3 on this thread to respect COM STA requirements on Windows
        try:
            pyttsx3 = _load_pyttsx3()
        except Exception:
            logging.warning("pyttsx3 not installed; TTS disabled")
            self.enabled = False
            self._ready.set()
            return

        try:
            self.engine = pyttsx3.init()
            try:
                self._apply_voice_config(voice_gender, voice_id, voice_style)
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
                    self._speak_with_fresh_engine(text, voice_gender, voice_id, voice_style)
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
    voice_id = os.getenv("VOICE_ID", "").strip() or find_zira_voice_id()
    voice_style = os.getenv("VOICE_STYLE", "casual")
    t = TTSManager(voice_gender=gender, voice_id=voice_id, voice_style=voice_style)
    if not getattr(t, "enabled", False):
        logging.warning("TTSManager created but not enabled; falling back to no TTS")
        return None
    return t
