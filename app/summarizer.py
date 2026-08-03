from typing import List
import logging

from app.chat import chat_with_roha


def summarize_texts(texts: List[str], max_chars: int = 3000) -> str:
    """Use the chat model to produce a concise summary of the provided texts.

    Falls back to naive concatenation if the model is unavailable.
    """
    if not texts:
        return ""
    joined = "\n---\n".join(texts)
    if len(joined) > max_chars:
        joined = joined[-max_chars:]

    system = (
        "You are an assistant specialized in condensing conversation transcripts and notes. "
        "Produce a short, bullet-point style summary of the most important facts, decisions, "
        "and action items. Be concise and keep it factual."
    )

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Summarize the following content:\n\n{joined}"},
    ]

    try:
        summary = chat_with_roha(messages)
        if summary:
            return summary.strip()
    except Exception:
        logging.exception("LLM summarization failed; falling back to naive summary")

    # naive fallback: return first N chars
    fallback = ("\n".join(texts))
    return (fallback[:max_chars] + "...") if len(fallback) > max_chars else fallback
