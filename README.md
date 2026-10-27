# VoiceChat for World of Warcraft

Talk instead of typing in WoW chat. Hold a key, say *"party, pull in five"*, let go, and
`/p Pull in five` is sent to party chat.

Speech recognition runs locally with [faster-whisper](https://github.com/SYSTRAN/faster-whisper):
it's free, works offline, and your voice never leaves your computer. It works on Windows and macOS.

## Setup

You need Python 3.10 or newer.

- **Windows:** double-click `start.bat`
- **macOS:** double-click `start.command`. If macOS won't open it, right-click it and choose Open.

The first run installs the dependencies and downloads the speech model (about 150 MB).

### macOS permissions
Allow these in **System Settings → Privacy & Security** for Terminal, or for whichever app runs the script:
- **Microphone**: to hear you
- **Accessibility**: to type into WoW
- **Input Monitoring**: to see the push-to-talk key

Restart the script after granting them. On most Mac keyboards F9 is a media key, so hold **fn+F9**
or pick another key.

## Usage

Hold **F9**, speak, and release. Start with a channel word:

| Say | Sends |
|---|---|
| party … | `/p` |
| raid … | `/ra` |
| raid warning … | `/rw` |
| guild … / officer … | `/g` / `/o` |
| instance … / say … / yell … | `/i` / `/s` / `/y` |
| whisper *name* … | `/w name` |
| reply … | `/r` |
| *(no channel word)* | typed into your current channel, then waits for you to press Enter |

End with **"cancel"** or **"scratch that"** to throw the message away. Nothing is typed unless WoW is the active window.

## Settings

The settings are at the top of `voicechat.py`: push-to-talk key, model size (`tiny.en` / `base.en` / `small.en`),
whether messages without a channel word send automatically, beeps, and the channel words.

## Notes

- If WoW runs as administrator on Windows, run the launcher as administrator too.
- WoW chat messages are limited to 255 characters, so longer dictation is sent as several messages.
