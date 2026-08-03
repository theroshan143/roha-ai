from typing import Sequence
import time
import logging

from ollama import chat

from app.config import MODEL
from app.types import Message


def chat_with_roha(messages: Sequence[Message]) -> str:
    """Call Ollama chat with a small retry loop and basic response validation."""
    attempts = int(__import__('os').environ.get('MODEL_RETRY', '2'))
    delay = 1
    last_exc = None
    for attempt in range(1, attempts + 1):
        try:
            start = time.time()
            response = chat(model=MODEL, messages=messages)
            latency = time.time() - start
            logging.info("Model call latency: %.2fs (attempt %d)", latency, attempt)
            if not isinstance(response, dict):
                raise RuntimeError("Invalid model response type")
            msg = response.get("message") or {}
            content = msg.get("content")
            if not isinstance(content, str):
                raise RuntimeError("Model returned non-string content")
            return content.strip()
        except Exception as e:
            last_exc = e
            logging.warning("Model attempt %d failed: %s", attempt, e)
            time.sleep(delay)
            delay *= 2
    raise RuntimeError(f"LLM call failed after {attempts} attempts: {last_exc}")