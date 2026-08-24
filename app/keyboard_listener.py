import logging

try:
    import keyboard
except ImportError:
    keyboard = None


def watch_for_stop(tts):
    if keyboard is None:
        logging.debug("keyboard module not installed; hotkey listener disabled.")
        return
    try:
        keyboard.add_hotkey("esc", tts.stop)
    except Exception:
        logging.warning("Failed to register ESC hotkey for TTS stop.")