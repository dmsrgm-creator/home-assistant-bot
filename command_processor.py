# command_processor.py - Общая логика обработки команд
# Используется и в Telegram, и в локальном голосовом ассистенте

import logging
from ha_integration import (
    get_ha_time,
    get_ha_date,
    handle_volume,
    turn_on_tv,
    turn_off_tv,
    handle_temperature
)

logger = logging.getLogger(__name__)

# ============================================================
# 1. ДЕТЕКТ ИНТЕНТОВ
# ============================================================

def detect_intent(text):
    """Определяет намерение пользователя"""
    text_lower = text.lower()
    
    # ===== ТЕЛЕВИЗОР =====
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
    
    # ===== СВЕТ =====
    if "свет" in text_lower:
        if any(word in text_lower for word in ["включи", "вкл", "зажги"]):
            return "light_on", {"room": extract_room(text)}
        elif any(word in text_lower for word in ["выключи", "выкл", "погаси"]):
            return "light_off", {"room": extract_room(text)}
    
    # ===== ПОГОДА =====
    weather_keywords = ["погод", "дождь", "солнце", "облачно", "ветер", "тучи"]
    if any(word in text_lower for word in weather_keywords):
        return "weather", {"text": text}
    
    return "unknown", {}

def extract_room(text):
    """Извлекает название комнаты"""
    rooms = ["гостиная", "кухня", "спальня", "ванная", "коридор", "комната"]
    for room in rooms:
        if room in text.lower():
            return room
    return "комната"

# ============================================================
# 2. ОБРАБОТЧИКИ НАВЫКОВ
# ============================================================

def handle_light_on(room):
    return f"💡 Включаю свет в {room}"

def handle_light_off(room):
    return f"💡 Выключаю свет в {room}"

def handle_weather(text):
    return "☀️ На улице солнечно, +25°C"

# ============================================================
# 3. ГЛАВНАЯ ФУНКЦИЯ ОБРАБОТКИ КОМАНДЫ
# ============================================================

def process_command(text, source="telegram"):
    """
    Обрабатывает команду пользователя.
    
    Args:
        text: текст команды
        source: "telegram" или "local"
    
    Returns:
        {
            "reply": str,       # текст ответа
            "speak": bool,      # нужно ли озвучивать (для локального режима)
            "success": bool,    # удалось ли выполнить
            "intent": str       # определённый интент
        }
    """
    intent, params = detect_intent(text)
    logger.info(f"🎯 Интент: {intent} (источник: {source})")
    
    # ============================================================
    # ВРЕМЯ
    # ============================================================
    if intent == "time":
        reply = get_ha_time()
        return {"reply": f"🕐 {reply}", "speak": True, "success": True, "intent": intent}
    
    # ============================================================
    # ДАТА
    # ============================================================
    if intent == "date":
        reply = get_ha_date()
        return {"reply": f"📅 {reply}", "speak": True, "success": True, "intent": intent}
    
    # ============================================================
    # ДАТЧИКИ (температура/влажность)
    # ============================================================
    if intent == "sensor":
        reply = handle_temperature(params.get("text", ""))
        if reply is None:
            return {"reply": "Не понял, какой датчик?", "speak": True, "success": False, "intent": intent}
        return {"reply": reply, "speak": True, "success": True, "intent": intent}
    
    # ============================================================
    # ТЕЛЕВИЗОР
    # ============================================================
    if intent == "tv_on":
        success, reply = turn_on_tv()
        return {"reply": reply, "speak": False, "success": success, "intent": intent}
    
    if intent == "tv_off":
        success, reply = turn_off_tv()
        return {"reply": reply, "speak": False, "success": success, "intent": intent}
    
    # ============================================================
    # ГРОМКОСТЬ
    # ============================================================
    if intent == "volume":
        reply = handle_volume(params.get("text", ""))
        if reply is None:
            return {"reply": "Не понял команду громкости", "speak": False, "success": False, "intent": intent}
        success = not reply.startswith("❌")
        return {"reply": reply, "speak": False, "success": success, "intent": intent}
    
    # ============================================================
    # СВЕТ (заготовка)
    # ============================================================
    if intent == "light_on":
        reply = handle_light_on(params.get("room", "комната"))
        return {"reply": reply, "speak": False, "success": True, "intent": intent}
    
    if intent == "light_off":
        reply = handle_light_off(params.get("room", "комната"))
        return {"reply": reply, "speak": False, "success": True, "intent": intent}
    
    # ============================================================
    # ПОГОДА (заготовка)
    # ============================================================
    if intent == "weather":
        reply = handle_weather(params.get("text", ""))
        return {"reply": reply, "speak": True, "success": True, "intent": intent}
    
    # ============================================================
    # НЕИЗВЕСТНО
    # ============================================================
    if source == "local":
        # Локально — не используем LLM, просто говорим "не понял"
        return {"reply": None, "speak": True, "success": False, "intent": "unknown"}
    else:
        # В Telegram — можно использовать LLM
        return {"reply": None, "speak": False, "success": False, "intent": "unknown"}
