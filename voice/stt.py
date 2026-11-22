# voice/stt.py
import os
from faster_whisper import WhisperModel

MODEL = None

def load_model():
    global MODEL
    if MODEL is None:
        print("🔄 Загрузка faster-whisper...")
        # compute_type="int8" — квантование (быстро на CPU)
        # device="cpu" — без GPU
        MODEL = WhisperModel("base", device="cpu", compute_type="int8")
        print("✅ faster-whisper загружен!")
    return MODEL

def recognize(audio_path):
    model = load_model()
    segments, info = model.transcribe(
        audio_path,
        language="ru",
        beam_size=1,        # 1 = быстрее, 5 = точнее (по умолчанию 5)
        vad_filter=False    # у нас свой VAD, не дублируем
    )
    text = " ".join(seg.text for seg in segments).strip()
    os.unlink(audio_path)
    return text
