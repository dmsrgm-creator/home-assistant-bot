# voice/recorder.py
import sounddevice as sd
import soundfile as sf
import tempfile

# ============================================================
# НАСТРОЙКИ
# ============================================================

AUDIO_DEVICE = 0        # ReSpeaker Lite (карта 0 в этой ВМ)
SAMPLE_RATE = 16000     # Whisper обучен на 16000 Гц — не меняй!
CHANNELS = 1            # моно
DTYPE = 'int16'         # XMOS отдаёт int16 нативно, без конвертации

# Порог тишины для int16 (диапазон -32768..32767).
# 500 — отсекает шум XMOS, но не режет тихую речь.
SILENCE_THRESHOLD = 500


def record(duration=5):
    """
    Записывает audio с ReSpeaker (карта 0).
    Возвращает путь к WAV-файлу или None, если тишина.
    """
    print(f"🎙️ Запись {duration} сек...")

    recording = sd.rec(
        int(duration * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype=DTYPE,
        device=AUDIO_DEVICE
    )
    sd.wait()

    max_amp = abs(recording).max()
    print(f"📊 Амплитуда: {max_amp}")

    # Проверка на тишину
    if max_amp < SILENCE_THRESHOLD:
        print("🔇 Слишком тихо, пропускаю")
        return None

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        sf.write(tmp.name, recording, SAMPLE_RATE, subtype='PCM_16')
        return tmp.name
