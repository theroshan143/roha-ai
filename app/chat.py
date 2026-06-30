from ollama import chat
from app.config import MODEL


def chat_with_roha(messages):
    response = chat(
        model=MODEL,
        messages=messages
    )

    return response["message"]["content"]