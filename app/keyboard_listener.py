import keyboard


def watch_for_stop(tts):
    keyboard.add_hotkey("esc", tts.stop)