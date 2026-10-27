"""
VoiceChat for World of Warcraft (Windows and macOS)
Hold the push-to-talk key, speak, release. Start with a channel word to send it there:

  "party pull in five"        -> /p pull in five
  "raid wipe it, run back"    -> /ra wipe it, run back
  "guild anyone up for a dungeon" -> /g anyone up for a dungeon
  "whisper Bob on my way"     -> /w Bob on my way
  "hello there"               -> typed into your current chat channel (see NO_KEYWORD_SEND)

End a sentence with "cancel" to throw it away.
"""

import re
import subprocess
import sys
import threading
import time

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
from pynput.keyboard import Controller, Key, KeyCode, Listener

# ---------------------------------------------------------------- settings
PUSH_TO_TALK_KEY = "f9"   # hold while speaking; must be unbound in WoW. On a Mac you may need fn+F9.
MODEL_SIZE = "base.en"    # tiny.en (fastest), base.en, small.en (most accurate, slower)
NO_KEYWORD_SEND = False   # no channel word: True = send right away, False = leave it in the chat box for you to check
ONLY_WHEN_WOW_ACTIVE = True
BEEPS = True

CHANNELS = {
    "raid warning": "/rw",
    "party": "/p",
    "raid": "/ra",
    "guild": "/g",
    "officer": "/o",
    "instance": "/i",
    "say": "/s",
    "yell": "/y",
    "reply": "/r",
}
# Helps Whisper spell game words correctly
VOCAB_HINT = "Party, raid, guild. Pull, tank, healer, DPS, mana, wipe, AoE, LFG, LFM, buff, boss, mob, inc, OOM."
# -------------------------------------------------------------------------

SAMPLE_RATE = 16000
MAX_MSG = 255
IS_MAC = sys.platform == "darwin"
WOW_WINDOW = "World of Warcraft"

kb = Controller()
recording = False
chunks = []
lock = threading.Lock()


# ------------------------------------------------------- platform helpers
if IS_MAC:
    from Quartz import (
        CGWindowListCopyWindowInfo,
        kCGNullWindowID,
        kCGWindowListExcludeDesktopElements,
        kCGWindowListOptionOnScreenOnly,
    )

    MAC_SOUNDS = {"start": "Tink", "stop": "Pop", "error": "Basso"}

    def beep(kind):
        if BEEPS:
            subprocess.Popen(["afplay", f"/System/Library/Sounds/{MAC_SOUNDS[kind]}.aiff"])

    def wow_is_active():
        # The first normal-layer on-screen window belongs to the frontmost app
        opts = kCGWindowListOptionOnScreenOnly | kCGWindowListExcludeDesktopElements
        for w in CGWindowListCopyWindowInfo(opts, kCGNullWindowID) or []:
            if w.get("kCGWindowLayer") == 0:
                return WOW_WINDOW in (w.get("kCGWindowOwnerName") or "")
        return False

else:
    import ctypes
    import winsound

    WIN_TONES = {"start": 900, "stop": 600, "error": 300}

    def beep(kind):
        if BEEPS:
            threading.Thread(target=winsound.Beep, args=(WIN_TONES[kind], 80), daemon=True).start()

    def wow_is_active():
        user32 = ctypes.windll.user32
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(user32.GetForegroundWindow(), buf, 256)
        return WOW_WINDOW in buf.value


def parse_key(name):
    name = name.lower()
    return getattr(Key, name) if hasattr(Key, name) else KeyCode.from_char(name)


# ---------------------------------------------------------- text handling
def parse(text):
    """Returns (slash_prefix or None, message)."""
    text = text.strip()
    plain = re.sub(r"^[^\w]+", "", text)
    lower = plain.lower()

    m = re.match(r"whisper\s+(\w+)[\s,.:]*(.*)", lower, re.S)
    if m:
        name = m.group(1).capitalize()
        rest = plain[m.end(1):].lstrip(" ,.:")
        return f"/w {name}", rest

    for word, slash in CHANNELS.items():  # "raid warning" is checked before "raid"
        if re.match(rf"{word}\b", lower):
            return slash, plain[len(word):].lstrip(" ,.:")
    return None, text


def tidy(msg):
    msg = msg.strip()
    if msg.endswith(".") and not msg.endswith(".."):
        msg = msg[:-1]
    return msg[:1].upper() + msg[1:] if msg else msg


def split_message(msg, limit):
    parts, line = [], ""
    for word in msg.split():
        if line and len(line) + 1 + len(word) > limit:
            parts.append(line)
            line = word
        else:
            line = f"{line} {word}" if line else word
    if line:
        parts.append(line)
    return parts


def press_enter():
    kb.press(Key.enter)
    kb.release(Key.enter)


def type_into_wow(prefix, msg, send):
    limit = MAX_MSG - (len(prefix) + 1 if prefix else 0)
    for part in split_message(msg, limit):
        line = f"{prefix} {part}" if prefix else part
        press_enter()  # open the chat box
        time.sleep(0.08)
        for ch in line:  # one key at a time so WoW doesn't drop any
            kb.type(ch)
            time.sleep(0.005)
        if send:
            time.sleep(0.05)
            press_enter()
            time.sleep(0.15)


# --------------------------------------------------------- speech handling
def handle(audio):
    if len(audio) < SAMPLE_RATE * 0.3:  # under 0.3 s: accidental tap
        return
    if not np.any(audio):
        print("  (microphone gave only silence; on a Mac, allow Microphone access for this app)")
        beep("error")
        return
    segments, _ = model.transcribe(
        audio, language="en", beam_size=1, vad_filter=True, initial_prompt=VOCAB_HINT
    )
    text = " ".join(s.text for s in segments).strip()
    if not text:
        print("  (heard nothing)")
        return
    print(f"  heard: {text}")

    if re.search(r"\b(cancel|scratch that)[.!]?$", text, re.I):
        print("  cancelled")
        beep("error")
        return

    prefix, msg = parse(text)
    msg = tidy(msg)
    if not msg:
        return
    if ONLY_WHEN_WOW_ACTIVE and not wow_is_active():
        print("  WoW isn't the active window, not typing")
        beep("error")
        return

    send = prefix is not None or NO_KEYWORD_SEND
    print(f"  -> {prefix + ' ' if prefix else ''}{msg}{'' if send else '   (waiting for you to press Enter)'}")
    type_into_wow(prefix, msg, send)


def audio_callback(indata, frames, t, status):
    if recording:
        chunks.append(indata[:, 0].copy())


def on_press(key):
    global recording
    if key != PTT:
        return
    with lock:
        if recording:  # key auto-repeat
            return
        chunks.clear()
        recording = True
    beep("start")


def on_release(key):
    global recording
    if key != PTT:
        return
    with lock:
        if not recording:
            return
        recording = False
        audio = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)
    beep("stop")
    threading.Thread(target=handle, args=(audio,), daemon=True).start()


if __name__ == "__main__":
    PTT = parse_key(PUSH_TO_TALK_KEY)

    print(f"Loading speech model '{MODEL_SIZE}' (first run downloads it)...")
    model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32", callback=audio_callback), \
            Listener(on_press=on_press, on_release=on_release) as listener:
        if IS_MAC and not getattr(listener, "IS_TRUSTED", True):
            print("\n!! macOS is blocking keyboard access. Open System Settings > Privacy & Security and")
            print("!! allow Terminal under both 'Accessibility' and 'Input Monitoring', then restart this.\n")
        print(f"Ready. Hold {PUSH_TO_TALK_KEY.upper()} in WoW and speak. Ctrl+C here to quit.")
        try:
            listener.join()
        except KeyboardInterrupt:
            pass
