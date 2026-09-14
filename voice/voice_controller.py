# voice/voice_controller.py

from recorder import record
from stt import recognize
from tts import speak
from player import play
from wake_word import listen_for_wake_word

def main():
    print("🎤 Голосовой ассистент 'Вася'")
    print("👂 Скажите 'Вася' для активации...")

    while True:
        # 1. Ждём пробуждения
        listen_for_wake_word()

        # 2. Голосовое подтверждение
        speak("Да, я слушаю.")
        play("/home/dima/tts_output.wav")  # воспроизводим подтверждение

        # 3. Запись 5 секунд
        audio_path = record(duration=5)  # теперь 5 секунд, не 7
        if audio_path is None:
            print("❌ Тихо, попробуй ещё.")
            continue

        # 4. Распознавание
        text = recognize(audio_path)
        print(f"📝 Распознано: {text}")

        if not text:
            reply = "Не расслышал, повторите."
        else:
            # ❗ ВРЕМЕННО: эхо
            reply = f"Вы сказали: {text}"

        wav = speak(reply)
        play(wav)

if __name__ == "__main__":
    main()
