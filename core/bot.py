# -*- coding: utf-8 -*-

"""
Основной класс торгового бота
"""

import time
import logging
from datetime import datetime
import threading

from pybit.unified_trading import HTTP
from pybit.unified_trading import WebSocket

from core.market_data import MarketData
from core.position_manager import PositionManager
from core.risk_manager import RiskManager
from strategies.strategy_manager import StrategyManager
from utils.market_analyzer import MarketAnalyzer

class TradingBot:
    """Класс торгового бота для Bybit"""
    
    def __init__(self, config, paper_trading=False, backtest_mode=False, logger=None):
        """
        Инициализация торгового бота
        
        Args:
            config (dict): конфигурация бота
            paper_trading (bool): режим бумажной торговли
            backtest_mode (bool): режим бэктестинга
            logger (logging.Logger): объект логгера
        """
        self.config = config
        self.paper_trading = paper_trading
        self.backtest_mode = backtest_mode
        self.logger = logger or logging.getLogger(__name__)
        
        # Статус работы бота
        self.is_running = False
        self.market_data_thread = None
        self.strategy_thread = None
        
        # Настройка API-клиента Bybit
        self._setup_api_client()
        
        # Инициализация компонентов
        self.market_data = MarketData(
            api_client=self.api_client, 
            ws_client=self.ws_client,
            symbols=self.config['trading']['symbols'],
            intervals=self.config['trading']['intervals'],
            logger=self.logger
        )
        
        self.market_analyzer = MarketAnalyzer(
            config=self.config,
            logger=self.logger
        )
        
        self.risk_manager = RiskManager(
            config=self.config['risk_management'],
            balance=self._get_account_balance(),
            logger=self.logger
        )
        
        self.position_manager = PositionManager(
            api_client=self.api_client,
            config=self.config,
            risk_manager=self.risk_manager,
            paper_trading=self.paper_trading,
            logger=self.logger
        )
        
        self.strategy_manager = StrategyManager(
            config=self.config['strategies'],
            market_data=self.market_data,
            market_analyzer=self.market_analyzer,
            position_manager=self.position_manager,
            risk_manager=self.risk_manager,
            logger=self.logger
        )
        
    def _setup_api_client(self):
        """Настройка API-клиента Bybit"""
        api_config = self.config['api']
        
        try:
            # HTTP API клиент
            self.api_client = HTTP(
                testnet=api_config.get('testnet', False),
                api_key=api_config.get('api_key', ''),
                api_secret=api_config.get('api_secret', '')
            )
            
            # WebSocket API клиент
            self.ws_client = WebSocket(
                testnet=api_config.get('testnet', False),
                api_key=api_config.get('api_key', ''),
                api_secret=api_config.get('api_secret', ''),
                channel_type="private"
            )
            
            self.logger.info('API клиент Bybit успешно инициализирован')
            
            # Проверка подключения
            server_time = self.api_client.get_server_time()
            self.logger.info(f'Соединение с Bybit установлено. Время сервера: {server_time}')
            
        except Exception as e:
            self.logger.error(f'Ошибка инициализации API клиента: {str(e)}')
            raise
    
    def _get_account_balance(self):
        """Получение баланса аккаунта"""
        try:
            if self.paper_trading:
                # В режиме бумажной торговли используем значение из конфигурации
                balance = self.config['paper_trading']['initial_balance']
                self.logger.info(f'Бумажная торговля: начальный баланс: {balance} USDT')
                return balance
            else:
                # Получение реального баланса
                account_info = self.api_client.get_wallet_balance(
                    accountType="UNIFIED",
                    coin="USDT"
                )
                balance = float(account_info['result']['list'][0]['coin'][0]['walletBalance'])
                self.logger.info(f'Баланс аккаунта: {balance} USDT')
                return balance
        except Exception as e:
            self.logger.error(f'Ошибка при получении баланса: {str(e)}')
            return 0.0
    
    def start(self):
        """Запуск бота"""
        if self.is_running:
            self.logger.warning('Бот уже запущен')
            return
        
        self.is_running = True
        self.logger.info('Запуск бота...')
        
        # Запуск сбора рыночных данных
        self.market_data_thread = threading.Thread(
            target=self._run_market_data_loop,
            daemon=True
        )
        self.market_data_thread.start()
        
        # Даем немного времени для сбора начальных данных
        time.sleep(5)
        
        # Запуск стратегии
        self.strategy_thread = threading.Thread(
            target=self._run_strategy_loop,
            daemon=True
        )
        self.strategy_thread.start()
        
        self.logger.info('Бот успешно запущен')
    
    def stop(self):
        """Остановка бота"""
        if not self.is_running:
            return
        
        self.logger.info('Остановка бота...')
        self.is_running = False
        
        # Ожидание завершения потоков
        if self.market_data_thread and self.market_data_thread.is_alive():
            self.market_data_thread.join(timeout=5)
        
        if self.strategy_thread and self.strategy_thread.is_alive():
            self.strategy_thread.join(timeout=5)
        
        self.logger.info('Закрытие соединений...')
        try:
            self.ws_client.stop_websocket()
        except Exception as e:
            self.logger.error(f'Ошибка при закрытии WebSocket: {str(e)}')
        
        self.logger.info('Бот остановлен')
    
    def _run_market_data_loop(self):
        """Основной цикл сбора рыночных данных"""
        self.logger.info("Запуск цикла сбора рыночных данных")
        
        # Инициализация получения данных
        self.market_data.start()
        
        while self.is_running:
            try:
                # В режиме бэктестинга иная логика работы с данными
                if self.backtest_mode:
                    self.logger.info("Загрузка исторических данных для бэктестинга")
                    self.market_data.load_historical_data()
                    break  # Выход из цикла после загрузки исторических данных
                
                # Обновление рыночных данных происходит в маркет дата через WebSocket
                time.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Ошибка в цикле сбора данных: {str(e)}", exc_info=True)
                time.sleep(5)  # Пауза перед повторной попыткой
        
        self.logger.info("Цикл сбора рыночных данных остановлен")
    
    def _run_strategy_loop(self):
        """Основной цикл работы стратегии"""
        self.logger.info("Запуск цикла работы торговой стратегии")
        
        while self.is_running:
            try:
                # Проверка глобального рыночного тренда (особенно для BTC)
                btc_trend = self.market_analyzer.analyze_btc_trend()
                
                # Реализация вашего требования: если BTC падает, не входить в лонг
                if btc_trend == "bearish":
                    self.logger.info("BTC в нисходящем тренде - лонг-позиции заблокированы")
                    self.strategy_manager.block_long_entries = True
                else:
                    self.strategy_manager.block_long_entries = False
                
                # Обновление аналитики рынка
                self.market_analyzer.update(self.market_data)
                
                # Выполнение стратегии
                self.strategy_manager.execute()
                
                # Управление рисками и обновление существующих позиций
                self.position_manager.manage_positions()
                
                # Обновление статистики
                self._update_stats()
                
                # Пауза между итерациями
                sleep_time = self.config['bot'].get('strategy_interval', 60)
                time.sleep(sleep_time)
                
            except Exception as e:
                self.logger.error(f"Ошибка в цикле работы стратегии: {str(e)}", exc_info=True)
                time.sleep(10)  # Пауза перед повторной попыткой
        
        self.logger.info("Цикл работы торговой стратегии остановлен")
    
    def _update_stats(self):
        """Обновление статистики работы бота"""
        if not hasattr(self, 'last_stats_time') or \
           (datetime.now() - self.last_stats_time).total_seconds() > 3600:
            
            # Обновляем статистику раз в час
            self.last_stats_time = datetime.now()
            
            # Получение текущего баланса и активных позиций
            try:
                current_balance = self._get_account_balance()
                active_positions = self.position_manager.get_active_positions()
                
                # Расчет P&L
                initial_balance = self.config['paper_trading']['initial_balance'] if self.paper_trading else 0
                pnl = current_balance - initial_balance if initial_balance > 0 else "Н/Д"
                
                self.logger.info(f"===== СТАТИСТИКА БОТА =====")
                self.logger.info(f"Текущий баланс: {current_balance} USDT")
                self.logger.info(f"Общий P&L: {pnl} USDT")
                self.logger.info(f"Активных позиций: {len(active_positions)}")
                self.logger.info(f"==========================")
                
            except Exception as e:
                self.logger.error(f"Ошибка при обновлении статистики: {str(e)}")