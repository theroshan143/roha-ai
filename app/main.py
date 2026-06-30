from app.prompts import load_system_prompt
from app.config import MODEL
from app.chat import chat_with_roha

# Roha's personality
system_prompt = load_system_prompt()

# Conversation history
messages = [
    {
        "role": "system",
        "content": system_prompt
    }
]

print("Roha is online!")
print("Type 'exit' to quit.")

while True:
    user_input = input("You: ")

    if user_input.lower() == "exit":
        print("\nRoha: Goodbye, Sir!")
        break

    # Save user's message
    messages.append(
        {
            "role": "user",
            "content": user_input
        }
    )

    # Send entire conversation to Ollama
    assistant_reply = chat_with_roha(messages)
    # Save Roha's reply
    messages.append(
        {
            "role": "assistant",
            "content": assistant_reply
        }
    )

    print("\nRoha:", assistant_reply)
    print()