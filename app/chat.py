from typing import Sequence

from ollama import chat

from app.config import MODEL
from app.types import Message


def chat_with_roha(messages: Sequence[Message]) -> str:
    try:
        response = chat(
            model=MODEL,
            messages=messages,
        )
        return response["message"]["content"]

    except Exception as e:
        raise RuntimeError(f"LLM call failed: {e}")