# -*- coding: utf-8 -*-

"""
Менеджер стратегий торговли
"""

import time
import importlib
import logging
from datetime import datetime

class StrategyManager:
    """Класс для управления торговыми стратегиями"""
    
    def __init__(self, config, market_data, market_analyzer, position_manager, risk_manager, logger=None):
        """
        Инициализация менеджера стратегий
        
        Args:
            config (dict): конфигурация стратегий
            market_data: объект с рыночными данными
            market_analyzer: объект анализатора рынка
            position_manager: объект управления позициями
            risk_manager: объект управления рисками
            logger: объект логгера
        """
        self.config = config
        self.market_data = market_data
        self.market_analyzer = market_analyzer
        self.position_manager = position_manager
        self.risk_manager = risk_manager
        self.logger = logger or logging.getLogger(__name__)
        
        # Словарь активных стратегий
        # {strategy_name: strategy_instance}
        self.strategies = {}
        
        # Флаг блокировки лонг-позиций (используется при медвежьем тренде BTC)
        self.block_long_entries = False
        
        # Инициализация стратегий
        self._initialize_strategies()
    
    def _initialize_strategies(self):
        """Инициализация стратегий из конфигурации"""
        try:
            # Получаем список стратегий из конфигурации
            strategies_list = self.config.get('strategies', [])
            
            if not strategies_list:
                self.logger.warning("Список стратегий пуст. Проверьте конфигурацию.")
                return
            
            # Инициализация каждой стратегии
            for strategy_config in strategies_list:
                strategy_name = strategy_config.get('name')
                strategy_class = strategy_config.get('class')
                strategy_params = strategy_config.get('params', {})
                strategy_symbols = strategy_config.get('symbols', [])
                strategy_timeframes = strategy_config.get('timeframes', [])
                strategy_enabled = strategy_config.get('enabled', True)
                
                if not strategy_name or not strategy_class:
                    self.logger.warning(f"Пропуск стратегии с неполной конфигурацией: {strategy_config}")
                    continue
                
                if not strategy_enabled:
                    self.logger.info(f"Стратегия {strategy_name} отключена в конфигурации")
                    continue
                
                try:
                    # Если указан полный путь к классу
                    if '.' in strategy_class:
                        module_name, class_name = strategy_class.rsplit('.', 1)
                        module = importlib.import_module(module_name)
                        strategy_class_obj = getattr(module, class_name)
                    else:
                        # Поиск в стандартных местах
                        try:
                            module = importlib.import_module(f"strategies.{strategy_class.lower()}")
                            strategy_class_obj = getattr(module, strategy_class)
                        except (ImportError, AttributeError):
                            self.logger.error(f"Не удалось найти класс стратегии: {strategy_class}")
                            continue
                    
                    # Создание экземпляра стратегии
                    strategy = strategy_class_obj(
                        name=strategy_name,
                        symbols=strategy_symbols,
                        timeframes=strategy_timeframes,
                        market_data=self.market_data,
                        market_analyzer=self.market_analyzer,
                        position_manager=self.position_manager,
                        risk_manager=self.risk_manager,
                        params=strategy_params,
                        logger=self.logger
                    )
                    
                    # Добавление в словарь стратегий
                    self.strategies[strategy_name] = strategy
                    self.logger.info(f"Стратегия {strategy_name} инициализирована успешно")
                
                except Exception as e:
                    self.logger.error(f"Ошибка при инициализации стратегии {strategy_name}: {str(e)}")
            
            self.logger.info(f"Инициализировано {len(self.strategies)} стратегий")
        
        except Exception as e:
            self.logger.error(f"Ошибка при инициализации стратегий: {str(e)}")
    
    def execute(self):
        """Выполнение всех активных стратегий"""
        try:
            if not self.strategies:
                self.logger.warning("Нет активных стратегий для выполнения")
                return
            
            self.logger.info("Выполнение торговых стратегий...")
            
            # Выполнение каждой стратегии
            for strategy_name, strategy in self.strategies.items():
                try:
                    # Проверка, включена ли стратегия
                    if not strategy.is_enabled():
                        continue
                    
                    # Выполнение стратегии
                    self.logger.debug(f"Выполнение стратегии {strategy_name}")
                    
                    # Если лонг-позиции заблокированы из-за тренда BTC,
                    # передаем этот флаг в стратегию
                    strategy.block_long_entries = self.block_long_entries
                    
                    # Выполнение стратегии
                    strategy.execute()
                
                except Exception as e:
                    self.logger.error(f"Ошибка при выполнении стратегии {strategy_name}: {str(e)}")
        
        except Exception as e:
            self.logger.error(f"Ошибка при выполнении стратегий: {str(e)}")
    
    def get_strategy(self, strategy_name):
        """
        Получение стратегии по имени
        
        Args:
            strategy_name (str): название стратегии
        
        Returns:
            BaseStrategy: экземпляр стратегии или None, если стратегия не найдена
        """
        return self.strategies.get(strategy_name)
    
    def enable_strategy(self, strategy_name):
        """
        Включение стратегии
        
        Args:
            strategy_name (str): название стратегии
        
        Returns:
            bool: True если стратегия успешно включена, иначе False
        """
        strategy = self.get_strategy(strategy_name)
        if strategy:
            strategy.enable()
            self.logger.info(f"Стратегия {strategy_name} включена")
            return True
        return False
    
    def disable_strategy(self, strategy_name):
        """
        Отключение стратегии
        
        Args:
            strategy_name (str): название стратегии
        
        Returns:
            bool: True если стратегия успешно отключена, иначе False
        """
        strategy = self.get_strategy(strategy_name)
        if strategy:
            strategy.disable()
            self.logger.info(f"Стратегия {strategy_name} отключена")
            return True
        return False
    
    def get_strategies_status(self):
        """
        Получение статуса всех стратегий
        
        Returns:
            dict: {strategy_name: {enabled: bool, stats: dict}}
        """
        status = {}
        for name, strategy in self.strategies.items():
            status[name] = {
                'enabled': strategy.is_enabled(),
                'stats': strategy.get_stats()
            }
        return status