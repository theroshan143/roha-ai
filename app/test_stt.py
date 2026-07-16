from app.stt import transcribe_audio

text = transcribe_audio("recordings/input.wav")

print("\nRecognized Text:")
print(text)
