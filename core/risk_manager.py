# -*- coding: utf-8 -*-

"""
Класс для управления рисками
"""

import math
import json
from datetime import datetime, timedelta

class RiskManager:
    """Класс для управления рисками торговли"""
    
    def __init__(self, config, balance=0, logger=None):
        """
        Инициализация менеджера рисков
        
        Args:
            config (dict): конфигурация управления рисками
            balance (float): баланс счета
            logger: объект логгера
        """
        self.config = config
        self.balance = balance
        self.logger = logger
        
        # Загрузка параметров
        self.max_positions = config.get('max_positions', 5)
        self.max_positions_per_symbol = config.get('max_positions_per_symbol', 1)
        self.max_risk_per_trade = config.get('max_risk_per_trade', 1.0) / 100  # процент от баланса
        self.max_risk_total = config.get('max_risk_total', 5.0) / 100  # процент от баланса
        self.min_risk_reward_ratio = config.get('min_risk_reward_ratio', 2.0)
        self.leverage = config.get('leverage', 1)
        
        # Текущий риск
        self.current_risk = 0  # сумма риска всех открытых позиций
        
        # Журнал операций риск-менеджера
        self.risk_log = []
    
    def update_balance(self, new_balance):
        """
        Обновление баланса
        
        Args:
            new_balance (float): новый баланс счета
        """
        self.balance = new_balance
    
    def check_position_size(self, symbol, size, price):
        """
        Проверка размера позиции на соответствие правилам управления рисками
        
        Args:
            symbol (str): торговая пара
            size (float): размер позиции
            price (float): цена входа
        
        Returns:
            bool: True если размер позиции допустим, иначе False
        """
        if self.balance <= 0:
            self.logger.warning("Нулевой или отрицательный баланс. Торговля невозможна.")
            return False
        
        # Расчет стоимости позиции
        position_value = size * price
        
        # Проверка на максимальный риск на одну сделку
        max_position_value = self.balance * self.max_risk_per_trade * self.leverage
        
        if position_value > max_position_value:
            self.logger.warning(f"Размер позиции {position_value} превышает максимально допустимый {max_position_value}")
            return False
        
        # Проверка на общий риск
        if (self.current_risk + position_value / self.leverage) > (self.balance * self.max_risk_total):
            self.logger.warning(f"Общий риск превышает максимально допустимый")
            return False
        
        return True
    
    def calculate_position_size(self, symbol, entry_price, stop_loss_price, risk_percent=None):
        """
        Расчет размера позиции на основе риска
        
        Args:
            symbol (str): торговая пара
            entry_price (float): цена входа
            stop_loss_price (float): цена стоп-лосса
            risk_percent (float, optional): процент риска от баланса
        
        Returns:
            float: размер позиции в базовой валюте
        """
        if risk_percent is None:
            risk_percent = self.max_risk_per_trade
        
        # Проверка параметров
        if entry_price <= 0 or stop_loss_price <= 0:
            self.logger.error("Некорректные цены для расчета размера позиции")
            return 0
        
        # Расчет риска на единицу
        price_diff = abs(entry_price - stop_loss_price)
        if price_diff == 0:
            self.logger.error("Нулевая разница между ценой входа и стоп-лоссом")
            return 0
        
        # Расчет риска в абсолютном выражении
        risk_amount = self.balance * risk_percent
        
        # Расчет размера позиции с учетом кредитного плеча
        position_size = (risk_amount * self.leverage) / price_diff
        
        # Округление до 4 знаков после запятой (или другой точности)
        position_size = math.floor(position_size * 10000) / 10000
        
        return position_size
    
    def calculate_stop_loss(self, symbol, entry_price, side, atr_value=None, atr_multiplier=2.0):
        """
        Расчет уровня стоп-лосса на основе ATR или процента
        
        Args:
            symbol (str): торговая пара
            entry_price (float): цена входа
            side (str): сторона позиции ('long' или 'short')
            atr_value (float, optional): значение ATR
            atr_multiplier (float): множитель ATR
        
        Returns:
            float: цена стоп-лосса
        """
        # Если указан ATR, используем его для расчета
        if atr_value is not None and atr_value > 0:
            stop_distance = atr_value * atr_multiplier
            
            if side == 'long':
                stop_loss = entry_price - stop_distance
            else:
                stop_loss = entry_price + stop_distance
        
        # Иначе используем процент от цены
        else:
            stop_percent = self.config.get('stop_loss_percent', 1.0) / 100
            
            if side == 'long':
                stop_loss = entry_price * (1 - stop_percent)
            else:
                stop_loss = entry_price * (1 + stop_percent)
        
        # Округление до нужного количества знаков
        precision = 2  # Можно уточнить для каждой валютной пары
        stop_loss = round(stop_loss, precision)
        
        return stop_loss
    
    def calculate_take_profit(self, entry_price, stop_loss, side):
        """
        Расчет уровня тейк-профита на основе соотношения риск/прибыль
        
        Args:
            entry_price (float): цена входа
            stop_loss (float): цена стоп-лосса
            side (str): сторона позиции ('long' или 'short')
        
        Returns:
            float: цена тейк-профита
        """
        # Расчет расстояния до стоп-лосса
        stop_distance = abs(entry_price - stop_loss)
        
        # Расчет тейк-профита с учетом соотношения риск/прибыль
        if side == 'long':
            take_profit = entry_price + (stop_distance * self.min_risk_reward_ratio)
        else:
            take_profit = entry_price - (stop_distance * self.min_risk_reward_ratio)
        
        # Округление до нужного количества знаков
        precision = 2  # Можно уточнить для каждой валютной пары
        take_profit = round(take_profit, precision)
        
        return take_profit
    
    def check_risk_reward_ratio(self, entry_price, stop_loss, take_profit, side):
        """
        Проверка соотношения риск/прибыль
        
        Args:
            entry_price (float): цена входа
            stop_loss (float): цена стоп-лосса
            take_profit (float): цена тейк-профита
            side (str): сторона позиции ('long' или 'short')
        
        Returns:
            bool: True если соотношение приемлемо, иначе False
        """
        # Расчет расстояния до стоп-лосса
        stop_distance = abs(entry_price - stop_loss)
        
        # Расчет расстояния до тейк-профита
        take_profit_distance = abs(entry_price - take_profit)
        
        # Расчет соотношения риск/прибыль
        if stop_distance > 0:
            risk_reward_ratio = take_profit_distance / stop_distance
        else:
            return False
        
        # Проверка минимального соотношения
        if risk_reward_ratio < self.min_risk_reward_ratio:
            self.logger.warning(f"Неприемлемое соотношение риск/прибыль: {risk_reward_ratio:.2f} < {self.min_risk_reward_ratio}")
            return False
        
        return True
    
    def add_position_risk(self, symbol, size, entry_price, stop_loss):
        """
        Добавление риска новой позиции в общий учет
        
        Args:
            symbol (str): торговая пара
            size (float): размер позиции
            entry_price (float): цена входа
            stop_loss (float): цена стоп-лосса
        """
        # Расчет риска для позиции
        risk_per_unit = abs(entry_price - stop_loss)
        position_risk = size * risk_per_unit / self.leverage
        
        # Добавление к общему риску
        self.current_risk += position_risk
        
        # Логирование
        self.risk_log.append({
            'time': datetime.now(),
            'action': 'add_risk',
            'symbol': symbol,
            'size': size,
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'position_risk': position_risk,
            'current_risk': self.current_risk,
            'risk_percent': (self.current_risk / self.balance) * 100 if self.balance > 0 else 0
        })
    
    def remove_position_risk(self, symbol, size, entry_price, stop_loss):
        """
        Удаление риска закрытой позиции из общего учета
        
        Args:
            symbol (str): торговая пара
            size (float): размер позиции
            entry_price (float): цена входа
            stop_loss (float): цена стоп-лосса
        """
        # Расчет риска для позиции
        risk_per_unit = abs(entry_price - stop_loss)
        position_risk = size * risk_per_unit / self.leverage
        
        # Вычитание из общего риска
        self.current_risk = max(0, self.current_risk - position_risk)
        
        # Логирование
        self.risk_log.append({
            'time': datetime.now(),
            'action': 'remove_risk',
            'symbol': symbol,
            'size': size,
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'position_risk': position_risk,
            'current_risk': self.current_risk,
            'risk_percent': (self.current_risk / self.balance) * 100 if self.balance > 0 else 0
        })
    
    def get_risk_stats(self):
        """
        Получение статистики по текущим рискам
        
        Returns:
            dict: статистика рисков
        """
        risk_percent = (self.current_risk / self.balance) * 100 if self.balance > 0 else 0
        
        return {
            'balance': self.balance,
            'current_risk': self.current_risk,
            'risk_percent': risk_percent,
            'max_risk_per_trade': self.max_risk_per_trade * 100,
            'max_risk_total': self.max_risk_total * 100,
            'max_position_value': self.balance * self.max_risk_per_trade * self.leverage if self.balance > 0 else 0,
            'leverage': self.leverage
        }
    
    def check_btc_trend(self, btc_trend):
        """
        Проверка тренда BTC для принятия решения о входе в позицию
        
        Args:
            btc_trend (str): тренд BTC ('bullish', 'bearish', 'neutral')
        
        Returns:
            bool: True если вход в лонг разрешен, иначе False
        """
        # Если тренд BTC медвежий, запрещаем входить в лонг для всех токенов
        if btc_trend == 'bearish':
            self.logger.info("BTC в нисходящем тренде, вход в лонг запрещен")
            return False
        
        return True