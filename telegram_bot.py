# telegram_bot.py - НОВАЯ ВЕРСИЯ С ИНТЕГРАЦИЕЙ HA

import logging
import os
import time
import threading
import gc
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
# 2. НАСТРОЙКИ МОДЕЛИ
# ============================================================

MODEL_PATH = "/home/dima/models/qwen2.5-3b-instruct-q4_k_m.gguf"
BOT_NAME = "Вася"
UNLOAD_TIMEOUT = 60 * 15  # 15 минут бездействия

MODEL_CONFIG = {
    "n_ctx": 2048,
    "n_threads": 2,
    "n_gpu_layers": 0,
    "verbose": False
}

GENERATION_CONFIG = {
    "max_tokens": 256,
    "temperature": 0.5,
    "top_p": 0.85,
    "repeat_penalty": 1.1
}

# ============================================================
# 3. ЛОГИРОВАНИЕ
# ============================================================

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================================================
# 4. ЛЕНИВАЯ ЗАГРУЗКА МОДЕЛИ С АВТОВЫГРУЗКОЙ
# ============================================================

llm = None
last_used = time.time()

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
    """Фоновый поток: проверяет бездействие и выгружает модель"""
    global llm
    while True:
        time.sleep(60)
        if llm is not None and (time.time() - last_used > UNLOAD_TIMEOUT):
            logger.info("⏳ Выгружаем модель (бездействие 15 мин)")
            llm = None
            gc.collect()

thread = threading.Thread(target=unload_worker, daemon=True)
thread.start()
logger.info("🧠 Фоновый поток выгрузки запущен")

# ============================================================
# 5. ИСТОРИЯ ДИАЛОГОВ
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
# 6. АКТИВАЦИЯ ПО ИМЕНИ
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
# 7. ГЕНЕРАЦИЯ ОТВЕТА
# ============================================================

def generate_response(user_message, user_id):
    history = get_user_history(user_id)
    history.append({"role": "user", "content": user_message})
    history = trim_history(history)
    
    model = get_llm()
    
    response = model.create_chat_completion(
        messages=history,
        **GENERATION_CONFIG
    )
    
    reply = response["choices"][0]["message"]["content"]
    history.append({"role": "assistant", "content": reply})
    return reply

# ============================================================
# 8. ОБРАБОТЧИКИ КОМАНД
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"👋 Привет! Я {BOT_NAME}, твой домашний ассистент.\n"
        f"В группе обращайся: '{BOT_NAME}, включи свет'\n"
        f"В личке можно просто писать.\n\n"
        f"Команды:\n"
        f"/time — текущее время\n"
        f"/date — текущая дата\n"
        f"/datetime — дата и время\n"
        f"/clear — очистить историю\n"
        f"/stats — статистика\n"
        f"/unload — выгрузить модель из памяти"
    )

async def time_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает текущее время из Home Assistant"""
    time_str = get_ha_time()
    await update.message.reply_text(f"🕐 Текущее время: {time_str}")

async def date_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает текущую дату из Home Assistant"""
    date_str = get_ha_date()
    await update.message.reply_text(f"📅 Текущая дата: {date_str}")

async def datetime_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает текущие дату и время из Home Assistant"""
    datetime_str = get_ha_datetime()
    await update.message.reply_text(f"📅🕐 Текущие дата и время: {datetime_str}")

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
        f"📊 Сообщений в диалоге: {msg_count}\n"
        f"Контекст: {MODEL_CONFIG['n_ctx']} токенов\n"
        f"Ядер CPU: {MODEL_CONFIG['n_threads']}\n"
        f"Модель в памяти: {model_loaded}"
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
        reply = generate_response(clean_text, user_id)
        await update.message.reply_text(reply)
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await update.message.reply_text("😅 Ошибка. Попробуйте /clear или подождите.")

# ============================================================
# 9. ЗАПУСК БОТА
# ============================================================

def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("time", time_command))
    application.add_handler(CommandHandler("date", date_command))
    application.add_handler(CommandHandler("datetime", datetime_command))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("unload", unload_command))
    
    # Обработчик сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("🚀 Бот запущен! Жду сообщения...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
