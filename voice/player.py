# voice/player.py

import subprocess

OUTPUT_DEVICE = "plughw:0,0"

def play(wav_path):
    subprocess.run(["aplay", "-D", OUTPUT_DEVICE, wav_path], check=True)
