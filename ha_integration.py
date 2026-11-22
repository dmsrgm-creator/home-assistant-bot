# ha_integration.py - Модуль для работы с Home Assistant

import os
import requests
from dotenv import load_dotenv

# Загружаем переменные
load_dotenv()

HA_URL = os.getenv("HA_URL")
HA_TOKEN = os.getenv("HA_TOKEN")

# ============================================================
# СУЩЕСТВУЮЩИЕ ФУНКЦИИ (время, дата)
# ============================================================

def get_ha_time():
    """Получает текущее время из Home Assistant"""
    url = f"{HA_URL}/api/states/sensor.time"
    headers = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json"
    }
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if "state" in data:
                return data["state"]
            else:
                return "Ошибка: время не найдено"
        else:
            return f"Ошибка: статус {response.status_code}"
    except requests.exceptions.ConnectionError:
        return "Ошибка: не могу подключиться к Home Assistant"
    except requests.exceptions.Timeout:
        return "Ошибка: таймаут соединения"
    except Exception as e:
        return f"Ошибка: {str(e)}"

def get_ha_date():
    """Получает текущую дату из Home Assistant"""
    url = f"{HA_URL}/api/states/sensor.date"
    headers = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json"
    }
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if "state" in data:
                return data["state"]
            else:
                return "Ошибка: дата не найдена"
        else:
            return f"Ошибка: статус {response.status_code}"
    except requests.exceptions.ConnectionError:
        return "Ошибка: не могу подключиться к Home Assistant"
    except requests.exceptions.Timeout:
        return "Ошибка: таймаут соединения"
    except Exception as e:
        return f"Ошибка: {str(e)}"

def get_ha_datetime():
    """Получает текущие дату и время из Home Assistant"""
    time_str = get_ha_time()
    date_str = get_ha_date()
    if "Ошибка" not in time_str and "Ошибка" not in date_str:
        return f"{date_str} {time_str}"
    else:
        return f"Дата: {date_str}, Время: {time_str}"

# ============================================================
# НОВАЯ ФУНКЦИЯ: ВЫЗОВ СКРИПТОВ HA
# ============================================================

def call_ha_script(script_name, data=None):
    """
    Вызывает скрипт в Home Assistant через API.
    Пример: call_ha_script("gromkost", {"command": "set", "value": 50})
    """
    if data is None:
        data = {}
    
    url = f"{HA_URL}/api/services/script/{script_name}"
    headers = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, json=data, headers=headers, timeout=10)
        if response.status_code in [200, 201]:
            return True, "✅ Команда выполнена"
        else:
            return False, f"❌ Ошибка: {response.status_code}"
    except requests.exceptions.ConnectionError:
        return False, "❌ Ошибка: не могу подключиться к Home Assistant"
    except requests.exceptions.Timeout:
        return False, "❌ Ошибка: таймаут соединения"
    except Exception as e:
        return False, f"❌ Ошибка: {str(e)}"

def handle_volume(text):
    """
    Обрабатывает команды громкости и вызывает скрипт gromkost
    """
    import re
    text_lower = text.lower()
    
    # ===== 1. Установка громкости: "громкость 50", "сделай громкость 8" =====
    match = re.search(r'(громкость|громче до|сделай громкость)\s*(\d{1,3})', text_lower)
    if match:
        value = int(match.group(2))
        if 0 <= value <= 100:
            success, msg = call_ha_script("gromkost", {"command": "set", "value": value})
            return msg if success else msg
        else:
            return "❌ Громкость должна быть от 0 до 100"
    
    # ===== 2. Шаг громкости (сколько раз "еще" или "чуть") =====
    step = 1
    if "еще" in text_lower or "чуть" in text_lower:
        step = text_lower.count("еще") + text_lower.count("чуть")
        if step == 0:
            step = 1
    
    # ===== 3. "Громче" =====
    if "громче" in text_lower:
        for _ in range(step):
            success, msg = call_ha_script("gromkost", {"command": "up"})
        return "🔊 Громкость увеличена" if success else msg
    
    # ===== 4. "Тише" =====
    if "тише" in text_lower:
        for _ in range(step):
            success, msg = call_ha_script("gromkost", {"command": "down"})
        return "🔉 Громкость уменьшена" if success else msg
    
    # ===== 5. "Выключить звук" =====
    if any(word in text_lower for word in ["выключи звук", "без звука", "тишина", "заглуши", "mute"]):
        success, msg = call_ha_script("gromkost", {"command": "mute"})
        return "🔇 Звук выключен" if success else msg
    
    return None  # Не распознано



# ============================================================
# ФУНКЦИИ ДЛЯ ТЕМПЕРАТУРЫ / ВЛАЖНОСТИ
# ============================================================

def get_ha_sensor(sensor_name):
    """
    Универсальная функция для получения значения сенсора.
    Пример: get_ha_sensor("sensor.ulitsa_temperature")
    """
    url = f"{HA_URL}/api/states/{sensor_name}"
    headers = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if "state" in data:
                return data["state"]
            else:
                return None
        else:
            return None
    except Exception as e:
        print(f"Ошибка получения сенсора {sensor_name}: {e}")
        return None

# Словарь сенсоров: ключевые слова → sensor_id
SENSORS = {
    # Температура
    "улица": "sensor.ulitsa_temperature",
    "улице": "sensor.ulitsa_temperature",
    "спальня": "sensor.bedroom_temperature",
    "спальне": "sensor.bedroom_temperature",
    "миша": "sensor.komnatamishi_temperature",
    "миши": "sensor.komnatamishi_temperature",
    "мишина": "sensor.komnatamishi_temperature",
    "вика": "sensor.komnataviki_temperature",
    "вики": "sensor.komnataviki_temperature",
    "викина": "sensor.komnataviki_temperature",
    
    # Влажность
    "влажность улица": "sensor.ulitsa_humidity",
    "влажность спальня": "sensor.bedroom_humidity",
    "влажность миша": "sensor.komnatamishi_humidity",
    "влажность вика": "sensor.komnataviki_humidity",
}

def handle_temperature(text):
    """
    Обрабатывает запрос температуры.
    Пример: "сколько градусов на улице" → "На улице +15°C"
    """
    text_lower = text.lower()
    
    # Ищем сенсор по ключевым словам
    sensor_id = None
    room_name = None
    
    for keyword, sensor in SENSORS.items():
        if keyword in text_lower:
            sensor_id = sensor
            room_name = keyword
            break
    
    if sensor_id is None:
        return None  # не распознали
    
    # Получаем значение
    value = get_ha_sensor(sensor_id)
    if value is None:
        return "Не могу получить данные с датчика"
    
    # Форматируем ответ
    if "temperature" in sensor_id:
        return f"На {room_name} {value} градусов"
    elif "humidity" in sensor_id:
        return f"Влажность на {room_name} {value} процентов"
    
    return f"{value}"

# ============================================================
# УПРАВЛЕНИЕ ТЕЛЕВИЗОРОМ
# ============================================================

TV_ENTITY = "remote.televizor_v_spalne"

def turn_on_tv():
    """Включает телевизор в спальне"""
    url = f"{HA_URL}/api/services/remote/turn_on"
    headers = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {"entity_id": TV_ENTITY}
    
    try:
        response = requests.post(url, json=data, headers=headers, timeout=5)
        if response.status_code in [200, 201]:
            return True, "📺 Включаю телевизор"
        else:
            return False, f"❌ Ошибка: {response.status_code}"
    except Exception as e:
        return False, f"❌ Ошибка: {str(e)}"

def turn_off_tv():
    """Выключает телевизор в спальне"""
    url = f"{HA_URL}/api/services/remote/turn_off"
    headers = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {"entity_id": TV_ENTITY}
    
    try:
        response = requests.post(url, json=data, headers=headers, timeout=5)
        if response.status_code in [200, 201]:
            return True, "📺 Выключаю телевизор"
        else:
            return False, f"❌ Ошибка: {response.status_code}"
    except Exception as e:
        return False, f"❌ Ошибка: {str(e)}"
