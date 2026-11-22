# voice/wake_word.py
import sounddevice as sd
import numpy as np
import json
import os
from vosk import Model, KaldiRecognizer

# ============================================================
# НАСТРОЙКИ
# ============================================================

MODEL_PATH = "/home/dima/models/vosk-model-ru"
AUDIO_DEVICE = 0        # ReSpeaker Lite (карта 0)
SAMPLE_RATE = 16000     # Vosk ждёт 16000 — не меняй!
BLOCKSIZE = 8000        # 0.5 сек при 16000 Гц — оптимально для wake word


def listen_for_wake_word():
    """Блокируется, пока не услышит 'Вася'"""
    print("👂 Слушаю... скажите 'Вася'")

    if not os.path.exists(MODEL_PATH):
        print(f"❌ Модель не найдена: {MODEL_PATH}")
        print("📁 Скачай: https://alphacephei.com/vosk/models")
        return

    model = Model(MODEL_PATH)
    rec = KaldiRecognizer(model, SAMPLE_RATE)
    rec.SetWords(False)

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype='int16',
        blocksize=BLOCKSIZE,
        device=AUDIO_DEVICE      # 👈 ReSpeaker, а не дефолт
    ) as stream:
        while True:
            data, _ = stream.read(BLOCKSIZE)
            data_bytes = np.array(data, dtype=np.int16).tobytes()

            if rec.AcceptWaveform(data_bytes):
                result = json.loads(rec.Result())
                text = result.get("text", "").lower()
                print(f"🗣️ Слышу: {text}")

                if "вася" in text:
                    print("🔊 Услышал 'Вася'!")
                    return
