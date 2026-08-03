import os
import time
import logging

import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write


def record_audio(
    filename="recordings/input.wav",
    duration=5,
    sample_rate=16000,
):
    """Record for a fixed duration (used for testing)."""

    os.makedirs(os.path.dirname(filename) or "recordings", exist_ok=True)

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


def record_wake_audio(
    filename="recordings/input.wav",
    sample_rate=16000,
    silence_threshold=500,
    silence_duration=1.5,
    max_duration=3.5,
):
    """
    Record until the user stops speaking.

    This version uses RMS audio level detection.
    Later we'll replace the detection logic with Silero VAD
    without changing the rest of the application.
    """

    os.makedirs(os.path.dirname(filename) or "recordings", exist_ok=True)

    print("🎤 Listening... (speak naturally)")

    recording = []
    silence_start = None
    start_time = time.time()

    block_size = int(sample_rate * 0.25)  # 250 ms

    try:
        with sd.InputStream(
            samplerate=sample_rate,
            channels=1,
            dtype="int16",
            blocksize=block_size,
        ) as stream:

            while True:
                block, overflowed = stream.read(block_size)
                if overflowed:
                    print("⚠️  Audio buffer overflowed!")

                # append only if block has data
                if block is not None and len(block) > 0:
                    recording.append(block)

                try:
                    rms = np.sqrt(np.mean(block.astype(np.float32) ** 2))
                except Exception:
                    rms = 0

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
    except Exception:
        logging.exception("Error during audio capture")

    if not recording:
        # write a short silent file to avoid downstream errors
        logging.warning("No audio captured; creating short silent file %s", filename)
        silent = np.zeros(int(0.1 * sample_rate), dtype="int16")
        write(filename, sample_rate, silent)
        return filename

    try:
        audio = np.concatenate(recording, axis=0)
    except Exception:
        logging.exception("Failed to concatenate audio blocks; falling back to last block")
        audio = recording[-1]

    write(filename, sample_rate, audio)

    print(f"✅ Audio saved to {filename}")

    return filename