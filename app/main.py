import logging
import os
from app.prompts import load_system_prompt
from app.chat import chat_with_roha
from app.memory import MemoryManager


# Ensure necessary directories exist
os.makedirs("logs", exist_ok=True)
os.makedirs("data", exist_ok=True)

# Logging to console and file
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler("logs/roha.log", encoding="utf-8"),
        logging.StreamHandler()
    ],
)


def trimmed_messages(messages, history_limit=12):
    """Return a trimmed copy of messages keeping the system prompt and last N messages."""
    if not messages:
        return messages
    system = [m for m in messages if m.get("role") == "system"]
    other = [m for m in messages if m.get("role") != "system"]
    trimmed = system[:1] + other[-history_limit:]
    return trimmed


def main():
    # Roha's personality
    system_prompt = load_system_prompt()

    # Conversation history
    messages = [
        {"role": "system", "content": system_prompt}
    ]

    memory_manager = MemoryManager()
    # initialize TTS once to avoid repeated engine creation
    try:
        from app.tts import create_default_tts

        tts = create_default_tts()
        if tts:
            logging.info("TTS initialized")
        else:
            logging.info("TTS disabled via environment")
    except Exception:
        tts = None
        logging.debug("TTS module not available")

    print("Roha is online!")
    print("Type 'exit' to quit.")

    try:
        while True:
            user_input = input("You: ")

            if user_input.lower() == "exit":
                print("\nRoha: Goodbye!")
                break

            # Add user's message to conversation and memory
            messages.append({"role": "user", "content": user_input})
            memory_manager.add_message("user", user_input)

            # Send trimmed history to the model to avoid token limits
            to_send = trimmed_messages(messages, history_limit=12)

            try:
                assistant_reply = chat_with_roha(to_send)
            except Exception as e:
                logging.error("Failed to get assistant reply: %s", e)
                assistant_reply = "I'm having trouble connecting to the model right now. Please try again later."

            # Save Roha's reply
            messages.append({"role": "assistant", "content": assistant_reply})
            memory_manager.add_message("assistant", assistant_reply)

            print("\nRoha:", assistant_reply)
            print()

            # speak if TTS is available
            try:
                if tts:
                    tts.speak(assistant_reply)
                else:
                    logging.debug("TTS not enabled for this session")
            except Exception as e:
                logging.warning("TTS speak failed: %s", e)

    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        memory_manager.close()
        try:
            if 'tts' in locals() and tts:
                tts.shutdown()
                logging.info("TTS shut down")
        except Exception:
            logging.debug("Error shutting down TTS")


if __name__ == "__main__":
    main()