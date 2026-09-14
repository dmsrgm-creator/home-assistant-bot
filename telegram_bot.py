# telegram_bot.py - ВЕРСИЯ 3.2 (с ТВ и датчиками)

import logging
import os
import time
import threading
import gc
import re
import subprocess
import tempfile
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from llama_cpp import Llama
import whisper

# Импортируем функции HA
from ha_integration import (
    get_ha_time,
    get_ha_date,
    get_ha_datetime,
    handle_volume,
    turn_on_tv,
    turn_off_tv,
    handle_temperature
)

# ============================================================
# 1. ЗАГРУЗКА ПЕРЕМЕННЫХ ИЗ .env
# ============================================================

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN не найден в .env файле!")

# ============================================================
# 2. ЛОГИРОВАНИЕ
# ============================================================

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================================================
# 3. НАСТРОЙКИ МОДЕЛИ
# ============================================================

MODEL_PATH = "/home/dima/models/qwen2.5-1.5b-instruct-q4_k_m.gguf"
BOT_NAME = "Вася"

MODEL_CONFIG = {
    "n_ctx": 1024,
    "n_threads": 2,
    "n_gpu_layers": 0,
    "verbose": False
}

# ============================================================
# 4. УМНОЕ УПРАВЛЕНИЕ ПАМЯТЬЮ (LLM)
# ============================================================

llm = None
last_used = time.time()

def get_unload_timeout():
    hour = datetime.now().hour
    if 17 <= hour <= 24:
        return None
    else:
        return 60 * 30

def should_unload_model():
    global llm
    if llm is None:
        return False
    timeout = get_unload_timeout()
    if timeout is None:
        return False
    return (time.time() - last_used) > timeout

def get_llm():
    global llm, last_used
    if llm is None:
        logger.info("🔄 Загрузка LLM...")
        llm = Llama(model_path=MODEL_PATH, **MODEL_CONFIG)
        logger.info("✅ LLM загружена!")
    last_used = time.time()
    return llm

def unload_worker():
    global llm
    while True:
        time.sleep(60)
        if should_unload_model():
            logger.info("⏳ Выгружаем LLM...")
            llm = None
            gc.collect()

thread = threading.Thread(target=unload_worker, daemon=True)
thread.start()
logger.info("🧠 Фоновый поток управления памятью запущен")

# ============================================================
# 5. WHISPER (ленивая загрузка)
# ============================================================

whisper_model = None

def get_whisper_model():
    global whisper_model
    if whisper_model is None:
        logger.info("🔄 Загрузка Whisper...")
        whisper_model = whisper.load_model("base")
        logger.info("✅ Whisper загружен!")
    return whisper_model

# ============================================================
# 6. ИСТОРИЯ ДИАЛОГОВ
# ============================================================

SYSTEM_PROMPT = "Ты полезный домашний ассистент. Отвечаешь кратко и по делу на русском языке. Если не знаешь точного ответа — скажи 'не знаю' вместо выдумывания."

user_histories = {}

def get_user_history(user_id):
    if user_id not in user_histories:
        user_histories[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    return user_histories[user_id]

def trim_history(history, max_messages=10):
    if len(history) > max_messages:
        return [history[0]] + history[-(max_messages-1):]
    return history

# ============================================================
# 7. АКТИВАЦИЯ ПО ИМЕНИ
# ============================================================

def extract_query(text):
    if not text:
        return None, False
    
    text_lower = text.lower()
    name_variants = ["вася", "васья", "васенька", "василий"]
    
    for name in name_variants:
        if text_lower.startswith(name):
            cleaned = text[len(name):].lstrip(", .!?;: \t\n")
            return cleaned, True
    
    return text, False

# ============================================================
# 8. ОПРЕДЕЛЕНИЕ ТИПА ЗАПРОСА (ДЛЯ LLM)
# ============================================================

def detect_query_type(text):
    text_lower = text.lower()
    fact_keywords = ["кто такой", "что такое", "кто это", "что это", "где находится", "когда был", "сколько будет", "какой", "какая", "какое", "какие"]
    if any(word in text_lower for word in fact_keywords):
        return "fact"
    history_keywords = ["расскажи", "расскажи про", "история", "произошло", "в каком году", "как", "почему", "зачем", "объясни", "опиши", "что значит"]
    if any(word in text_lower for word in history_keywords):
        return "history"
    creative_keywords = ["напиши стих", "сочини", "придумай", "расскажи историю", "придумай рассказ", "создай", "стихотворение", "поэма"]
    if any(word in text_lower for word in creative_keywords):
        return "creative"
    return "dialogue"

def get_generation_config(query_type):
    configs = {
        "fact": {"max_tokens": 128, "temperature": 0.3, "top_p": 0.85, "repeat_penalty": 1.1},
        "history": {"max_tokens": 256, "temperature": 0.5, "top_p": 0.85, "repeat_penalty": 1.1},
        "creative": {"max_tokens": 512, "temperature": 0.8, "top_p": 0.9, "repeat_penalty": 1.1},
        "dialogue": {"max_tokens": 256, "temperature": 0.6, "top_p": 0.85, "repeat_penalty": 1.1}
    }
    return configs.get(query_type, configs["dialogue"])

# ============================================================
# 9. ГИБРИДНЫЙ ДЕТЕКТ КОМАНД (INTENT DETECTION)
# ============================================================

def detect_intent(text):
    text_lower = text.lower()
    
    # ===== ТЕЛЕВИЗОР (включить/выключить) =====
    if any(word in text_lower for word in ["телевизор", "телек", "тв"]):
        if any(word in text_lower for word in ["включи", "вкл", "зажги", "вруби"]):
            return "tv_on", {}
        elif any(word in text_lower for word in ["выключи", "выкл", "погаси", "выруби"]):
            return "tv_off", {}
    
    # ===== ТЕМПЕРАТУРА / ВЛАЖНОСТЬ =====
    if any(word in text_lower for word in ["температур", "градус", "влажност"]):
        return "sensor", {"text": text}
    
    # ===== ГРОМКОСТЬ =====
    volume_keywords = ["громк", "громче", "тише", "звук", "громкость", "чуть", "еще"]
    if any(word in text_lower for word in volume_keywords):
        return "volume", {"text": text}
    
    # ===== ВРЕМЯ =====
    time_keywords = ["время", "часов", "час", "сколько времени", "который час", "скажи время", "времени", "сколько сейчас", "текущее время", "покажи время"]
    if any(word in text_lower for word in time_keywords):
        return "time", {}
    
    # ===== ДАТА =====
    date_keywords = ["дата", "число", "какой сегодня", "сегодняшняя дата"]
    if any(word in text_lower for word in date_keywords):
        return "date", {}
    
    # ===== ПОГОДА (заготовка) =====
    weather_keywords = ["погод", "дождь", "солнце", "облачно", "ветер", "тучи"]
    if any(word in text_lower for word in weather_keywords):
        return "weather", {"text": text}
    
    # ===== СВЕТ =====
    if "свет" in text_lower:
        if any(word in text_lower for word in ["включи", "вкл", "зажги"]):
            return "light_on", {"room": extract_room(text)}
        elif any(word in text_lower for word in ["выключи", "выкл", "погаси"]):
            return "light_off", {"room": extract_room(text)}
    
    return "unknown", {}

def extract_room(text):
    rooms = ["гостиная", "кухня", "спальня", "ванная", "коридор", "комната"]
    for room in rooms:
        if room in text.lower():
            return room
    return "комната"

# ============================================================
# 10. ОБРАБОТЧИКИ НАВЫКОВ (SKILLS)
# ============================================================

def handle_time():
    return get_ha_time()

def handle_date():
    return get_ha_date()

def handle_light_on(room):
    return f"💡 Включаю свет в {room}"

def handle_light_off(room):
    return f"💡 Выключаю свет в {room}"

def handle_weather(text):
    return "☀️ На улице солнечно, +25°C"  # заготовка

# ============================================================
# 11. ГЕНЕРАЦИЯ ОТВЕТА (LLM)
# ============================================================

def generate_response(user_message, user_id):
    history = get_user_history(user_id)
    history.append({"role": "user", "content": user_message})
    history = trim_history(history)
    
    query_type = detect_query_type(user_message)
    logger.info(f"📝 Тип запроса: {query_type}")
    gen_config = get_generation_config(query_type)
    
    model = get_llm()
    response = model.create_chat_completion(messages=history, **gen_config)
    reply = response["choices"][0]["message"]["content"]
    history.append({"role": "assistant", "content": reply})
    return reply

# ============================================================
# 12. ОБРАБОТЧИК ГОЛОСОВЫХ СООБЩЕНИЙ
# ============================================================

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает голосовые сообщения из Telegram"""
    try:
        voice = update.message.voice
        file = await context.bot.get_file(voice.file_id)
        
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            await file.download_to_drive(tmp.name)
            ogg_path = tmp.name
        
        wav_path = ogg_path.replace(".ogg", ".wav")
        subprocess.run([
            "ffmpeg", "-i", ogg_path, "-ar", "16000", "-ac", "1",
            "-c:a", "pcm_s16le", wav_path, "-y"
        ], capture_output=True)
        os.unlink(ogg_path)
        
        model = get_whisper_model()
        result = model.transcribe(wav_path, language="ru", fp16=False)
        text = result["text"].strip()
        os.unlink(wav_path)
        
        if not text:
            await update.message.reply_text("😅 Не расслышал, повтори пожалуйста.")
            return
        
        logger.info(f"🎤 Распознано: {text}")
        
        user_id = update.effective_user.id
        is_group = update.effective_chat.type in ["group", "supergroup"]
        
        if is_group:
            clean_text, should_reply = extract_query(text)
            if not should_reply:
                await update.message.reply_text("👋 Чтобы обратиться ко мне, скажи 'Вася, ...'")
                return
        else:
            clean_text = text
        
        if not clean_text or clean_text.isspace():
            await update.message.reply_text("Слушаю...")
            return
        
        intent, params = detect_intent(clean_text)
        
        if intent == "time":
            reply = handle_time()
        elif intent == "date":
            reply = handle_date()
        elif intent == "sensor":
            reply = handle_temperature(params.get("text", ""))
            if reply is None:
                reply = "Не понял, какой датчик?"
        elif intent == "tv_on":
            success, reply = turn_on_tv()
        elif intent == "tv_off":
            success, reply = turn_off_tv()
        elif intent == "weather":
            reply = handle_weather(params.get("text", ""))
        elif intent == "light_on":
            reply = handle_light_on(params.get("room", "комната"))
        elif intent == "light_off":
            reply = handle_light_off(params.get("room", "комната"))
        elif intent == "volume":
            reply = handle_volume(params.get("text", ""))
            if reply is None:
                reply = generate_response(clean_text, user_id)
        else:
            reply = generate_response(clean_text, user_id)
        
        await update.message.reply_text(reply)
        
    except Exception as e:
        logger.error(f"Ошибка обработки голоса: {e}")
        await update.message.reply_text("😅 Ошибка при распознавании речи. Попробуйте текстом.")

# ============================================================
# 13. ОБРАБОТЧИКИ КОМАНД
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"👋 Привет! Я {BOT_NAME}, твой домашний ассистент.\n\n"
        f"💡 Я понимаю команды:\n"
        f"• 'сколько время?' — покажу время\n"
        f"• 'какая дата?' — покажу дату\n"
        f"• 'включи/выключи телевизор' — управление ТВ\n"
        f"• 'сколько градусов на улице' — температура\n"
        f"• 'какая влажность у Миши' — влажность\n"
        f"• 'громкость 50' — установить громкость\n"
        f"• 'еще громче' — увеличить громкость\n"
        f"• 'выключи звук' — выключить звук\n"
        f"• 'кто такой Иван Грозный?' — отвечу на вопросы\n"
        f"• 'напиши стих про осень' — сочиню стих\n\n"
        f"🎤 Отправь голосовое сообщение — я распознаю!\n\n"
        f"Команды:\n"
        f"/time, /date, /clear, /stats, /unload"
    )

async def time_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🕐 {get_ha_time()}")

async def date_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"📅 {get_ha_date()}")

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_histories[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    await update.message.reply_text("🧹 История очищена!")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    history = get_user_history(user_id)
    msg_count = len([m for m in history if m["role"] == "user"])
    model_loaded = "✅" if llm is not None else "❌"
    whisper_loaded = "✅" if whisper_model is not None else "❌"
    await update.message.reply_text(
        f"📊 Статистика:\n"
        f"- Сообщений в диалоге: {msg_count}\n"
        f"- Контекст: {MODEL_CONFIG['n_ctx']} токенов\n"
        f"- LLM в памяти: {model_loaded}\n"
        f"- Whisper в памяти: {whisper_loaded}\n"
        f"- Режим: {'🌙 Вечерний' if 17 <= datetime.now().hour <= 24 else '☀️ Дневный'}"
    )

async def unload_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global llm, whisper_model
    if llm is not None:
        llm = None
        gc.collect()
    if whisper_model is not None:
        whisper_model = None
        gc.collect()
    await update.message.reply_text("💾 Модели выгружены из памяти!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    if not text:
        return
    
    is_group = update.effective_chat.type in ["group", "supergroup"]
    is_private = update.effective_chat.type == "private"
    
    if is_private:
        clean_text = text
        should_reply = True
    else:
        clean_text, should_reply = extract_query(text)
        if not should_reply:
            return
    
    if not clean_text or clean_text.isspace():
        await update.message.reply_text("Слушаю...")
        return
    
    try:
        await update.message.chat.send_action(action="typing")
        
        intent, params = detect_intent(clean_text)
        
        if intent == "time":
            reply = handle_time()
        elif intent == "date":
            reply = handle_date()
        elif intent == "sensor":
            reply = handle_temperature(params.get("text", ""))
            if reply is None:
                reply = "Не понял, какой датчик?"
        elif intent == "tv_on":
            success, reply = turn_on_tv()
        elif intent == "tv_off":
            success, reply = turn_off_tv()
        elif intent == "weather":
            reply = handle_weather(params.get("text", ""))
        elif intent == "light_on":
            reply = handle_light_on(params.get("room", "комната"))
        elif intent == "light_off":
            reply = handle_light_off(params.get("room", "комната"))
        elif intent == "volume":
            reply = handle_volume(params.get("text", ""))
            if reply is None:
                reply = generate_response(clean_text, user_id)
        else:
            reply = generate_response(clean_text, user_id)
        
        await update.message.reply_text(reply)
        
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await update.message.reply_text("😅 Ошибка. Попробуйте /clear или подождите.")

# ============================================================
# 14. ЗАПУСК БОТА
# ============================================================

def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("time", time_command))
    application.add_handler(CommandHandler("date", date_command))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("unload", unload_command))
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    
    logger.info("🚀 Бот запущен! Жду сообщения...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
