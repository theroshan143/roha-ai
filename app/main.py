from ollama import chat

print("Roha is online!")
print("Type 'exit' to quit.\n")

while True:
    user_input = input("You: ")

    if user_input.lower() == "exit":
        print("Roha: Goodbye!")
        break

    response = chat(
        model="gemma3:4b",
        messages=[
            {
                "role": "user",
                "content": user_input,
            }
        ],
    )

    print("Roha:", response["message"]["content"])

print("Roha is offline.")