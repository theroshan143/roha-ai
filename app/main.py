import logging
import os
from typing import List
import concurrent.futures

from app.types import Message
from app.prompts import load_system_prompt
from app.chat import chat_with_roha
from app.memory import MemoryManager
from app.tts import create_default_tts, get_voice_style
from app.microphone import record_wake_audio
from app.stt import transcribe_audio
from app.keyboard_listener import watch_for_stop
from app.wake_detector import wait_for_wake_word
from app.config import LOG_PATH, DB_PATH, HISTORY_LIMIT


# Ensure necessary directories exist
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# Logging to console and file
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler()
    ],
)


def trimmed_messages(messages: List[Message], history_limit: int = HISTORY_LIMIT) -> List[Message]:
    """Return a trimmed copy of messages keeping the system prompt and last N messages."""
    if not messages:
        return messages
    system = [m for m in messages if m.get("role") == "system"]
    other = [m for m in messages if m.get("role") != "system"]
    trimmed: List[Message] = (system[:1] if system else []) + other[-history_limit:]
    return trimmed


def _call_model_with_timeout(messages, timeout: int = 30) -> str:
    """Call the chat model with a timeout using a thread to avoid blocking the main loop."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(chat_with_roha, messages)
        try:
            return fut.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            fut.cancel()
            raise TimeoutError("Model request timed out")


def main():
    # Roha's personality
    system_prompt = load_system_prompt()

    # Conversation history
    messages: List[Message] = [
        {"role": "system", "content": system_prompt}
    ]

    memory_manager = MemoryManager(DB_PATH)
    # circuit breaker for model calls
    from app.circuit_breaker import CircuitBreaker
    cb = CircuitBreaker()

    # initialize TTS once to avoid repeated engine creation
    try:
        voice_style = os.getenv("VOICE_STYLE", "casual").strip().lower()
        if os.getenv("VOICE_ENABLED", "false").lower() in ("1", "true", "yes"):
            style_preview = get_voice_style(voice_style).get("sample", "This is Roha.")
            print(f"Using {voice_style} style: {style_preview}")

        tts = create_default_tts()

        if tts:
            watch_for_stop(tts)
            logging.info("TTS initialized")
        else:
            logging.info("TTS disabled via environment")
    except Exception:
        tts = None
        logging.debug("TTS module not available")

    print("=" * 40)
    print("          ROHA")
    print("=" * 40)
    print("1. Text Mode")
    print("2. Voice Mode")
    print("3. Wake Word Mode")
    print("0. Exit")
    print("=" * 40)

    choice = input("Select mode: ").strip()
    if choice == "1":
        mode = "text"

    elif choice == "2":
        mode = "voice"

    elif choice == "3":
        mode = "wake"

    elif choice == "0":
        print("Goodbye!")
        return

    else:
        print("Invalid choice.")
        return

    try:
        while True:
            user_input = None
            if mode == "text":
                raw = input("You: ")
                user_input = raw.strip() if raw is not None else ""

            elif mode == "voice":
                audio_path = record_wake_audio()
                raw = transcribe_audio(audio_path)
                user_input = raw.strip() if raw else ""
                print(f"You: {user_input}")
                
            elif mode == "wake":
                wait_for_wake_word()
                print("Roha: Yes?")
                if tts:
                    try:
                        tts.speak("Yes?")
                    except Exception:
                        logging.exception("TTS 'Yes?' speak failed")
                audio_path = record_wake_audio()
                raw = transcribe_audio(audio_path)
                user_input = raw.strip() if raw else ""
                print(f"You: {user_input}")
                
            else:
                raw = input("You: ")
                user_input = raw.strip() if raw is not None else ""

            if not user_input:
                # empty or failed transcription
                print("Sorry I didn't catch that. Please try again.")
                continue

            if user_input.lower() == "exit":
                print("\nRoha: Goodbye!")
                break

            # Add user's message to conversation and memory
            messages.append({"role": "user", "content": user_input})
            memory_manager.add_message("user", user_input)

            # Send trimmed history to the model to avoid token limits
            to_send = trimmed_messages(messages, history_limit=HISTORY_LIMIT)

            try:
                if not cb.call_allowed():
                    wait_seconds = cb.time_until_reset()
                    logging.warning("Circuit breaker open; skipping model call for %d seconds", wait_seconds)
                    assistant_reply = "The model is temporarily unavailable due to repeated errors. Please try again later."
                else:
                    try:
                        assistant_reply = _call_model_with_timeout(to_send, timeout=int(os.getenv("MODEL_TIMEOUT", "30")))
                        # model succeeded
                        cb.record_success()
                    except Exception as e:
                        logging.exception("Model call failed")
                        cb.record_failure()
                        assistant_reply = "I'm having trouble connecting to the model right now. Please try again later."
            except Exception:
                logging.exception("Unexpected model error")
                assistant_reply = "Sorry, something went wrong while generating a response."

            # Save Roha's reply
            messages.append({"role": "assistant", "content": assistant_reply})
            try:
                memory_manager.add_message("assistant", assistant_reply)
            except Exception:
                logging.exception("Failed to persist assistant message")

            # occasionally summarize memory to keep DB small
            try:
                # summarize every 20 assistant responses
                last_assistant_count = sum(1 for m in messages if m.get("role") == "assistant")
                if last_assistant_count % 20 == 0:
                    memory_manager.summarize_memory(keep_last=200)
            except Exception:
                logging.exception("Memory summarization failed")

            print("\nRoha:", assistant_reply)
            print()

            # speak if TTS is available
            try:
                if tts:
                    tts.speak(assistant_reply)
                    logging.info("TTS status after enqueue: %s", tts.status())
                else:
                    logging.debug("TTS not enabled for this session")
            except Exception:
                logging.exception("TTS speak failed")

    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        try:
            memory_manager.close()
        except Exception:
            logging.exception("Error closing memory manager")
        try:
            if 'tts' in locals() and tts:
                tts.shutdown()
                logging.info("TTS shut down")
        except Exception:
            logging.exception("Error shutting down TTS")


if __name__ == "__main__":
    main()