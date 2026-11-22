# voice/voice_controller.py
import sys
import os
import time


# Добавляем корень проекта в путь импорта
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from vad_recorder import record_until_silence
from stt import recognize
from tts import speak
from player import play
from wake_word import listen_for_wake_word
from command_processor import process_command
from llm_client import generate

def main():
    print("🎤 Голосовой ассистент 'Вася'")
    print("👂 Скажите 'Вася' для активации...")

    while True:
        # 1. Ждём пробуждения
        listen_for_wake_word()

        # 2. Пауза 0.5 сек — пользователь начинает команду
        time.sleep(0.5)

        # 3. VAD записывает команду (до тишины)
        audio_path = record_until_silence()
        if audio_path is None:
            print("❌ Тихо, попробуй ещё.")
            continue

        # 4. Распознавание
        text = recognize(audio_path)
        print(f"📝 Распознано: {text}")

        if not text:
            reply = "Не расслышал, повторите."
            wav = speak(reply)
            play(wav)
            continue

        # 5. Общая логика
        result = process_command(text, source="local")
        print(f"🎯 Интент: {result['intent']}, успех: {result['success']}")

        reply = result["reply"]

        # 6. Если local не распознал — reply=None
        if reply is None:
            #reply = "Не понял команду"
            print("🤔 LLM думает...")
            reply = generate(text, max_tokens=64)
        # 7. Озвучиваем только если speak=True
        if result.get("speak", True):
            print(f"🗣️ Говорю: {reply}")
            wav = speak(reply)
            play(wav)
        else:
            print(f"✅ Выполнено: {reply}")


if __name__ == "__main__":
    main()
