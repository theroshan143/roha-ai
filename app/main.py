from ollama import chat

# Read Roha's personality
with open("prompts/system_prompt.txt", "r", encoding="utf-8") as file:
    system_prompt = file.read()

# Initialize Roha
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
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_input,
            }
        ],
    )

    print("Roha:", response["message"]["content"])

print("Roha is offline.")