# -*- coding: utf-8 -*-

"""
Модуль для загрузки конфигурации
"""

import os
import yaml
import logging

def load_config(config_path):
    """
    Загрузка конфигурации из YAML файла
    
    Args:
        config_path (str): путь к файлу конфигурации
    
    Returns:
        dict: конфигурация бота
    """
    logger = logging.getLogger("bybit_trading_bot")
    
    try:
        # Проверка существования файла
        if not os.path.exists(config_path):
            logger.error(f"Файл конфигурации не найден: {config_path}")
            raise FileNotFoundError(f"Файл конфигурации не найден: {config_path}")
        
        # Загрузка YAML
        with open(config_path, 'r', encoding='utf-8') as config_file:
            config = yaml.safe_load(config_file)
        
        # Проверка основных разделов конфигурации
        required_sections = ['api', 'trading', 'risk_management']
        for section in required_sections:
            if section not in config:
                logger.error(f"В конфигурации отсутствует обязательный раздел: {section}")
                raise ValueError(f"В конфигурации отсутствует обязательный раздел: {section}")
        
        # Проверка ключевых параметров API
        if 'api_key' not in config['api'] or 'api_secret' not in config['api']:
            logger.warning("В конфигурации отсутствуют API ключи")
        
        # Проверка списка символов и интервалов
        if 'symbols' not in config['trading'] or not config['trading']['symbols']:
            logger.error("В конфигурации не указаны торговые пары")
            raise ValueError("В конфигурации не указаны торговые пары")
        
        if 'intervals' not in config['trading'] or not config['trading']['intervals']:
            logger.error("В конфигурации не указаны временные интервалы")
            raise ValueError("В конфигурации не указаны временные интервалы")
        
        # Проверка параметров риск-менеджмента
        if 'max_risk_per_trade' not in config['risk_management']:
            logger.warning("Не указан максимальный риск на сделку, используется значение по умолчанию")
            config['risk_management']['max_risk_per_trade'] = 1.0
        
        # Проверка наличия стратегий
        if 'strategies' not in config or 'strategies' not in config['strategies'] or not config['strategies']['strategies']:
            logger.warning("В конфигурации не указаны стратегии")
        
        logger.info(f"Конфигурация успешно загружена из {config_path}")
        return config
    
    except (yaml.YAMLError, KeyError, ValueError, FileNotFoundError) as e:
        logger.error(f"Ошибка при загрузке конфигурации: {str(e)}")
        raise