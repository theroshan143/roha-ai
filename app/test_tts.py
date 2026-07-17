from app.tts import create_default_tts


def main():
    t = create_default_tts()
    print("TTS instance:", bool(t))
    if t:
        t.speak("Hello, this is Roha speaking. If you can hear this, T T S is working.")


if __name__ == "__main__":
    main()
