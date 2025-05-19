#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Главный файл запуска торгового бота Bybit
"""

import os
import time
import logging
from datetime import datetime
import argparse

from core.bot import TradingBot
from config.settings import load_config
from utils.logger import setup_logger

def parse_arguments():
    """Парсинг аргументов командной строки"""
    parser = argparse.ArgumentParser(description='Bybit Trading Bot')
    parser.add_argument('--config', type=str, default='config/config.yaml',
                       help='Путь к файлу конфигурации')
    parser.add_argument('--debug', action='store_true',
                       help='Включить режим отладки')
    parser.add_argument('--paper', action='store_true',
                       help='Бумажная торговля (без реальных сделок)')
    parser.add_argument('--backtest', action='store_true',
                       help='Режим бэктестинга')
    return parser.parse_args()

def main():
    """Основная функция запуска бота"""
    # Парсинг аргументов
    args = parse_arguments()
    
    # Создание папки для логов, если её нет
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    # Настройка логирования
    current_time = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    log_file = f'logs/bot_{current_time}.log'
    log_level = logging.DEBUG if args.debug else logging.INFO
    logger = setup_logger(log_level, log_file)
    
    logger.info('Запуск торгового бота Bybit')
    logger.info(f'Используется конфигурация: {args.config}')
    
    try:
        # Загрузка конфигурации
        config = load_config(args.config)
        
        # Создание экземпляра бота
        bot = TradingBot(
            config=config,
            paper_trading=args.paper,
            backtest_mode=args.backtest,
            logger=logger
        )
        
        # Запуск бота
        bot.start()
        
        # Основной цикл для поддержания работы программы
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info('Получен сигнал остановки. Завершение работы бота...')
        if 'bot' in locals():
            bot.stop()
    except Exception as e:
        logger.error(f'Критическая ошибка: {str(e)}', exc_info=True)
    finally:
        logger.info('Бот остановлен')

if __name__ == "__main__":
    main()