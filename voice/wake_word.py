# voice/wake_word.py

import sounddevice as sd
import numpy as np
import json
import os
from vosk import Model, KaldiRecognizer

MODEL_PATH = "/home/dima/models/vosk-model-ru"

def listen_for_wake_word():
    print("👂 Слушаю... скажите 'Вася'")

    if not os.path.exists(MODEL_PATH):
        print(f"❌ Модель не найдена: {MODEL_PATH}")
        print("📁 Скачай: https://alphacephei.com/vosk/models")
        return

    model = Model(MODEL_PATH)
    rec = KaldiRecognizer(model, 16000)
    rec.SetWords(False)

    with sd.InputStream(samplerate=16000, channels=1, dtype='int16', blocksize=8000) as stream:
        while True:
            data, _ = stream.read(8000)
            data_bytes = np.array(data, dtype=np.int16).tobytes()

            if rec.AcceptWaveform(data_bytes):
                result = json.loads(rec.Result())
                text = result.get("text", "").lower()
                print(f"🗣️ Слышу: {text}")

                if "вася" in text:
                    print("🔊 Услышал 'Вася'!")
                    return
            else:
                # Частичный результат (можно игнорировать)
                pass
