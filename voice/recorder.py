# voice/recorder.py

import sounddevice as sd
import soundfile as sf
import tempfile
import os

USB_DEVICE = 0
SAMPLE_RATE = 44100

def record(duration=5):  # ← теперь параметр
    print(f"🎙️ Запись {duration} сек...")
    recording = sd.rec(int(duration * SAMPLE_RATE),
                       samplerate=SAMPLE_RATE,
                       channels=1,
                       device=USB_DEVICE)
    sd.wait()
    max_amp = abs(recording).max()
    print(f"📊 Амплитуда: {max_amp:.3f}")

    if max_amp < 0.01:
        return None

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        sf.write(tmp.name, recording, SAMPLE_RATE)
        return tmp.name
