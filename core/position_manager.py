# -*- coding: utf-8 -*-

"""
Класс для управления позициями
"""

import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union
from decimal import Decimal

class PositionManager:
    """Класс для управления торговыми позициями"""
    
    def __init__(self, api_client, config, risk_manager, paper_trading=False, logger=None):
        """
        Инициализация менеджера позиций
        
        Args:
            api_client: HTTP-клиент API Bybit
            config (dict): конфигурация бота
            risk_manager: объект управления рисками
            paper_trading (bool): режим бумажной торговли
            logger: объект логгера
        """
        self.api_client = api_client
        self.config = config
        self.risk_manager = risk_manager
        self.paper_trading = paper_trading
        self.logger = logger or logging.getLogger(__name__)
        
        # Кэш позиций
        self.positions = {}
        self.last_update_time = 0
        
        # Журнал операций
        self.operations_log = []
        
        # Время обновления кэша (в секундах)
        self.cache_update_interval = 5
        
        # В режиме бумажной торговли храним позиции в памяти
        if self.paper_trading:
            self.paper_positions = {}
            self.paper_orders = {}
            self.paper_balance = config['paper_trading']['initial_balance']
    
    def get_active_positions(self):
        """
        Получение всех активных позиций
        
        Returns:
            dict: активные позиции
        """
        self._update_positions()
        return self.positions
    
    def _update_positions(self, force=False):
        """
        Обновление информации о позициях
        
        Args:
            force (bool): принудительное обновление
        """
        current_time = time.time()
        
        # Проверяем, нужно ли обновлять кэш
        if force or (current_time - self.last_update_time >= self.cache_update_interval):
            try:
                if not self.paper_trading:
                    # Получаем реальные позиции через API
                    positions_response = self.api_client.get_positions(
                        category="linear",
                        settleCoin="USDT"
                    )
                    
                    if positions_response['retCode'] == 0:
                        positions_list = positions_response['result']['list']
                        self.positions = {}
                        
                        for pos in positions_list:
                            # Фильтруем только позиции с ненулевым размером
                            if float(pos['size']) > 0:
                                symbol = pos['symbol']
                                side = 'long' if pos['side'] == 'Buy' else 'short'
                                position_key = f"{symbol}_{side}"
                                
                                self.positions[position_key] = {
                                    'symbol': symbol,
                                    'side': side,
                                    'size': float(pos['size']),
                                    'entry_price': float(pos['entryPrice']),
                                    'leverage': float(pos['leverage']),
                                    'margin_type': pos['marginType'],
                                    'unrealized_pnl': float(pos['unrealisedPnl']),
                                    'realized_pnl': float(pos['realisedPnl']),
                                    'position_value': float(pos['positionValue']),
                                    'created_time': datetime.fromtimestamp(int(pos['createdTime']) / 1000),
                                    'updated_time': datetime.fromtimestamp(int(pos['updatedTime']) / 1000)
                                }
                    else:
                        self.logger.error(f"Ошибка при получении позиций: {positions_response['retMsg']}")
                
                else:
                    # В режиме бумажной торговли используем локальные данные
                    self.positions = self.paper_positions
                
                self.last_update_time = current_time
                
            except Exception as e:
                self.logger.error(f"Ошибка при обновлении информации о позициях: {str(e)}")
    
    def open_position(self, symbol, side, size=None, entry_price=None, stop_loss=None, take_profit=None, 
                      order_type='Market', strategy_name=None):
        """
        Открытие новой позиции
        
        Args:
            symbol (str): торговая пара
            side (str): сторона ('long' или 'short')
            size (float, optional): размер позиции
            entry_price (float, optional): цена входа (для лимитных ордеров)
            stop_loss (float, optional): уровень стоп-лосса
            take_profit (float, optional): уровень тейк-профита
            order_type (str): тип ордера ('Market', 'Limit')
            strategy_name (str, optional): название стратегии
            
        Returns:
            dict: результат открытия позиции
        """
        try:
            # Нормализация стороны для API Bybit
            api_side = "Buy" if side.lower() == "long" else "Sell"
            
            # Получение текущей цены, если не указана
            if entry_price is None:
                ticker = self._get_ticker(symbol)
                if ticker:
                    entry_price = float(ticker['last_price'])
                else:
                    self.logger.error(f"Не удалось получить цену для {symbol}")
                    return None
            
            # Установка плеча, если необходимо
            leverage = self.config['risk_management']['leverage']
            self._set_leverage(symbol, leverage)
            
            # Расчет размера позиции, если не указан
            if size is None:
                if stop_loss is None:
                    self.logger.error("Для расчета размера позиции необходимо указать стоп-лосс")
                    return None
                    
                size = self.risk_manager.calculate_position_size(
                    symbol=symbol,
                    entry_price=entry_price,
                    stop_loss_price=stop_loss
                )
            
            # Журналирование операции
            self.logger.info(f"Открытие позиции: {symbol} {side} размер={size} цена={entry_price}")
            
            # Режим бумажной торговли
            if self.paper_trading:
                return self._open_paper_position(
                    symbol=symbol,
                    side=side,
                    size=size,
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    strategy_name=strategy_name
                )
            
            # Размещение реального ордера
            order_result = self._place_order(
                symbol=symbol,
                side=api_side,
                order_type=order_type,
                qty=size,
                price=entry_price if order_type == 'Limit' else None
            )
            
            if order_result and order_result['retCode'] == 0:
                order_id = order_result['result']['orderId']
                self.logger.info(f"Ордер размещен успешно: {order_id}")
                
                # Установка стоп-лосса и тейк-профита
                if stop_loss or take_profit:
                    self._set_stop_loss_take_profit(
                        symbol=symbol,
                        side=side,
                        size=size,
                        stop_loss=stop_loss,
                        take_profit=take_profit
                    )
                
                # Принудительное обновление кэша позиций
                self._update_positions(force=True)
                
                # Добавление риска в риск-менеджер
                if stop_loss:
                    self.risk_manager.add_position_risk(
                        symbol=symbol,
                        size=size,
                        entry_price=entry_price,
                        stop_loss=stop_loss
                    )
                
                # Журналирование операции
                self.operations_log.append({
                    'time': datetime.now(),
                    'operation': 'open_position',
                    'symbol': symbol,
                    'side': side,
                    'size': size,
                    'entry_price': entry_price,
                    'stop_loss': stop_loss,
                    'take_profit': take_profit,
                    'strategy': strategy_name,
                    'order_id': order_id
                })
                
                return {
                    'success': True,
                    'order_id': order_id,
                    'symbol': symbol,
                    'side': side,
                    'size': size,
                    'entry_price': entry_price,
                    'stop_loss': stop_loss,
                    'take_profit': take_profit
                }
            else:
                error_msg = order_result['retMsg'] if order_result else "Неизвестная ошибка"
                self.logger.error(f"Ошибка при размещении ордера: {error_msg}")
                return None
        
        except Exception as e:
            self.logger.error(f"Ошибка при открытии позиции: {str(e)}")
            return None
    
    def close_position(self, symbol, side=None, percentage=100.0):
        """
        Закрытие позиции
        
        Args:
            symbol (str): торговая пара
            side (str, optional): сторона ('long' или 'short')
            percentage (float): процент позиции для закрытия
            
        Returns:
            dict: результат закрытия позиции
        """
        try:
            # Принудительное обновление кэша позиций
            self._update_positions(force=True)
            
            # Поиск позиции для закрытия
            position = None
            
            if side:
                position_key = f"{symbol}_{side.lower()}"
                position = self.positions.get(position_key)
            else:
                # Поиск любой позиции по символу
                for key, pos in self.positions.items():
                    if pos['symbol'] == symbol:
                        position = pos
                        break
            
            if not position:
                self.logger.warning(f"Не найдена позиция для закрытия: {symbol} {side}")
                return None
            
            # Расчет размера для закрытия
            size = position['size'] * percentage / 100.0
            
            # Противоположная сторона для закрытия
            close_side = "Buy" if position['side'] == "short" else "Sell"
            
            self.logger.info(f"Закрытие позиции: {symbol} {position['side']} размер={size}")
            
            # Режим бумажной торговли
            if self.paper_trading:
                return self._close_paper_position(
                    symbol=symbol,
                    side=position['side'],
                    size=size,
                    percentage=percentage
                )
            
            # Размещение ордера на закрытие
            order_result = self._place_order(
                symbol=symbol,
                side=close_side,
                order_type='Market',
                qty=size,
                price=None,
                reduce_only=True
            )
            
            if order_result and order_result['retCode'] == 0:
                order_id = order_result['result']['orderId']
                self.logger.info(f"Ордер на закрытие размещен успешно: {order_id}")
                
                # Принудительное обновление кэша позиций
                self._update_positions(force=True)
                
                # Уменьшение риска в риск-менеджере
                if position.get('entry_price') and position.get('stop_loss'):
                    self.risk_manager.remove_position_risk(
                        symbol=symbol,
                        size=size,
                        entry_price=position['entry_price'],
                        stop_loss=position['stop_loss']
                    )
                
                # Журналирование операции
                self.operations_log.append({
                    'time': datetime.now(),
                    'operation': 'close_position',
                    'symbol': symbol,
                    'side': position['side'],
                    'size': size,
                    'percentage': percentage,
                    'order_id': order_id
                })
                
                return {
                    'success': True,
                    'order_id': order_id,
                    'symbol': symbol,
                    'side': position['side'],
                    'size': size,
                    'percentage': percentage
                }
            else:
                error_msg = order_result['retMsg'] if order_result else "Неизвестная ошибка"
                self.logger.error(f"Ошибка при размещении ордера на закрытие: {error_msg}")
                return None
        
        except Exception as e:
            self.logger.error(f"Ошибка при закрытии позиции: {str(e)}")
            return None
    
    def modify_position(self, symbol, side, stop_loss=None, take_profit=None, trailing_stop=None):
        """
        Изменение параметров позиции
        
        Args:
            symbol (str): торговая пара
            side (str): сторона ('long' или 'short')
            stop_loss (float, optional): новый уровень стоп-лосса
            take_profit (float, optional): новый уровень тейк-профита
            trailing_stop (float, optional): новый уровень трейлинг-стопа
            
        Returns:
            dict: результат изменения позиции
        """
        try:
            # Принудительное обновление кэша позиций
            self._update_positions(force=True)
            
            # Поиск позиции для изменения
            position_key = f"{symbol}_{side.lower()}"
            position = self.positions.get(position_key)
            
            if not position:
                self.logger.warning(f"Не найдена позиция для модификации: {symbol} {side}")
                return None
            
            # Журналирование операции
            self.logger.info(f"Изменение позиции: {symbol} {side} SL={stop_loss} TP={take_profit} TS={trailing_stop}")
            
            # Режим бумажной торговли
            if self.paper_trading:
                return self._modify_paper_position(
                    symbol=symbol,
                    side=side,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    trailing_stop=trailing_stop
                )
            
            # Отмена существующих заявок на SL/TP
            self._cancel_stop_orders(symbol)
            
            # Установка новых значений SL/TP
            result = self._set_stop_loss_take_profit(
                symbol=symbol,
                side=side,
                size=position['size'],
                stop_loss=stop_loss,
                take_profit=take_profit,
                trailing_stop=trailing_stop
            )
            
            # Журналирование операции
            self.operations_log.append({
                'time': datetime.now(),
                'operation': 'modify_position',
                'symbol': symbol,
                'side': side,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'trailing_stop': trailing_stop
            })
            
            return result
        
        except Exception as e:
            self.logger.error(f"Ошибка при изменении позиции: {str(e)}")
            return None
    
    def manage_positions(self):
        """
        Управление открытыми позициями (проверка трейлинг-стопов и т.д.)
        """
        try:
            # Принудительное обновление кэша позиций
            self._update_positions(force=True)
            
            for position_key, position in self.positions.items():
                symbol = position['symbol']
                side = position['side']
                
                # Проверка условий для трейлинг-стопа
                if self.config['risk_management']['trailing_stop_enabled']:
                    self._check_trailing_stop(symbol, side, position)
                
                # Другая логика управления позициями может быть добавлена здесь
        
        except Exception as e:
            self.logger.error(f"Ошибка при управлении позициями: {str(e)}")
    
    def _check_trailing_stop(self, symbol, side, position):
        """
        Проверка и обновление трейлинг-стопа
        
        Args:
            symbol (str): торговая пара
            side (str): сторона позиции
            position (dict): данные позиции
        """
        try:
            # Получение текущей цены
            ticker = self._get_ticker(symbol)
            if not ticker:
                return
            
            current_price = float(ticker['last_price'])
            entry_price = position['entry_price']
            
            # Настройки трейлинг-стопа
            activation_percent = self.config['risk_management']['trailing_stop_activation'] / 100.0
            callback_percent = self.config['risk_management']['trailing_stop_callback'] / 100.0
            
            # Проверка для лонг-позиции
            if side == 'long':
                profit_percent = (current_price - entry_price) / entry_price
                
                # Если достигнут порог активации трейлинг-стопа
                if profit_percent >= activation_percent:
                    # Расчет нового уровня трейлинг-стопа
                    new_stop = current_price * (1 - callback_percent)
                    
                    # Проверка, что новый стоп выше предыдущего
                    current_stop = position.get('stop_loss', 0)
                    if new_stop > current_stop:
                        # Обновление стоп-лосса
                        self.modify_position(symbol, side, stop_loss=new_stop)
                        self.logger.info(f"Трейлинг-стоп активирован: {symbol} новый уровень={new_stop}")
            
            # Проверка для шорт-позиции
            elif side == 'short':
                profit_percent = (entry_price - current_price) / entry_price
                
                # Если достигнут порог активации трейлинг-стопа
                if profit_percent >= activation_percent:
                    # Расчет нового уровня трейлинг-стопа
                    new_stop = current_price * (1 + callback_percent)
                    
                    # Проверка, что новый стоп ниже предыдущего
                    current_stop = position.get('stop_loss', float('inf'))
                    if new_stop < current_stop:
                        # Обновление стоп-лосса
                        self.modify_position(symbol, side, stop_loss=new_stop)
                        self.logger.info(f"Трейлинг-стоп активирован: {symbol} новый уровень={new_stop}")
        
        except Exception as e:
            self.logger.error(f"Ошибка при проверке трейлинг-стопа: {str(e)}")
    
    def _place_order(self, symbol, side, order_type, qty, price=None, reduce_only=False):
        """
        Размещение ордера через API
        
        Args:
            symbol (str): торговая пара
            side (str): сторона ('Buy' или 'Sell')
            order_type (str): тип ордера ('Market' или 'Limit')
            qty (float): количество
            price (float, optional): цена для лимитного ордера
            reduce_only (bool): флаг reduce_only
            
        Returns:
            dict: ответ API или None в случае ошибки
        """
        try:
            params = {
                "category": "linear",
                "symbol": symbol,
                "side": side,
                "orderType": order_type,
                "qty": str(qty),
                "timeInForce": "GTC",
                "reduceOnly": reduce_only
            }
            
            if order_type == "Limit" and price is not None:
                params["price"] = str(price)
            
            return self.api_client.place_order(**params)
        
        except Exception as e:
            self.logger.error(f"Ошибка при размещении ордера: {str(e)}")
            return None
    
    def _set_stop_loss_take_profit(self, symbol, side, size, stop_loss=None, take_profit=None, trailing_stop=None):
        """
        Установка стоп-лосса и тейк-профита
        
        Args:
            symbol (str): торговая пара
            side (str): сторона ('long' или 'short')
            size (float): размер позиции
            stop_loss (float, optional): уровень стоп-лосса
            take_profit (float, optional): уровень тейк-профита
            trailing_stop (float, optional): уровень трейлинг-стопа
            
        Returns:
            dict: результат установки стоп-лосса и тейк-профита
        """
        try:
            result = {'success': True}
            
            # Нормализация стороны
            api_side = "Sell" if side.lower() == "long" else "Buy"
            
            # Установка стоп-лосса
            if stop_loss is not None:
                sl_params = {
                    "category": "linear",
                    "symbol": symbol,
                    "side": api_side,
                    "orderType": "Market",
                    "qty": str(size),
                    "triggerPrice": str(stop_loss),
                    "triggerBy": "LastPrice",
                    "stopOrderType": "StopLoss",
                    "timeInForce": "GoodTillCancel",
                    "reduceOnly": True
                }
                
                sl_response = self.api_client.place_order(**sl_params)
                
                if sl_response['retCode'] == 0:
                    result['stop_loss'] = {
                        'success': True,
                        'order_id': sl_response['result']['orderId']
                    }
                else:
                    result['stop_loss'] = {
                        'success': False,
                        'error': sl_response['retMsg']
                    }
            
            # Установка тейк-профита
            if take_profit is not None:
                tp_params = {
                    "category": "linear",
                    "symbol": symbol,
                    "side": api_side,
                    "orderType": "Market",
                    "qty": str(size),
                    "triggerPrice": str(take_profit),
                    "triggerBy": "LastPrice",
                    "stopOrderType": "TakeProfit",
                    "timeInForce": "GoodTillCancel",
                    "reduceOnly": True
                }
                
                tp_response = self.api_client.place_order(**tp_params)
                
                if tp_response['retCode'] == 0:
                    result['take_profit'] = {
                        'success': True,
                        'order_id': tp_response['result']['orderId']
                    }
                else:
                    result['take_profit'] = {
                        'success': False,
                        'error': tp_response['retMsg']
                    }
            
            # Установка трейлинг-стопа
            if trailing_stop is not None:
                ts_params = {
                    "category": "linear",
                    "symbol": symbol,
                    "side": api_side,
                    "orderType": "Market",
                    "qty": str(size),
                    "triggerPrice": "0",  # Будет использоваться цена активации
                    "triggerBy": "LastPrice",
                    "stopOrderType": "TrailingStop",
                    "timeInForce": "GoodTillCancel",
                    "trailingStop": str(trailing_stop),
                    "reduceOnly": True
                }
                
                ts_response = self.api_client.place_order(**ts_params)
                
                if ts_response['retCode'] == 0:
                    result['trailing_stop'] = {
                        'success': True,
                        'order_id': ts_response['result']['orderId']
                    }
                else:
                    result['trailing_stop'] = {
                        'success': False,
                        'error': ts_response['retMsg']
                    }
            
            return result
        
        except Exception as e:
            self.logger.error(f"Ошибка при установке SL/TP: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _cancel_stop_orders(self, symbol):
        """
        Отмена всех стоп-ордеров по символу
        
        Args:
            symbol (str): торговая пара
            
        Returns:
            bool: True в случае успеха, иначе False
        """
        try:
            # Получение активных стоп-ордеров
            response = self.api_client.get_open_orders(
                category="linear",
                symbol=symbol,
                orderFilter="StopOrder"
            )
            
            if response['retCode'] != 0:
                self.logger.error(f"Ошибка при получении ордеров: {response['retMsg']}")
                return False
            
            # Отмена каждого ордера
            success = True
            for order in response['result']['list']:
                cancel_response = self.api_client.cancel_order(
                    category="linear",
                    symbol=symbol,
                    orderId=order['orderId']
                )
                
                if cancel_response['retCode'] != 0:
                    self.logger.error(f"Ошибка при отмене ордера {order['orderId']}: {cancel_response['retMsg']}")
                    success = False
            
            return success
        
        except Exception as e:
            self.logger.error(f"Ошибка при отмене стоп-ордеров: {str(e)}")
            return False
    
    def _set_leverage(self, symbol, leverage):
        """
        Установка кредитного плеча
        
        Args:
            symbol (str): торговая пара
            leverage (int): значение плеча
            
        Returns:
            bool: True в случае успеха, иначе False
        """
        try:
            if self.paper_trading:
                return True
                
            response = self.api_client.set_leverage(
                category="linear",
                symbol=symbol,
                buyLeverage=str(leverage),
                sellLeverage=str(leverage)
            )
            
            if response['retCode'] == 0:
                self.logger.info(f"Плечо для {symbol} установлено: {leverage}x")
                return True
            else:
                self.logger.warning(f"Ошибка при установке плеча для {symbol}: {response['retMsg']}")
                return False
        
        except Exception as e:
            self.logger.error(f"Ошибка при установке плеча: {str(e)}")
            return False
    
    def _get_ticker(self, symbol):
        """
        Получение данных тикера
        
        Args:
            symbol (str): торговая пара
            
        Returns:
            dict: данные тикера или None в случае ошибки
        """
        try:
            response = self.api_client.get_tickers(
                category="linear",
                symbol=symbol
            )
            
            if response['retCode'] == 0 and response['result']['list']:
                return response['result']['list'][0]
            else:
                self.logger.warning(f"Ошибка при получении тикера для {symbol}")
                return None
        
        except Exception as e:
            self.logger.error(f"Ошибка при получении тикера: {str(e)}")
            return None
    
    # Методы для бумажной торговли
    def _open_paper_position(self, symbol, side, size, entry_price, stop_loss=None, take_profit=None, strategy_name=None):
        """
        Открытие бумажной позиции
        
        Args:
            symbol (str): торговая пара
            side (str): сторона ('long' или 'short')
            size (float): размер позиции
            entry_price (float): цена входа
            stop_loss (float, optional): уровень стоп-лосса
            take_profit (float, optional): уровень тейк-профита
            strategy_name (str, optional): название стратегии
            
        Returns:
            dict: результат открытия позиции
        """
        position_key = f"{symbol}_{side.lower()}"
        
        # Создание новой позиции
        position = {
            'symbol': symbol,
            'side': side.lower(),
            'size': size,
            'entry_price': entry_price,
            'leverage': self.config['risk_management']['leverage'],
            'margin_type': 'isolated',
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'unrealized_pnl': 0.0,
            'realized_pnl': 0.0,
            'position_value': size * entry_price,
            'strategy': strategy_name,
            'created_time': datetime.now(),
            'updated_time': datetime.now()
        }
        
        # Добавление позиции в кэш
        self.paper_positions[position_key] = position
        
        # Генерация уникального ID ордера
        order_id = f"paper_{int(time.time())}_{hash(symbol)}"
        
        # Журналирование операции
        self.operations_log.append({
            'time': datetime.now(),
            'operation': 'open_paper_position',
            'symbol': symbol,
            'side': side,
            'size': size,
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'strategy': strategy_name,
            'order_id': order_id
        })
        
        # Возвращаем результат
        return {
            'success': True,
            'order_id': order_id,
            'symbol': symbol,
            'side': side,
            'size': size,
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit
        }
    
    def _close_paper_position(self, symbol, side, size, percentage):
        """
        Закрытие бумажной позиции
        
        Args:
            symbol (str): торговая пара
            side (str): сторона ('long' или 'short')
            size (float): размер позиции для закрытия
            percentage (float): процент позиции для закрытия
            
        Returns:
            dict: результат закрытия позиции
        """
        position_key = f"{symbol}_{side.lower()}"
        
        # Проверка существования позиции
        if position_key not in self.paper_positions:
            self.logger.warning(f"Бумажная позиция не найдена: {symbol} {side}")
            return None
        
        position = self.paper_positions[position_key]
        
        # Получение текущей цены
        ticker = self._get_ticker(symbol)
        close_price = float(ticker['last_price']) if ticker else position['entry_price']
        
        # Расчет прибыли/убытка
        if side.lower() == "long":
            pnl = (close_price - position['entry_price']) * size
        else:
            pnl = (position['entry_price'] - close_price) * size
        
        # Применение плеча
        pnl *= position['leverage']
        
        # Обновление баланса
        self.paper_balance += pnl
        
        # Обновление позиции
        position['size'] -= size
        position['realized_pnl'] += pnl
        position['updated_time'] = datetime.now()
        
        # Генерация ID ордера
        order_id = f"paper_close_{int(time.time())}_{hash(symbol)}"
        
        # Если позиция полностью закрыта, удаляем ее
        if position['size'] <= 0 or percentage >= 100.0:
            del self.paper_positions[position_key]
        
        # Журналирование операции
        self.operations_log.append({
            'time': datetime.now(),
            'operation': 'close_paper_position',
            'symbol': symbol,
            'side': side,
            'size': size,
            'percentage': percentage,
            'close_price': close_price,
            'pnl': pnl,
            'order_id': order_id
        })
        
        # Уведомление в лог
        self.logger.info(f"Бумажная позиция закрыта: {symbol} {side} размер={size} P&L={pnl:.2f}")
        
        # Возвращаем результат
        return {
            'success': True,
            'order_id': order_id,
            'symbol': symbol,
            'side': side,
            'size': size,
            'close_price': close_price,
            'pnl': pnl
        }
    
    def _modify_paper_position(self, symbol, side, stop_loss=None, take_profit=None, trailing_stop=None):
        """
        Изменение параметров бумажной позиции
        
        Args:
            symbol (str): торговая пара
            side (str): сторона ('long' или 'short')
            stop_loss (float, optional): новый уровень стоп-лосса
            take_profit (float, optional): новый уровень тейк-профита
            trailing_stop (float, optional): новый уровень трейлинг-стопа
            
        Returns:
            dict: результат изменения позиции
        """
        position_key = f"{symbol}_{side.lower()}"
        
        # Проверка существования позиции
        if position_key not in self.paper_positions:
            self.logger.warning(f"Бумажная позиция не найдена: {symbol} {side}")
            return None
        
        position = self.paper_positions[position_key]
        
        # Обновление параметров
        if stop_loss is not None:
            position['stop_loss'] = stop_loss
        
        if take_profit is not None:
            position['take_profit'] = take_profit
        
        if trailing_stop is not None:
            position['trailing_stop'] = trailing_stop
        
        position['updated_time'] = datetime.now()
        
        # Журналирование операции
        self.operations_log.append({
            'time': datetime.now(),
            'operation': 'modify_paper_position',
            'symbol': symbol,
            'side': side,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'trailing_stop': trailing_stop
        })
        
        # Уведомление в лог
        self.logger.info(f"Бумажная позиция изменена: {symbol} {side} SL={stop_loss} TP={take_profit} TS={trailing_stop}")
        
        # Возвращаем результат
        return {
            'success': True,
            'symbol': symbol,
            'side': side,
            'stop_loss': stop_loss if stop_loss is not None else position.get('stop_loss'),
            'take_profit': take_profit if take_profit is not None else position.get('take_profit'),
            'trailing_stop': trailing_stop if trailing_stop is not None else position.get('trailing_stop')
        }
    
    def _check_paper_stop_loss_take_profit(self):
        """
        Проверка стоп-лоссов и тейк-профитов для бумажных позиций
        """
        if not self.paper_trading:
            return
        
        for position_key, position in list(self.paper_positions.items()):
            symbol = position['symbol']
            side = position['side']
            
            # Получение текущей цены
            ticker = self._get_ticker(symbol)
            if not ticker:
                continue
                
            current_price = float(ticker['last_price'])
            
            # Проверка стоп-лосса
            if position.get('stop_loss'):
                stop_loss = position['stop_loss']
                
                # Для лонг-позиций
                if side == 'long' and current_price <= stop_loss:
                    self.logger.info(f"Сработал стоп-лосс для {symbol} {side}: {stop_loss}")
                    self._close_paper_position(symbol, side, position['size'], 100.0)
                    continue
                
                # Для шорт-позиций
                elif side == 'short' and current_price >= stop_loss:
                    self.logger.info(f"Сработал стоп-лосс для {symbol} {side}: {stop_loss}")
                    self._close_paper_position(symbol, side, position['size'], 100.0)
                    continue
            
            # Проверка тейк-профита
            if position.get('take_profit'):
                take_profit = position['take_profit']
                
                # Для лонг-позиций
                if side == 'long' and current_price >= take_profit:
                    self.logger.info(f"Сработал тейк-профит для {symbol} {side}: {take_profit}")
                    self._close_paper_position(symbol, side, position['size'], 100.0)
                    continue
                
                # Для шорт-позиций
                elif side == 'short' and current_price <= take_profit:
                    self.logger.info(f"Сработал тейк-профит для {symbol} {side}: {take_profit}")
                    self._close_paper_position(symbol, side, position['size'], 100.0)
                    continue
    
    def _update_paper_positions_pnl(self):
        """
        Обновление P&L для бумажных позиций
        """
        if not self.paper_trading:
            return
        
        for position_key, position in self.paper_positions.items():
            symbol = position['symbol']
            side = position['side']
            size = position['size']
            entry_price = position['entry_price']
            
            # Получение текущей цены
            ticker = self._get_ticker(symbol)
            if not ticker:
                continue
                
            current_price = float(ticker['last_price'])
            
            # Расчет нереализованной прибыли/убытка
            if side == 'long':
                pnl = (current_price - entry_price) * size
            else:
                pnl = (entry_price - current_price) * size
            
            # Применение плеча
            pnl *= position['leverage']
            
            # Обновление позиции
            position['unrealized_pnl'] = pnl
            position['updated_time'] = datetime.now()
    
    def get_position_pnl(self, symbol, side=None):
        """
        Получение P&L по позиции
        
        Args:
            symbol (str): торговая пара
            side (str, optional): сторона ('long' или 'short')
            
        Returns:
            dict: информация о P&L
        """
        # Принудительное обновление кэша позиций
        self._update_positions(force=True)
        
        # В режиме бумажной торговли обновляем P&L
        if self.paper_trading:
            self._update_paper_positions_pnl()
        
        # Если указана сторона, ищем конкретную позицию
        if side:
            position_key = f"{symbol}_{side.lower()}"
            position = self.positions.get(position_key)
            
            if position:
                return {
                    'symbol': symbol,
                    'side': side,
                    'unrealized_pnl': position.get('unrealized_pnl', 0),
                    'realized_pnl': position.get('realized_pnl', 0),
                    'total_pnl': position.get('unrealized_pnl', 0) + position.get('realized_pnl', 0)
                }
            else:
                return {
                    'symbol': symbol,
                    'side': side,
                    'unrealized_pnl': 0,
                    'realized_pnl': 0,
                    'total_pnl': 0
                }
        
        # Если сторона не указана, суммируем P&L по всем позициям для символа
        unrealized_pnl = 0
        realized_pnl = 0
        
        for position_key, position in self.positions.items():
            if position['symbol'] == symbol:
                unrealized_pnl += position.get('unrealized_pnl', 0)
                realized_pnl += position.get('realized_pnl', 0)
        
        return {
            'symbol': symbol,
            'unrealized_pnl': unrealized_pnl,
            'realized_pnl': realized_pnl,
            'total_pnl': unrealized_pnl + realized_pnl
        }
    
    def get_position(self, symbol, side=None):
        """
        Получение информации о позиции
        
        Args:
            symbol (str): торговая пара
            side (str, optional): сторона ('long' или 'short')
            
        Returns:
            dict or list: информация о позиции или список позиций
        """
        # Принудительное обновление кэша позиций
        self._update_positions(force=True)
        
        if side:
            position_key = f"{symbol}_{side.lower()}"
            return self.positions.get(position_key)
        else:
            # Возвращаем все позиции по символу
            return [p for p in self.positions.values() if p['symbol'] == symbol]
    
    def get_positions_summary(self):
        """
        Получение сводной информации по всем позициям
        
        Returns:
            dict: сводная информация
        """
        # Принудительное обновление кэша позиций
        self._update_positions(force=True)
        
        # В режиме бумажной торговли обновляем P&L
        if self.paper_trading:
            self._update_paper_positions_pnl()
            self._check_paper_stop_loss_take_profit()
        
        # Статистика по всем позициям
        total_positions = len(self.positions)
        total_long_positions = sum(1 for p in self.positions.values() if p['side'] == 'long')
        total_short_positions = sum(1 for p in self.positions.values() if p['side'] == 'short')
        
        # Общий P&L
        total_unrealized_pnl = sum(p.get('unrealized_pnl', 0) for p in self.positions.values())
        total_realized_pnl = sum(p.get('realized_pnl', 0) for p in self.positions.values())
        
        # Позиции по символам
        positions_by_symbol = {}
        for position in self.positions.values():
            symbol = position['symbol']
            if symbol not in positions_by_symbol:
                positions_by_symbol[symbol] = []
            positions_by_symbol[symbol].append(position)
        
        return {
            'total_positions': total_positions,
            'long_positions': total_long_positions,
            'short_positions': total_short_positions,
            'unrealized_pnl': total_unrealized_pnl,
            'realized_pnl': total_realized_pnl,
            'total_pnl': total_unrealized_pnl + total_realized_pnl,
            'positions_by_symbol': positions_by_symbol,
            'paper_trading': self.paper_trading,
            'paper_balance': self.paper_balance if self.paper_trading else None
        }