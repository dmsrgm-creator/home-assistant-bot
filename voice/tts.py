# voice/tts.py

#import subprocess
#import os

#PIPER_MODEL = "/home/dima/models/ru_RU-dmitri-medium.onnx"
#OUTPUT_WAV = "/home/dima/tts_output.wav"

#def speak(text):
#    print(f"🗣️ Озвучиваю: {text}")
#    subprocess.run([
#        "piper",
#        "--model", PIPER_MODEL,
#        "--text", text,
#        "--output_file", OUTPUT_WAV
#    ], check=True)
#    return OUTPUT_WAV

# voice/tts.py
import subprocess

PIPER_MODEL = "/home/dima/models/ru_RU-dmitri-medium.onnx"
OUTPUT_WAV = "/home/dima/tts_output.wav"

def speak(text):
    print(f"🗣️ Озвучиваю: {text}")
    
    # Piper читает текст из stdin, а не из --text
    result = subprocess.run(
        [
            "piper",
            "--model", PIPER_MODEL,
            "--output_file", OUTPUT_WAV
        ],
        input=text.encode("utf-8"),   # 👈 текст через stdin
        check=True
    )
    return OUTPUT_WAV
