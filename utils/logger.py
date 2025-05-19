# -*- coding: utf-8 -*-

"""
Модуль для настройки логирования
"""

import os
import logging
from logging.handlers import RotatingFileHandler
import sys

def setup_logger(log_level=logging.INFO, log_file=None):
    """
    Настройка логгера
    
    Args:
        log_level (int): уровень логирования
        log_file (str, optional): путь к файлу логов
    
    Returns:
        logging.Logger: настроенный логгер
    """
    # Создание логгера
    logger = logging.getLogger("bybit_trading_bot")
    logger.setLevel(log_level)
    
    # Очистка существующих обработчиков
    logger.handlers = []
    
    # Формат сообщений
    formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d] - %(message)s')
    
    # Вывод в консоль
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Вывод в файл (если указан)
    if log_file:
        # Создаем папку для логов, если её нет
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # Создание обработчика для файла с ротацией
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    # Вывод информации о настройке логгера
    logger.info("Логгер настроен")
    
    return logger