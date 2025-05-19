# -*- coding: utf-8 -*-

"""
Базовый класс для торговых стратегий
"""

import time
import logging
from datetime import datetime, timedelta

class BaseStrategy:
    """Базовый класс для торговых стратегий"""
    
    def __init__(self, name, symbols, timeframes, market_data, market_analyzer, 
                position_manager, risk_manager, params=None, logger=None):
        """
        Инициализация базовой стратегии
        
        Args:
            name (str): название стратегии
            symbols (list): список торговых пар
            timeframes (list): список временных интервалов
            market_data: объект с рыночными данными
            market_analyzer: объект анализатора рынка
            position_manager: объект управления позициями
            risk_manager: объект управления рисками
            params (dict, optional): параметры стратегии
            logger: объект логгера
        """
        self.name = name
        self.symbols = symbols
        self.timeframes = timeframes
        self.market_data = market_data
        self.market_analyzer = market_analyzer
        self.position_manager = position_manager
        self.risk_manager = risk_manager
        self.params = params or {}
        self.logger = logger or logging.getLogger(__name__)
        
        # Статус стратегии (включена/выключена)
        self.enabled = True
        
        # Статистика торговли
        self.stats = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'profit': 0.0,
            'loss': 0.0,
            'win_rate': 0.0,
            'last_trade_time': None,
            'total_profit': 0.0
        }
        
        # Флаг блокировки лонг-позиций
        self.block_long_entries = False
        
        # Журнал сигналов
        self.signals_log = []
        
        # Последнее время проверки для каждой пары и таймфрейма
        self.last_check_time = {}
        
        # Инициализация настроек стратегии
        self._initialize()
    
    def _initialize(self):
        """Инициализация настроек стратегии"""
        # Инициализация по умолчанию
        # В дочерних классах можно переопределить для специфичной настройки
        
        # Проверяем, что все переданные торговые пары существуют в market_data
        for symbol in self.symbols:
            if symbol not in self.market_data.symbols:
                self.logger.warning(f"Символ {symbol} не найден в данных рынка")
        
        # Проверяем, что все переданные таймфреймы существуют в market_data
        for timeframe in self.timeframes:
            if timeframe not in self.market_data.intervals:
                self.logger.warning(f"Таймфрейм {timeframe} не найден в данных рынка")
        
        # Инициализация времени последней проверки
        for symbol in self.symbols:
            self.last_check_time[symbol] = {}
            for timeframe in self.timeframes:
                self.last_check_time[symbol][timeframe] = datetime.now() - timedelta(days=1)
    
    def execute(self):
        """
        Выполнение стратегии
        
        В этом методе должна быть логика выполнения стратегии.
        Переопределяется в дочерних классах.
        """
        raise NotImplementedError("Метод execute должен быть переопределен в дочернем классе")
    
    def analyze(self, symbol, timeframe):
        """
        Анализ рыночных данных и генерация сигналов
        
        Args:
            symbol (str): торговая пара
            timeframe (str): временной интервал
        
        Returns:
            dict: сигнал для торговли или None
        """
        # В дочерних классах должна быть реализована конкретная логика анализа
        raise NotImplementedError("Метод analyze должен быть переопределен в дочернем классе")
    
    def is_enabled(self):
        """
        Проверка активности стратегии
        
        Returns:
            bool: True если стратегия активна, иначе False
        """
        return self.enabled
    
    def enable(self):
        """Включение стратегии"""
        self.enabled = True
    
    def disable(self):
        """Отключение стратегии"""
        self.enabled = False
    
    def get_stats(self):
        """
        Получение статистики стратегии
        
        Returns:
            dict: статистика торговли
        """
        return self.stats
    
    def update_stats(self, trade_result):
        """
        Обновление статистики стратегии
        
        Args:
            trade_result (dict): результат сделки
        """
        self.stats['total_trades'] += 1
        self.stats['last_trade_time'] = datetime.now()
        
        pnl = trade_result.get('pnl', 0)
        self.stats['total_profit'] += pnl
        
        if pnl > 0:
            self.stats['winning_trades'] += 1
            self.stats['profit'] += pnl
        else:
            self.stats['losing_trades'] += 1
            self.stats['loss'] += abs(pnl)
        
        if self.stats['total_trades'] > 0:
            self.stats['win_rate'] = self.stats['winning_trades'] / self.stats['total_trades'] * 100
    
    def log_signal(self, signal):
        """
        Запись сигнала в журнал
        
        Args:
            signal (dict): торговый сигнал
        """
        signal_data = {
            'time': datetime.now(),
            'symbol': signal.get('symbol'),
            'timeframe': signal.get('timeframe'),
            'side': signal.get('side'),
            'entry_price': signal.get('entry_price'),
            'stop_loss': signal.get('stop_loss'),
            'take_profit': signal.get('take_profit'),
            'reason': signal.get('reason')
        }
        
        self.signals_log.append(signal_data)
        
        # Ограничиваем размер журнала
        max_log_size = 1000
        if len(self.signals_log) > max_log_size:
            self.signals_log = self.signals_log[-max_log_size:]
    
    def should_check_timeframe(self, symbol, timeframe):
        """
        Проверка необходимости анализа таймфрейма
        
        Args:
            symbol (str): торговая пара
            timeframe (str): временной интервал
        
        Returns:
            bool: True если нужно анализировать, иначе False
        """
        # Получаем текущее время
        now = datetime.now()
        
        # Получаем время последней проверки
        last_check = self.last_check_time.get(symbol, {}).get(timeframe, now - timedelta(days=1))
        
        # Определяем минимальный интервал между проверками
        min_interval = timedelta(minutes=1)  # По умолчанию 1 минута
        
        if timeframe == '1m':
            min_interval = timedelta(seconds=30)
        elif timeframe == '5m':
            min_interval = timedelta(minutes=1)
        elif timeframe == '15m':
            min_interval = timedelta(minutes=3)
        elif timeframe == '30m':
            min_interval = timedelta(minutes=5)
        elif timeframe == '1h':
            min_interval = timedelta(minutes=10)
        elif timeframe == '4h':
            min_interval = timedelta(minutes=30)
        elif timeframe == '1d':
            min_interval = timedelta(hours=4)
        
        # Проверяем, прошло ли достаточно времени
        if now - last_check < min_interval:
            return False
        
        # Обновляем время последней проверки
        if symbol not in self.last_check_time:
            self.last_check_time[symbol] = {}
        
        self.last_check_time[symbol][timeframe] = now
        
        return True
    
    def can_open_position(self, symbol, side):
        """
        Проверка возможности открытия позиции
        
        Args:
            symbol (str): торговая пара
            side (str): сторона ('long' или 'short')
        
        Returns:
            bool: True если можно открыть позицию, иначе False
        """
        # Проверка блокировки лонг-позиций
        if side == 'long' and self.block_long_entries:
            self.logger.info(f"Лонг-позиции заблокированы из-за тренда BTC")
            return False
        
        # Здесь можно добавить дополнительные проверки
        # Например, лимиты на количество открытых позиций
        
        return True
    
    def process_signal(self, signal):
        """
        Обработка торгового сигнала
        
        Args:
            signal (dict): торговый сигнал
        
        Returns:
            dict: результат обработки сигнала
        """
        if not signal:
            return None
        
        symbol = signal.get('symbol')
        side = signal.get('side')
        entry_price = signal.get('entry_price')
        stop_loss = signal.get('stop_loss')
        take_profit = signal.get('take_profit')
        size = signal.get('size')
        
        # Логирование сигнала
        self.log_signal(signal)
        
        # Проверка возможности открытия позиции
        if not self.can_open_position(symbol, side):
            return None
        
        # Если размер не указан, рассчитываем его с помощью риск-менеджера
        if not size:
            size = self.risk_manager.calculate_position_size(symbol, entry_price, stop_loss)
        
        # Проверка размера позиции через риск-менеджер
        if not self.risk_manager.check_position_size(symbol, size, entry_price):
            self.logger.warning(f"Размер позиции {size} не прошёл проверку риск-менеджера")
            return None
        
        # Открытие позиции
        position = self.position_manager.open_position(
            symbol=symbol,
            side=side,
            size=size,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            order_type='Limit',  # Можно параметризовать
            strategy_name=self.name
        )
        
        if position:
            self.logger.info(f"Открыта позиция {symbol} {side} по стратегии {self.name}")
            return position
        else:
            self.logger.warning(f"Не удалось открыть позицию {symbol} {side}")
            return None