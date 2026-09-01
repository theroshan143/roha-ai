import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Sequence

from openai import OpenAI

from app.config import MODEL, PROVIDERS, DEFAULT_PROVIDER
from app.types import Message


# Cache OpenAI client instances per base_url to avoid reconnect overhead
_CLIENT_CACHE: Dict[str, OpenAI] = {}


def _get_client(provider_key: str) -> OpenAI:
    """Get or create a cached OpenAI-compatible client for the given provider."""
    provider = PROVIDERS.get(provider_key)
    if not provider:
        raise ValueError(f"Unknown provider '{provider_key}'. Valid: {list(PROVIDERS.keys())}")

    base_url = provider["base_url"]
    if base_url not in _CLIENT_CACHE:
        _CLIENT_CACHE[base_url] = OpenAI(
            base_url=base_url,
            api_key=provider.get("api_key") or "no-key",
        )
    return _CLIENT_CACHE[base_url]


def _convert_tool_schema(ollama_tool: Dict[str, Any]) -> Dict[str, Any]:
    """Convert an Ollama-format tool schema to OpenAI function-calling format.

    Ollama format:
      {"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}

    OpenAI format is identical, so this is mostly a passthrough with validation.
    """
    if "type" in ollama_tool and ollama_tool["type"] == "function":
        return ollama_tool  # Already OpenAI-compatible
    # Fallback: wrap bare function dict
    return {"type": "function", "function": ollama_tool}


def _normalize_tool_calls(raw_tool_calls: Any) -> List[Dict[str, Any]]:
    """Normalize OpenAI-format tool_calls into Roha's internal format.

    Input (OpenAI format):
      [ChatCompletionMessageToolCall(id=..., type='function',
        function=Function(name='...', arguments='...'))]

    Output (Roha internal format):
      [{"function": {"name": "...", "arguments": {...}}}]
    """
    if not raw_tool_calls:
        return []

    result = []
    for tc in raw_tool_calls:
        # Handle both object and dict representations
        fn = getattr(tc, "function", None)
        if fn is None and isinstance(tc, dict):
            fn = tc.get("function")
        if fn is None:
            continue

        fn_name = getattr(fn, "name", None)
        if fn_name is None and isinstance(fn, dict):
            fn_name = fn.get("name")

        fn_args_raw = getattr(fn, "arguments", None)
        if fn_args_raw is None and isinstance(fn, dict):
            fn_args_raw = fn.get("arguments")

        # Parse arguments from JSON string to dict
        fn_args: Any = {}
        if isinstance(fn_args_raw, str):
            try:
                fn_args = json.loads(fn_args_raw)
            except (json.JSONDecodeError, TypeError):
                fn_args = fn_args_raw
        elif isinstance(fn_args_raw, (dict, list)):
            fn_args = fn_args_raw

        if fn_name:
            result.append({
                "function": {
                    "name": str(fn_name),
                    "arguments": fn_args,
                }
            })
    return result


def chat_with_roha(
    messages: Sequence[Message],
    tools: Optional[List[Dict[str, Any]]] = None,
    model: Optional[str] = None,
    provider: Optional[str] = None,
) -> Dict[str, Any]:
    """Call the LLM via OpenAI-compatible API with optional tool schemas and retry logic.

    Works identically for local Ollama and cloud Groq backends.
    Returns a dict: {"content": str, "tool_calls": list}
    """
    provider_key = provider or DEFAULT_PROVIDER
    provider_cfg = PROVIDERS.get(provider_key, PROVIDERS.get("local", {}))
    resolved_model = model or provider_cfg.get("model") or MODEL
    timeout = provider_cfg.get("timeout", 90)

    attempts = int(os.environ.get("MODEL_RETRY", "2"))
    delay = 1
    last_exc = None

    client = _get_client(provider_key)

    # Build kwargs
    kwargs: Dict[str, Any] = {
        "model": resolved_model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 400,
    }

    if tools:
        openai_tools = [_convert_tool_schema(t) for t in tools]
        kwargs["tools"] = openai_tools

    for attempt in range(1, attempts + 1):
        try:
            start = time.time()
            response = client.chat.completions.create(
                timeout=timeout,
                **kwargs,
            )
            latency = time.time() - start
            logging.info(
                "Model call [%s/%s] latency: %.2fs (attempt %d)",
                provider_key, resolved_model, latency, attempt,
            )

            # Parse response
            choice = response.choices[0] if response.choices else None
            content = ""
            tool_calls: List[Dict[str, Any]] = []

            if choice and choice.message:
                msg = choice.message
                if msg.content:
                    content = msg.content.strip()
                tool_calls = _normalize_tool_calls(msg.tool_calls)

            return {"content": content, "tool_calls": tool_calls}

        except Exception as e:
            last_exc = e
            logging.warning(
                "Model attempt %d failed [%s]: %s", attempt, provider_key, e
            )
            time.sleep(delay)
            delay *= 2

    raise RuntimeError(f"LLM call failed after {attempts} attempts [{provider_key}]: {last_exc}")


def check_provider_health(provider_key: str) -> Dict[str, Any]:
    """Quick health check for a provider — attempts to list models.

    Returns: {"healthy": bool, "provider": str, "detail": str}
    """
    try:
        client = _get_client(provider_key)
        # Use a minimal completions call with max_tokens=1 to test connectivity
        provider_cfg = PROVIDERS.get(provider_key, {})
        model = provider_cfg.get("model", "test")
        client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=1,
            timeout=10,
        )
        return {"healthy": True, "provider": provider_key, "detail": "OK"}
    except Exception as e:
        return {"healthy": False, "provider": provider_key, "detail": str(e)}
