# voice/stt.py

import whisper
import os

MODEL = None

def load_model():
    global MODEL
    if MODEL is None:
        print("🔄 Загрузка Whisper...")
        MODEL = whisper.load_model("small")
    return MODEL

def recognize(audio_path):
    model = load_model()
    result = model.transcribe(audio_path, language="ru", fp16=False)
    text = result["text"].strip()
    os.unlink(audio_path)
    return text
