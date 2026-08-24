import logging
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
    """Record for a fixed duration."""
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
    silence_threshold=400,
    silence_duration=1.2,
    initial_silence_timeout=4.0,
    max_duration=15.0,
):
    """
    Record audio with adaptive silence detection & voice activity tracking.

    - Uses dynamic ambient noise calibration during the first ~200ms.
    - Waits up to initial_silence_timeout if the user hasn't started speaking yet.
    - Stops recording after silence_duration of silence ONCE speech has started.
    - Caps total recording time at max_duration (default 15s instead of 3.5s).
    """
    os.makedirs(os.path.dirname(filename) or "recordings", exist_ok=True)

    print("🎤 Listening... (speak naturally)")

    recording = []
    silence_start = None
    start_time = time.time()
    speech_started = False

    block_size = int(sample_rate * 0.1)  # 100 ms blocks for faster reaction

    try:
        with sd.InputStream(
            samplerate=sample_rate,
            channels=1,
            dtype="int16",
            blocksize=block_size,
        ) as stream:

            # Calibrate ambient noise floor from initial blocks
            ambient_samples = []
            for _ in range(2):
                block, _ = stream.read(block_size)
                if block is not None and len(block) > 0:
                    ambient_samples.append(block)

            if ambient_samples:
                ambient_concat = np.concatenate(ambient_samples, axis=0)
                ambient_rms = float(np.sqrt(np.mean(ambient_concat.astype(np.float32) ** 2)))
                dynamic_threshold = max(silence_threshold, ambient_rms * 2.0 + 150)
            else:
                dynamic_threshold = silence_threshold

            while True:
                block, overflowed = stream.read(block_size)
                if overflowed:
                    logging.debug("Audio buffer overflowed")

                if block is not None and len(block) > 0:
                    recording.append(block)

                try:
                    rms = float(np.sqrt(np.mean(block.astype(np.float32) ** 2)))
                except Exception:
                    rms = 0.0

                now = time.time()
                elapsed = now - start_time

                if rms > dynamic_threshold:
                    if not speech_started:
                        speech_started = True
                        print("🗣️  Speech detected...")
                    silence_start = None
                else:
                    if silence_start is None:
                        silence_start = now
                    else:
                        silence_elapsed = now - silence_start
                        if speech_started:
                            if silence_elapsed >= silence_duration:
                                print("🛑 Silence detected (end of speech).")
                                break
                        else:
                            if elapsed >= initial_silence_timeout:
                                print("⏱  No speech detected within timeout.")
                                break

                if elapsed >= max_duration:
                    print("⏱  Maximum recording duration reached.")
                    break

    except Exception:
        logging.exception("Error during audio capture")

    if not recording:
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
    print(f"✅ Audio saved ({len(audio) / sample_rate:.1f}s)")
    return filename