from app.config import MODEL


def chat_with_roha(messages):
    try:
        # import the Ollama client lazily so the module can be imported in test environments
        from ollama import chat
    except Exception as e:
        raise RuntimeError("Ollama client not available: install 'ollama' or set up a mock for tests")

    try:
        response = chat(model=MODEL, messages=messages)
        return response["message"]["content"]
    except Exception as e:
        raise RuntimeError(f"LLM call failed: {e}")