# telegram_bot.py - ВЕРСИЯ 2.2 (с динамическими токенами)

import logging
import os
import time
import threading
import gc
import re
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from llama_cpp import Llama

# Импортируем функции HA
from ha_integration import get_ha_time, get_ha_date, get_ha_datetime

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

# Базовые настройки модели
MODEL_CONFIG = {
    "n_ctx": 1024,
    "n_threads": 2,
    "n_gpu_layers": 0,
    "verbose": False
}

# ============================================================
# 4. УМНОЕ УПРАВЛЕНИЕ ПАМЯТЬЮ
# ============================================================

llm = None
last_used = time.time()

def get_unload_timeout():
    """Динамический таймаут в зависимости от времени суток"""
    hour = datetime.now().hour
    
    # Вечер (пик активности) - модель всегда в памяти
    if 17 <= hour <= 24:
        return None  # никогда не выгружать
    
    # Ночь, утро, день - экономим ресурсы
    else:
        return 60 * 30  # 30 минут бездействия

def should_unload_model():
    """Проверяет, нужно ли выгрузить модель"""
    global llm
    if llm is None:
        return False
    
    timeout = get_unload_timeout()
    if timeout is None:
        return False  # никогда не выгружать
    
    idle_time = time.time() - last_used
    return idle_time > timeout

def get_llm():
    """Загружает модель в память при первом обращении"""
    global llm, last_used
    if llm is None:
        logger.info("🔄 Загрузка модели...")
        llm = Llama(model_path=MODEL_PATH, **MODEL_CONFIG)
        logger.info("✅ Модель загружена!")
    last_used = time.time()
    return llm

def unload_worker():
    """Фоновый поток с умной выгрузкой"""
    global llm
    while True:
        time.sleep(60)
        
        if should_unload_model():
            logger.info("⏳ Выгружаем модель (ночное/дневное время)")
            llm = None
            gc.collect()
            logger.info("✅ Модель выгружена, память освобождена")

def preload_model():
    """Загружает модель при старте бота (если вечер)"""
    hour = datetime.now().hour
    if 17 <= hour <= 24:
        logger.info("🌙 Вечерний режим: предзагружаем модель...")
        get_llm()
        logger.info("✅ Модель предзагружена")
    else:
        logger.info("☀️ Дневной режим: модель будет загружена по требованию")

# Запускаем фоновый поток выгрузки
thread = threading.Thread(target=unload_worker, daemon=True)
thread.start()
logger.info("🧠 Фоновый поток управления памятью запущен")

# ============================================================
# 5. ОПРЕДЕЛЕНИЕ ТИПА ЗАПРОСА (ДЛЯ ДИНАМИЧЕСКИХ НАСТРОЕК)
# ============================================================

def detect_query_type(text):
    """
    Определяет тип запроса для выбора настроек генерации
    
    Возвращает:
        "fact" - факты (короткие ответы)
        "history" - история, рассказы
        "creative" - творчество, стихи
        "dialogue" - обычный диалог
    """
    text_lower = text.lower()
    
    # Признаки запроса факта
    fact_keywords = [
        "кто такой", "что такое", "кто это", "что это",
        "где находится", "когда был", "сколько будет",
        "какой", "какая", "какое", "какие"
    ]
    if any(word in text_lower for word in fact_keywords):
        return "fact"
    
    # Признаки запроса истории/рассказа
    history_keywords = [
        "расскажи", "расскажи про", "история", "произошло",
        "в каком году", "как", "почему", "зачем",
        "объясни", "опиши", "что значит"
    ]
    if any(word in text_lower for word in history_keywords):
        return "history"
    
    # Признаки творческого запроса
    creative_keywords = [
        "напиши стих", "сочини", "придумай", "расскажи историю",
        "придумай рассказ", "создай", "стихотворение", "поэма"
    ]
    if any(word in text_lower for word in creative_keywords):
        return "creative"
    
    # По умолчанию - диалог
    return "dialogue"

def get_generation_config(query_type):
    """
    Возвращает настройки генерации в зависимости от типа запроса
    """
    configs = {
        "fact": {
            "max_tokens": 128,
            "temperature": 0.3,
            "top_p": 0.85,
            "repeat_penalty": 1.1
        },
        "history": {
            "max_tokens": 256,
            "temperature": 0.5,
            "top_p": 0.85,
            "repeat_penalty": 1.1
        },
        "creative": {
            "max_tokens": 512,
            "temperature": 0.8,
            "top_p": 0.9,
            "repeat_penalty": 1.1
        },
        "dialogue": {
            "max_tokens": 256,
            "temperature": 0.6,
            "top_p": 0.85,
            "repeat_penalty": 1.1
        }
    }
    return configs.get(query_type, configs["dialogue"])

# ============================================================
# 6. ГИБРИДНЫЙ ДЕТЕКТ КОМАНД (INTENT DETECTION)
# ============================================================

def detect_intent(text):
    """Определяет намерение пользователя по ключевым словам"""
    text_lower = text.lower()
    
    # ВРЕМЯ
    time_keywords = [
        "время", "часов", "час", "сколько времени", 
        "который час", "скажи время", "времени",
        "сколько сейчас", "текущее время", "покажи время"
    ]
    if any(word in text_lower for word in time_keywords):
        return "time", {}
    
    # ДАТА
    date_keywords = ["дата", "число", "какой сегодня", "сегодняшняя дата"]
    if any(word in text_lower for word in date_keywords):
        return "date", {}
    
    # ТЕМПЕРАТУРА
    temp_keywords = ["температур", "градус", "холодно", "жарко", "тепло", "сколько градусов"]
    if any(word in text_lower for word in temp_keywords):
        return "temperature", {"text": text}
    
    # ПОГОДА
    weather_keywords = ["погод", "дождь", "солнце", "облачно", "ветер", "тучи"]
    if any(word in text_lower for word in weather_keywords):
        return "weather", {"text": text}
    
    # СВЕТ
    if "свет" in text_lower:
        if any(word in text_lower for word in ["включи", "вкл", "зажги"]):
            return "light_on", {"room": extract_room(text)}
        elif any(word in text_lower for word in ["выключи", "выкл", "погаси"]):
            return "light_off", {"room": extract_room(text)}
    
    # ТЕЛЕВИЗОР
    if any(word in text_lower for word in ["телек", "телевизор", "тв"]):
        if "громче" in text_lower:
            return "tv_volume_up", {}
        elif "тише" in text_lower:
            return "tv_volume_down", {}
    
    return "unknown", {}

def extract_room(text):
    """Извлекает название комнаты из текста"""
    rooms = ["гостиная", "кухня", "спальня", "ванная", "коридор", "комната"]
    for room in rooms:
        if room in text.lower():
            return room
    return "комната"

# ============================================================
# 7. ОБРАБОТЧИКИ НАВЫКОВ (SKILLS)
# ============================================================

def handle_time():
    return get_ha_time()

def handle_date():
    return get_ha_date()

def handle_temperature(text):
    return "🌡️ Температура в доме: 24°C"

def handle_weather(text):
    return "☀️ На улице солнечно, +25°C"

def handle_light_on(room):
    return f"💡 Включаю свет в {room}"

def handle_light_off(room):
    return f"💡 Выключаю свет в {room}"

def handle_tv_volume_up():
    return "🔊 Увеличиваю громкость телевизора"

def handle_tv_volume_down():
    return "🔉 Уменьшаю громкость телевизора"

# ============================================================
# 8. ИСТОРИЯ ДИАЛОГОВ
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
# 9. АКТИВАЦИЯ ПО ИМЕНИ
# ============================================================

def extract_query(text):
    if not text:
        return None, False
    
    text_lower = text.lower()
    name_lower = BOT_NAME.lower()
    
    if text_lower.startswith(name_lower):
        cleaned = text[len(BOT_NAME):].lstrip(", .!?;: \t\n")
        return cleaned, True
    
    return text, False

# ============================================================
# 10. ГЕНЕРАЦИЯ ОТВЕТА (LLM) - С ДИНАМИЧЕСКИМИ НАСТРОЙКАМИ
# ============================================================

def generate_response(user_message, user_id):
    """
    Генерирует ответ с помощью LLM с динамическими настройками
    в зависимости от типа запроса
    """
    # Получаем историю диалога
    history = get_user_history(user_id)
    history.append({"role": "user", "content": user_message})
    history = trim_history(history)
    
    # Определяем тип запроса
    query_type = detect_query_type(user_message)
    logger.info(f"📝 Тип запроса: {query_type}")
    
    # Получаем настройки для этого типа
    gen_config = get_generation_config(query_type)
    logger.info(f"⚙️ Настройки: max_tokens={gen_config['max_tokens']}, temp={gen_config['temperature']}")
    
    # Загружаем модель
    model = get_llm()
    
    # Генерируем ответ
    response = model.create_chat_completion(
        messages=history,
        **gen_config
    )
    
    reply = response["choices"][0]["message"]["content"]
    history.append({"role": "assistant", "content": reply})
    return reply

# ============================================================
# 11. ОБРАБОТЧИКИ КОМАНД
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"👋 Привет! Я {BOT_NAME}, твой домашний ассистент.\n\n"
        f"💡 Я понимаю команды:\n"
        f"• 'сколько время?' — покажу время\n"
        f"• 'какая дата?' — покажу дату\n"
        f"• 'включи свет в гостиной' — управление светом\n"
        f"• 'сделай громче телек' — управление ТВ\n"
        f"• 'кто такой Иван Грозный?' — отвечу на вопросы\n"
        f"• 'расскажи про Петра I' — расскажу историю\n"
        f"• 'напиши стих про осень' — сочиню стих\n\n"
        f"Команды:\n"
        f"/time, /date, /clear, /stats, /unload"
    )

async def time_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    time_str = get_ha_time()
    await update.message.reply_text(f"🕐 {time_str}")

async def date_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    date_str = get_ha_date()
    await update.message.reply_text(f"📅 {date_str}")

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_histories[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    await update.message.reply_text("🧹 История очищена!")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    history = get_user_history(user_id)
    msg_count = len([m for m in history if m["role"] == "user"])
    model_loaded = "✅" if llm is not None else "❌"
    await update.message.reply_text(
        f"📊 Статистика:\n"
        f"- Сообщений в диалоге: {msg_count}\n"
        f"- Контекст: {MODEL_CONFIG['n_ctx']} токенов\n"
        f"- Модель в памяти: {model_loaded}\n"
        f"- Режим: {'🌙 Вечерний' if 17 <= datetime.now().hour <= 24 else '☀️ Дневный'}"
    )

async def unload_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global llm
    if llm is not None:
        llm = None
        gc.collect()
        await update.message.reply_text("💾 Модель выгружена из памяти!")
    else:
        await update.message.reply_text("⚠️ Модель и так не загружена.")

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
        
        # ГИБРИДНЫЙ ПОДХОД: сначала проверяем интенты
        intent, params = detect_intent(clean_text)
        
        if intent == "time":
            reply = handle_time()
        elif intent == "date":
            reply = handle_date()
        elif intent == "temperature":
            reply = handle_temperature(params.get("text", ""))
        elif intent == "weather":
            reply = handle_weather(params.get("text", ""))
        elif intent == "light_on":
            reply = handle_light_on(params.get("room", "комната"))
        elif intent == "light_off":
            reply = handle_light_off(params.get("room", "комната"))
        elif intent == "tv_volume_up":
            reply = handle_tv_volume_up()
        elif intent == "tv_volume_down":
            reply = handle_tv_volume_down()
        else:
            # Если интент не распознан - отправляем в LLM
            reply = generate_response(clean_text, user_id)
        
        await update.message.reply_text(reply)
        
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await update.message.reply_text("😅 Ошибка. Попробуйте /clear или подождите.")

# ============================================================
# 12. ЗАПУСК БОТА
# ============================================================

def main():
    # Предзагрузка модели при старте (если вечер)
    preload_model()
    
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("time", time_command))
    application.add_handler(CommandHandler("date", date_command))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("unload", unload_command))
    
    # Обработчик сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("🚀 Бот запущен! Жду сообщения...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
