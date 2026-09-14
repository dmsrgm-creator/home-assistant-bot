# voice/listener.py

import sounddevice as sd
import numpy as np
import time

USB_DEVICE = 0
SAMPLE_RATE = 16000
CHUNK = 1024

def listen_for_wake_word(wake_word="вася"):
    print(f"👂 Слушаю... скажите '{wake_word}'")
    stream = sd.InputStream(device=USB_DEVICE,
                            samplerate=SAMPLE_RATE,
                            channels=1,
                            blocksize=CHUNK)

    with stream:
        while True:
            data, _ = stream.read(CHUNK)
            # 🧠 Пока просто заглушка — ждём Enter
            # В будущем здесь будет реальный детектор (Porcupine / Vosk)
            time.sleep(0.1)
