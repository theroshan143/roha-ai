import argparse
import logging
import os

from app.assistant_session import RohaSession
from app.keyboard_listener import watch_for_stop
from app.microphone import record_wake_audio
from app.stt import transcribe_audio
from app.wake_detector import wait_for_wake_word
from app.tts import get_voice_style
from app.config import LOG_PATH, DB_PATH


# Ensure necessary directories exist
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# Logging to console and file
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)


def _resolve_mode() -> str:
    parser = argparse.ArgumentParser(description="Run Roha in text, voice, wake, or web mode.")
    parser.add_argument(
        "--mode",
        choices=("text", "voice", "wake", "web"),
        help="Start Roha directly in the selected mode.",
    )
    args = parser.parse_args()

    env_mode = os.getenv("ROHA_MODE", "").strip().lower()
    if args.mode:
        return args.mode
    if env_mode in ("text", "voice", "wake", "web"):
        return env_mode
    return "menu"


def main():
    session = RohaSession()

    try:
        voice_style = os.getenv("VOICE_STYLE", "casual").strip().lower()
        if os.getenv("VOICE_ENABLED", "false").lower() in ("1", "true", "yes"):
            style_preview = get_voice_style(voice_style).get("sample", "This is Roha.")
            print(f"Using {voice_style} style: {style_preview}")

        if session.tts:
            watch_for_stop(session.tts)
            logging.info("TTS initialized")
        else:
            logging.info("TTS disabled via environment")

        print("=" * 40)
        print("          ROHA")
        print("=" * 40)
        print("1. Text Mode")
        print("2. Voice Mode")
        print("3. Wake Word Mode")
        print("4. Web App")
        print("0. Exit")
        print("=" * 40)

        mode = _resolve_mode()
        if mode == "menu":
            choice = input("Select mode: ").strip()
            if choice == "1":
                mode = "text"
            elif choice == "2":
                mode = "voice"
            elif choice == "3":
                mode = "wake"
            elif choice == "4":
                mode = "web"
            elif choice == "0":
                print("Goodbye!")
                return
            else:
                print("Invalid choice.")
                return
        else:
            print(f"Starting in {mode} mode.")

        if mode == "web":
            from app.web_app import run_web_app

            run_web_app(session)
            return

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
                heard = wait_for_wake_word()
                if heard is None:
                    print("Wake listener stopped.")
                    break
                print("Roha: Yes?")
                if session.tts:
                    try:
                        session.tts.speak("Yes?")
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
                print("Sorry I didn't catch that. Please try again.")
                continue

            if user_input.lower() == "exit":
                print("\nRoha: Goodbye!")
                break

            assistant_reply = session.process_user_input(user_input, speak=False)

            print("\nRoha:", assistant_reply)
            print()

            try:
                if session.tts:
                    session.tts.speak(assistant_reply)
                    logging.info("TTS status after enqueue: %s", session.tts.status())
                else:
                    logging.debug("TTS not enabled for this session")
            except Exception:
                logging.exception("TTS speak failed")

    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        session.close()


if __name__ == "__main__":
    main()