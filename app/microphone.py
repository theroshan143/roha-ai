import os
import time

import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write


def record_audio(
    filename="recordings/input.wav",
    duration=5,
    sample_rate=16000,
):
    """Record for a fixed duration (used for testing)."""

    os.makedirs("recordings", exist_ok=True)

    print("🎤 Speak now...")

    audio = sd.rec(
        int(duration * sample_rate),
        samplerate=sample_rate,
        channels=1,
        dtype="int16",
    )

    sd.wait()

    write(filename, sample_rate, audio)

    print(f"✅ Audio saved to {filename}")

    return filename


def record_until_silence(
    filename="recordings/input.wav",
    sample_rate=16000,
    silence_threshold=500,
    silence_duration=1.2,
    max_duration=30,
):
    """
    Record until the user stops speaking.

    This version uses RMS audio level detection.
    Later we'll replace the detection logic with Silero VAD
    without changing the rest of the application.
    """

    os.makedirs("recordings", exist_ok=True)

    print("🎤 Listening... (speak naturally)")

    recording = []
    silence_start = None
    start_time = time.time()

    block_size = int(sample_rate * 0.25)  # 250 ms

    with sd.InputStream(
        samplerate=sample_rate,
        channels=1,
        dtype="int16",
        blocksize=block_size,
    ):

        while True:

            block, _ = sd.rec(
                block_size,
                samplerate=sample_rate,
                channels=1,
                dtype="int16",
            ), None

            sd.wait()

            recording.append(block)

            rms = np.sqrt(np.mean(block.astype(np.float32) ** 2))

            if rms > silence_threshold:
                silence_start = None

            else:
                if silence_start is None:
                    silence_start = time.time()

                elif time.time() - silence_start >= silence_duration:
                    print("🛑 Silence detected.")
                    break

            if time.time() - start_time > max_duration:
                print("⏱ Maximum recording duration reached.")
                break

    audio = np.concatenate(recording, axis=0)

    write(filename, sample_rate, audio)

    print(f"✅ Audio saved to {filename}")

    return filename