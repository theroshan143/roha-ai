import sounddevice as sd
from scipy.io.wavfile import write
import os


def record_audio(
    filename="recordings/input.wav",
    duration=5,
    sample_rate=16000
):
    # Ensure recordings folder exists
    os.makedirs("recordings", exist_ok=True)

    print("🎤 Speak now...")

    audio = sd.rec(
        int(duration * sample_rate),
        samplerate=sample_rate,
        channels=1,
        dtype="int16"
    )

    sd.wait()

    write(filename, sample_rate, audio)

    print(f"✅ Audio saved to {filename}")

    return filename