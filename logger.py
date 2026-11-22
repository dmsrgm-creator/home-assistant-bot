# voice/logger.py - Логирование в файл с ротацией

import logging
from logging.handlers import RotatingFileHandler
import os

LOG_FILE = "/home/dima/PROJECTS/home-assistant-bot/voice/voice.log"
MAX_SIZE = 1 * 1024 * 1024  # 1 МБ
BACKUP_COUNT = 1  # храним 1 старый файл

def setup_logger():
    """Настраивает логирование в файл с ротацией"""
    
    logger = logging.getLogger("voice")
    logger.setLevel(logging.INFO)
    
    # Если уже настроен — не дублируем
    if logger.handlers:
        return logger
    
    # Ротация: когда файл > 1 МБ, старый сохраняется как voice.log.1
    handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=MAX_SIZE,
        backupCount=BACKUP_COUNT,
        encoding="utf-8"
    )
    
    # Формат: время - уровень - сообщение
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    
    logger.addHandler(handler)
    return logger

# Создаём логгер
logger = setup_logger()
