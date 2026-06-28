from ollama import chat

# Roha's personality
with open("prompts/system_prompt.txt", "r", encoding="utf-8") as file:
    system_prompt = file.read()

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
        print("\nRoha: Goodbye, Roshan!")
        break

    # Save user's message
    messages.append(
        {
            "role": "user",
            "content": user_input
        }
    )

    # Send entire conversation to Ollama
    response = chat(
        model="gemma3:4b",   
        messages=messages
    )

    assistant_reply = response["message"]["content"]

    # Save Roha's reply
    messages.append(
        {
            "role": "assistant",
            "content": assistant_reply
        }
    )

    print("\nRoha:", assistant_reply)
    print()