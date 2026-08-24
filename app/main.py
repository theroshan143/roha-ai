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


def _prepare_speech_summary(text: str, max_chars: int = 250) -> str:
    """Summarize long text responses into a concise voice snippet for TTS."""
    clean = (text or "").strip()
    if len(clean) <= max_chars:
        return clean

    import re
    sentences = re.split(r"(?<=[.!?])\s+", clean)
    speech = ""
    for s in sentences:
        if len(speech) + len(s) + 1 <= max_chars:
            speech += (" " + s if speech else s)
        else:
            break
    if not speech:
        speech = clean[:max_chars]
    return speech.rstrip() + ". Here is the detailed response on screen."


def _resolve_mode() -> str:
    parser = argparse.ArgumentParser(description="Run Roha in web, text, voice, wake, or menu mode.")
    parser.add_argument(
        "--mode",
        choices=("text", "voice", "wake", "web", "menu"),
        help="Start Roha in the selected mode (default: web).",
    )
    args = parser.parse_args()

    env_mode = os.getenv("ROHA_MODE", "").strip().lower()
    if args.mode:
        return args.mode
    if env_mode in ("text", "voice", "wake", "web", "menu"):
        return env_mode
    return "web"  # Default directly to web console mode



def main():
    session = RohaSession()

    try:
        voice_style = os.getenv("VOICE_STYLE", "casual").strip().lower()
        speak_enabled = os.getenv("VOICE_ENABLED", "false").lower() in ("1", "true", "yes")

        if speak_enabled and session.tts:
            style_preview = get_voice_style(voice_style).get("sample", "This is Roha.")
            print(f"Using {voice_style} style: {style_preview}")

        if session.tts:
            watch_for_stop(session.tts)
            logging.info("TTS initialized")

        mode = _resolve_mode()

        if mode == "menu":
            print("=" * 40)
            print("          ROHA")
            print("=" * 40)
            print("1. Text Mode (Default)")
            print("2. Voice Mode")
            print("3. Wake Word Mode")
            print("4. Web App")
            print("0. Exit")
            print("=" * 40)
            choice = input("Select mode: ").strip()
            if choice == "1" or not choice:
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
                print("Invalid choice. Defaulting to text mode.")
                mode = "text"

        print("=" * 50)
        print(f" ROHA AI Agent — Started in [{mode.upper()}] mode")
        print(" Commands: '/tts' (toggle voice), '/stop' (stop speech), '/listen', '/help'")
        print(" Tip: Press [ESC] at any time to interrupt active voice speech.")
        print("=" * 50)

        if mode == "web":
            from app.web_app import run_web_app
            run_web_app(session)
            return

        while True:
            user_input = None
            if mode == "text":
                raw = input("\nYou: ")
                user_input = raw.strip() if raw is not None else ""

                # Handle dynamic in-session commands
                if user_input.lower() in ("/tts", "/voice", "/speech"):
                    speak_enabled = not speak_enabled
                    status = "ENABLED 🔊" if speak_enabled else "DISABLED 🔇"
                    print(f"System: Voice response is now {status}")
                    continue

                if user_input.lower() in ("/stop", "/mute", "/hush", "/quiet"):
                    if session.tts:
                        session.tts.stop()
                    print("System: Stopped active voice speech.")
                    continue

                if user_input.lower() == "/listen":
                    print("System: Recording audio from microphone... (speak now)")
                    audio_path = record_wake_audio()
                    user_input = transcribe_audio(audio_path).strip()
                    if user_input:
                        print(f"\n🎧 [Transcribed Speech]: \"{user_input}\"")
                    else:
                        print("\n⚠️  [Speech Recognition]: Could not transcribe any speech. Please try speaking again.")
                        continue

                if user_input.lower().startswith(("/auth", "/unlock")):
                    parts = user_input.split(maxsplit=1)
                    if len(parts) > 1:
                        pin = parts[1].strip()
                        if session.authenticate(pin):
                            print("System: 🔓 Creator Verified (Roshan Kumar). Full personal file & tool access unlocked!")
                        else:
                            print("System: ❌ Invalid PIN. Remaining in Guest Mode.")
                    else:
                        print("Usage: /auth <pin>")
                    continue

                if user_input.lower() in ("/lock", "/relock"):
                    session.lock_session()
                    print("System: 🔒 Session locked into Guest Mode. Personal file access restricted.")
                    continue

                if user_input.lower() == "/status":
                    status = "🔓 Verified Creator (Roshan Kumar)" if session.is_verified else "🔒 Guest / Unverified Mode"
                    print(f"System: Active Security Status: {status}")
                    continue

                elif user_input.lower().startswith("/mode"):
                    parts = user_input.split()
                    if len(parts) > 1 and parts[1] in ("text", "voice", "wake", "web"):
                        mode = parts[1]
                        print(f"System: Switched to [{mode.upper()}] mode.")
                        if mode == "web":
                            from app.web_app import run_web_app
                            run_web_app(session)
                            return
                        continue
                    else:
                        print("Usage: /mode [text|voice|wake|web]")
                        continue

                elif user_input.lower() in ("/help", "/commands"):
                    print("\n--- Available Commands ---")
                    print(" /tts, /voice   : Toggle text-to-speech voice output on/off")
                    print(" /stop, /mute   : Stop active speech playback immediately")
                    print(" /auth <pin>    : Authenticate as Creator (Roshan Kumar)")
                    print(" /lock          : Lock session into Guest Mode")
                    print(" /status        : View current authentication & security status")
                    print(" /listen        : Record voice input using microphone")
                    print(" /mode <mode>   : Switch mode (text, voice, wake, web)")
                    print(" exit           : Exit Roha")
                    print("--------------------------")
                    continue

            elif mode == "voice":
                print("\n[Voice Mode] Recording audio...")
                audio_path = record_wake_audio()
                raw = transcribe_audio(audio_path)
                user_input = raw.strip() if raw else ""
                if user_input:
                    print(f"🎧 [Transcribed Speech]: \"{user_input}\"")
                else:
                    print("⚠️  [Speech Recognition]: No speech detected.")
                    continue

            elif mode == "wake":
                heard = wait_for_wake_word()
                if heard is None:
                    print("Wake listener stopped.")
                    break
                print("Roha: Yes?")
                if session.tts and speak_enabled:
                    try:
                        session.tts.speak("Yes?")
                    except Exception:
                        logging.exception("TTS 'Yes?' speak failed")
                audio_path = record_wake_audio()
                raw = transcribe_audio(audio_path)
                user_input = raw.strip() if raw else ""
                if user_input:
                    print(f"🎧 [Transcribed Speech]: \"{user_input}\"")

            if not user_input:
                print("Sorry I didn't catch that. Please try again.")
                continue

            if user_input.lower() == "exit":
                print("\nRoha: Goodbye!")
                break

            assistant_reply = session.process_user_input(user_input, speak=False)

            print(f"\nRoha: {assistant_reply}")

            if speak_enabled and session.tts:
                try:
                    speech_text = _prepare_speech_summary(assistant_reply, max_chars=250)
                    session.tts.speak(speech_text)
                    logging.info("TTS status after enqueue: %s", session.tts.status())
                except Exception:
                    logging.exception("TTS speak failed")

    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        session.close()


if __name__ == "__main__":
    main()