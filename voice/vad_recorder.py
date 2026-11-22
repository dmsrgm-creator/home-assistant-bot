# voice/vad_recorder.py
# Запись с VAD: пишет, пока говоришь, останавливается после тишины

import sounddevice as sd
import soundfile as sf
import tempfile
import webrtcvad
import collections

# ============================================================
# НАСТРОЙКИ
# ============================================================

AUDIO_DEVICE = 0           # ReSpeaker Lite
SAMPLE_RATE = 16000        # Whisper + Vosk + webrtcvad — все любят 16000
CHANNELS = 1
DTYPE = 'int16'

# VAD настройки
FRAME_DURATION_MS = 30      # webrtcvad работает с 10/20/30 мс
FRAME_SIZE = int(SAMPLE_RATE * FRAME_DURATION_MS / 1000)  # 480 сэмплов

VAD_MODE = 3                # 0=агрессивный, 3=мягкий (2 — баланс)
SILENCE_DURATION_MS = 1000   # сколько тишины ждать после речи (0.7 сек)
MAX_DURATION_SEC = 7       # максимум записи (защита от зависания)
MIN_DURATION_SEC = 0.3      # минимум записи (короче — считаем шумом)


def record_until_silence(max_duration=MAX_DURATION_SEC):
    """
    Записывает с микрофона, пока пользователь говорит.
    Останавливается после SILENCE_DURATION_MS тишины.
    
    Возвращает путь к WAV или None, если речи не было.
    """
    print(f"🎙️ Слушаю (VAD, макс {max_duration} сек)...")

    vad = webrtcvad.Vad(VAD_MODE)

    # Буфер для аудио
    frames = []
    num_silent_frames = 0
    num_silent_frames_to_stop = SILENCE_DURATION_MS // FRAME_DURATION_MS

    # Открываем поток
    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype=DTYPE,
        blocksize=FRAME_SIZE,
        device=AUDIO_DEVICE
    ) as stream:
        total_frames = 0
        max_frames = int(max_duration * 1000 / FRAME_DURATION_MS)

        # Фаза 1: ждём начала речи (до 3 сек)
        # (если пользователь молчит — не пишем бесконечно)
        speech_started = False
        wait_frames = 0
        max_wait_frames = int(3000 / FRAME_DURATION_MS)  # 3 сек

        while wait_frames < max_wait_frames:
            data, _ = stream.read(FRAME_SIZE)
            data_bytes = data.tobytes()
            wait_frames += 1

            if vad.is_speech(data_bytes, SAMPLE_RATE):
                speech_started = True
                frames.append(data.copy())
                break

        if not speech_started:
            print("🔇 Речь не началась (тишина 3 сек)")
            return None

        # Фаза 2: пишем, пока говорим
        while total_frames < max_frames:
            data, _ = stream.read(FRAME_SIZE)
            data_bytes = data.tobytes()
            frames.append(data.copy())
            total_frames += 1

            if vad.is_speech(data_bytes, SAMPLE_RATE):
                num_silent_frames = 0
            else:
                num_silent_frames += 1
                if num_silent_frames >= num_silent_frames_to_stop:
                    break

    # Склеиваем фреймы
    import numpy as np
    audio = np.concatenate(frames, axis=0)

    duration = len(audio) / SAMPLE_RATE
    print(f"📊 Записано {duration:.1f} сек")

    if duration < MIN_DURATION_SEC:
        print(f"🔇 Слишком коротко ({duration:.1f} сек < {MIN_DURATION_SEC})")
        return None

    # Сохраняем
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        sf.write(tmp.name, audio, SAMPLE_RATE, subtype='PCM_16')
        return tmp.name
