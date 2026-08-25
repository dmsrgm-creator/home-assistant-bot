# ha_integration.py - Модуль для работы с Home Assistant

import os
import requests
from dotenv import load_dotenv

# Загружаем переменные
load_dotenv()

HA_URL = os.getenv("HA_URL")
HA_TOKEN = os.getenv("HA_TOKEN")

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
