import concurrent.futures
import logging
import os
import threading
import time
from typing import List, Optional

from app.chat import chat_with_roha
from app.config import DB_PATH, HISTORY_LIMIT
from app.memory import MemoryManager
from app.prompts import load_system_prompt
from app.tts import create_default_tts
from app.types import Message


def trimmed_messages(messages: List[Message], history_limit: int = HISTORY_LIMIT) -> List[Message]:
    """Return a trimmed copy of messages keeping the system prompt and last N messages."""
    if not messages:
        return messages
    system = [m for m in messages if m.get("role") == "system"]
    other = [m for m in messages if m.get("role") != "system"]
    trimmed: List[Message] = (system[:1] if system else []) + other[-history_limit:]
    return trimmed


def _call_model_with_timeout(messages, timeout: int = 30) -> str:
    """Call the chat model with a timeout without blocking shutdown of the worker thread."""
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    fut = executor.submit(chat_with_roha, messages)
    try:
        return fut.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        fut.cancel()
        raise TimeoutError("Model request timed out")
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


class RohaSession:
    """Shared assistant runtime for terminal and web UI entrypoints."""

    def __init__(self):
        self.system_prompt = load_system_prompt()
        self.messages: List[Message] = [{"role": "system", "content": self.system_prompt}]
        self.memory_manager = MemoryManager(DB_PATH)
        from app.circuit_breaker import CircuitBreaker

        self.cb = CircuitBreaker()
        self.tts = create_default_tts()
        self._lock = threading.Lock()

    def reset(self) -> None:
        with self._lock:
            self.messages = [{"role": "system", "content": self.system_prompt}]

    def snapshot_messages(self) -> List[Message]:
        with self._lock:
            return list(self.messages)

    def _assistant_count(self) -> int:
        return sum(1 for m in self.messages if m.get("role") == "assistant")

    def process_user_input(self, user_input: str, speak: bool = False) -> str:
        normalized = (user_input or "").strip()
        if not normalized:
            return ""

        if normalized.lower() == "exit":
            return "Goodbye!"

        with self._lock:
            self.messages.append({"role": "user", "content": normalized})
            self.memory_manager.add_message("user", normalized)

            to_send = trimmed_messages(self.messages, history_limit=HISTORY_LIMIT)

            try:
                if not self.cb.call_allowed():
                    wait_seconds = self.cb.time_until_reset()
                    logging.warning(
                        "Circuit breaker open; skipping model call for %d seconds",
                        wait_seconds,
                    )
                    assistant_reply = (
                        "The model is temporarily unavailable due to repeated errors. "
                        "Please try again later."
                    )
                else:
                    try:
                        assistant_reply = _call_model_with_timeout(
                            to_send,
                            timeout=int(os.getenv("MODEL_TIMEOUT", "30")),
                        )
                        self.cb.record_success()
                    except Exception:
                        logging.exception("Model call failed")
                        self.cb.record_failure()
                        assistant_reply = (
                            "I'm having trouble connecting to the model right now. "
                            "Please try again later."
                        )
            except Exception:
                logging.exception("Unexpected model error")
                assistant_reply = "Sorry, something went wrong while generating a response."

            self.messages.append({"role": "assistant", "content": assistant_reply})
            try:
                self.memory_manager.add_message("assistant", assistant_reply)
            except Exception:
                logging.exception("Failed to persist assistant message")

            try:
                if self._assistant_count() % 20 == 0:
                    self.memory_manager.summarize_memory(keep_last=200)
            except Exception:
                logging.exception("Memory summarization failed")

        if speak and self.tts:
            try:
                self.tts.speak(assistant_reply)
                logging.info("TTS status after enqueue: %s", self.tts.status())
            except Exception:
                logging.exception("TTS speak failed")

        return assistant_reply

    def close(self) -> None:
        try:
            self.memory_manager.close()
        except Exception:
            logging.exception("Error closing memory manager")
        try:
            if self.tts:
                self.tts.shutdown()
                logging.info("TTS shut down")
        except Exception:
            logging.exception("Error shutting down TTS")
