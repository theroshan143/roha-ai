import logging
import os
import time
from typing import Any, Dict, List, Optional, Sequence
# pyrefly: ignore [missing-import]
from ollama import chat
from app.config import MODEL
from app.types import Message


def chat_with_roha(
    messages: Sequence[Message], tools: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """Call Ollama chat with optional tool schemas and retry logic.

    Returns a dict: {"content": str, "tool_calls": list}
    """
    attempts = int(os.environ.get("MODEL_RETRY", "2"))
    delay = 1
    last_exc = None

    kwargs: Dict[str, Any] = {
        "model": MODEL,
        "messages": messages,
        "options": {
            "temperature": 0.2,
            "num_predict": 400,
        },
    }
    if tools:
        kwargs["tools"] = tools


    for attempt in range(1, attempts + 1):
        try:
            start = time.time()
            response = chat(**kwargs)
            latency = time.time() - start
            logging.info("Model call latency: %.2fs (attempt %d)", latency, attempt)

            msg = getattr(response, "message", None)
            if msg is None and isinstance(response, dict):
                msg = response.get("message")

            content = ""
            tool_calls: List[Dict[str, Any]] = []

            if msg is not None:
                raw_content = getattr(msg, "content", None)
                if raw_content is None and isinstance(msg, dict):
                    raw_content = msg.get("content")
                if isinstance(raw_content, str):
                    content = raw_content.strip()

                raw_tools = getattr(msg, "tool_calls", None)
                if raw_tools is None and isinstance(msg, dict):
                    raw_tools = msg.get("tool_calls")
                if raw_tools and isinstance(raw_tools, list):
                    for t in raw_tools:
                        fn = getattr(t, "function", None)
                        if fn is None and isinstance(t, dict):
                            fn = t.get("function")

                        fn_name = getattr(fn, "name", None)
                        if fn_name is None and isinstance(fn, dict):
                            fn_name = fn.get("name")

                        fn_args = getattr(fn, "arguments", None)
                        if fn_args is None and isinstance(fn, dict):
                            fn_args = fn.get("arguments")

                        if fn_name:
                            tool_calls.append({
                                "function": {
                                    "name": str(fn_name),
                                    "arguments": fn_args if isinstance(fn_args, (dict, list, str)) else {},
                                }
                            })

            return {"content": content, "tool_calls": tool_calls}

        except Exception as e:
            last_exc = e
            logging.warning("Model attempt %d failed: %s", attempt, e)
            time.sleep(delay)
            delay *= 2

    raise RuntimeError(f"LLM call failed after {attempts} attempts: {last_exc}")
