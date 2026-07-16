from faster_whisper import WhisperModel

print("Loading Whisper model...")

model = WhisperModel("base")


def transcribe_audio(audio_path):
    segments, info = model.transcribe(audio_path, language="en", beam_size=5)

    text = ""

    for segment in segments:
        text += segment.text + " "

    return text.strip()