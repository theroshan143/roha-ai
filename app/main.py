import logging
import os
from typing import List

from app.types import Message
from app.prompts import load_system_prompt
from app.chat import chat_with_roha
from app.memory import MemoryManager
from app.tts import create_default_tts, get_voice_style
from app.microphone import record_audio
from app.stt import transcribe_audio


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


def trimmed_messages(messages: List[Message], history_limit: int = 12) -> List[Message]:
    """Return a trimmed copy of messages keeping the system prompt and last N messages."""
    if not messages:
        return messages
    system = [m for m in messages if m.get("role") == "system"]
    other = [m for m in messages if m.get("role") != "system"]
    trimmed: List[Message] = system[:1] + other[-history_limit:]
    return trimmed


def main():
    # Roha's personality
    system_prompt = load_system_prompt()

    # Conversation history
    messages: List[Message] = [
        {"role": "system", "content": system_prompt}
    ]

    memory_manager = MemoryManager()
    # initialize TTS once to avoid repeated engine creation
    try:
        voice_style = os.getenv("VOICE_STYLE", "casual").strip().lower()
        if os.getenv("VOICE_ENABLED", "false").lower() in ("1", "true", "yes"):
            style_preview = get_voice_style(voice_style).get("sample", "This is Roha.")
            print(f"Using {voice_style} style: {style_preview}")

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
    mode = input("Choose mode (text/voice): ").strip().lower()

    try:
        while True:
            if mode == "voice":
                print("Recording audio...")
                audio_data = record_audio()
                user_input = transcribe_audio(audio_data)
                
            else:
                user_input = input("You: ")

            if user_input.lower() == "exit":
                print("\nRoha: Goodbye!")
                break

            # Add user's message to conversation and memory
            messages.append({"role": "user", "content": user_input})
            if not user_input.strip():
                print("Sorry I didn't catch that. Please try again.")
                continue
            memory_manager.add_message("user", user_input)

            # Send trimmed history to the model to avoid token limits
            to_send = trimmed_messages(messages, history_limit=12)

            try:
                assistant_reply = chat_with_roha(to_send)
            except Exception as e:
                import traceback
                traceback.print_exc()
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
                    logging.info("TTS status after enqueue: %s", tts.status())
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