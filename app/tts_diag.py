import logging
import traceback

try:
    import pyttsx3
except Exception as e:
    print("pyttsx3 import failed:", e)
    raise

print('pyttsx3 OK')

try:
    engine = pyttsx3.init()
    print('Engine created')
    voices = engine.getProperty('voices') or []
    print(f'Found {len(voices)} voices:')
    for i, v in enumerate(voices):
        print(i, repr(getattr(v, 'name', None)), getattr(v, 'id', None))

    # Try to pick a female-sounding voice
    chosen = None
    for v in voices:
        name = (getattr(v, 'name', '') or '').lower()
        if 'female' in name or 'zira' in name or 'sara' in name or 'frau' in name or 'voice' in name:
            chosen = v
            break
    if not chosen and voices:
        chosen = voices[0]

    if chosen:
        try:
            engine.setProperty('voice', chosen.id)
            print('Set voice to', getattr(chosen, 'name', chosen.id))
        except Exception as e:
            print('Failed to set voice:', e)

    # Speak a test phrase synchronously
    test_phrase = 'This is Roha. Diagnostic speech test. If you can hear me, T T S is working.'
    print('Speaking: ', test_phrase)
    engine.say(test_phrase)
    engine.runAndWait()
    print('Speak finished')

except Exception as e:
    print('Diagnostic failed:')
    traceback.print_exc()
