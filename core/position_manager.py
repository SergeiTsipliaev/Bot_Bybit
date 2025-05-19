import time
import logging
from typing import Dict, List, Optional, Tuple, Union
from decimal import Decimal

# Предполагаем, что у нас есть клиент Bybit в другом модуле
from .bybit_client import BybitClient
from .risk_manager import RiskManager
from .order_manager import OrderManager
from .position_calculator import calculate_position_size, calculate_stop_loss, calculate_take_profit

# Настройка логгера
logger = logging.getLogger(__name__)

class PositionManager:
    """
    Класс для управления позициями на бирже Bybit.
    Отвечает за:
    - Открытие новых позиций
    - Закрытие существующих позиций
    - Модификацию параметров открытых позиций
    - Контроль риска и прибыли
    - Мониторинг статуса позиций
    """
    
    def __init__(self, client: BybitClient, risk_manager: RiskManager, order_manager: OrderManager):
        """
        Инициализация менеджера позиций
        
        Args:
            client: Экземпляр клиента Bybit API
            risk_manager: Экземпляр менеджера риска
            order_manager: Экземпляр менеджера ордеров
        """
        self.client = client
        self.risk_manager = risk_manager
        self.order_manager = order_manager
        
        # Кэш открытых позиций
        self._positions_cache = {}
        self._last_update_time = 0
        
        # Интервал обновления кэша позиций (в секундах)
        self.cache_update_interval = 5
    
    def refresh_positions(self, force: bool = False) -> Dict:
        """
        Обновляет кэш открытых позиций
        
        Args:
            force: Принудительно обновить кэш, игнорируя интервал обновления
            
        Returns:
            Dict: Словарь с текущими открытыми позициями
        """
        current_time = time.time()
        
        # Проверяем, нужно ли обновлять кэш
        if force or (current_time - self._last_update_time) >= self.cache_update_interval:
            try:
                # Получаем все открытые позиции
                positions = self.client.get_positions()
                
                # Обновляем кэш
                self._positions_cache = {
                    f"{p['symbol']}_{p['side'].lower()}": p 
                    for p in positions if float(p['size']) > 0
                }
                
                self._last_update_time = current_time
                logger.debug(f"Positions cache refreshed. Found {len(self._positions_cache)} active positions.")
            except Exception as e:
                logger.error(f"Failed to refresh positions: {str(e)}")
        
        return self._positions_cache
    
    def get_position(self, symbol: str, side: str = None) -> Optional[Dict]:
        """
        Получает информацию о конкретной позиции
        
        Args:
            symbol: Символ торговой пары (например, 'BTCUSDT')
            side: Сторона позиции ('buy' или 'sell'). Если не указана, 
                  возвращает все позиции по данному символу
        
        Returns:
            Dict or List[Dict]: Информация о позиции или список позиций
        """
        # Обновляем кэш позиций
        positions = self.refresh_positions()
        
        if side:
            # Нормализуем сторону к нижнему регистру
            side = side.lower()
            position_key = f"{symbol}_{side}"
            return positions.get(position_key)
        else:
            # Возвращаем все позиции по символу
            return [p for k, p in positions.items() if k.startswith(f"{symbol}_")]
    
    def open_position(
        self, 
        symbol: str, 
        side: str, 
        size: Union[float, Decimal] = None, 
        entry_price: Union[float, Decimal] = None,
        stop_loss: Union[float, Decimal] = None,
        take_profit: Union[float, Decimal] = None,
        leverage: int = None,
        position_mode: str = "one-way",
        order_type: str = "market",
        time_in_force: str = "GoodTillCancel",
        reduce_only: bool = False,
        close_on_trigger: bool = False,
        risk_percentage: float = None,
        **kwargs
    ) -> Dict:
        """
        Открывает новую позицию
        
        Args:
            symbol: Символ торговой пары
            side: Сторона ('buy' или 'sell')
            size: Размер позиции (в контрактах или долларах, в зависимости от настроек)
            entry_price: Цена входа (для лимитных ордеров)
            stop_loss: Уровень стоп-лосса
            take_profit: Уровень тейк-профита
            leverage: Кредитное плечо
            position_mode: Режим позиции ('one-way' или 'hedge')
            order_type: Тип ордера ('market', 'limit', 'stop', 'stop_market', 'take_profit', 'take_profit_market')
            time_in_force: Время действия ордера ('GoodTillCancel', 'ImmediateOrCancel', 'FillOrKill', 'PostOnly')
            reduce_only: Флаг reduce-only
            close_on_trigger: Флаг close-on-trigger
            risk_percentage: Процент риска от баланса (если указан, то size будет рассчитан автоматически)
            
        Returns:
            Dict: Результат размещения ордера
        """
        # Нормализуем сторону
        side = side.lower()
        
        # Проверяем, установлен ли режим позиции
        current_mode = self.client.get_position_mode(symbol)
        if current_mode != position_mode:
            logger.info(f"Changing position mode for {symbol} from {current_mode} to {position_mode}")
            self.client.set_position_mode(symbol, position_mode)
        
        # Если указан leverage, устанавливаем его
        if leverage is not None:
            current_leverage = self.client.get_leverage(symbol)
            if current_leverage != leverage:
                logger.info(f"Changing leverage for {symbol} from {current_leverage}x to {leverage}x")
                self.client.set_leverage(symbol, leverage)
        
        # Получаем текущую цену, если необходимо
        current_price = None
        if entry_price is None or risk_percentage is not None:
            ticker = self.client.get_ticker(symbol)
            current_price = float(ticker["last_price"])
            
            if entry_price is None and order_type != "market":
                entry_price = current_price
        
        # Рассчитываем размер позиции на основе риска, если указан
        if risk_percentage is not None:
            if stop_loss is None:
                raise ValueError("Stop loss must be provided when using risk-based position sizing")
            
            # Получаем баланс аккаунта
            account_info = self.client.get_wallet_balance()
            balance = float(account_info["balance"])
            
            # Рассчитываем размер позиции
            price = entry_price if entry_price is not None else current_price
            size = calculate_position_size(
                balance=balance,
                risk_percentage=risk_percentage,
                entry_price=price,
                stop_loss=float(stop_loss),
                leverage=leverage or 1
            )
            
            logger.info(f"Calculated position size based on {risk_percentage}% risk: {size}")
        
        # Проверяем через риск-менеджер
        if not self.risk_manager.is_position_allowed(
            symbol=symbol, 
            side=side, 
            size=size, 
            leverage=leverage,
            current_positions=self.refresh_positions(force=True)
        ):
            error_msg = f"Position not allowed by risk manager: {symbol} {side} {size}"
            logger.warning(error_msg)
            raise ValueError(error_msg)
        
        # Размещаем основной ордер для входа в позицию
        order_result = self.order_manager.place_order(
            symbol=symbol,
            side=side,
            qty=size,
            price=entry_price,
            order_type=order_type,
            time_in_force=time_in_force,
            reduce_only=reduce_only,
            close_on_trigger=close_on_trigger,
            **kwargs
        )
        
        # Если ордер успешно размещен, устанавливаем стоп-лосс и тейк-профит
        if order_result.get("order_id") and (stop_loss is not None or take_profit is not None):
            try:
                # Устанавливаем стоп-лосс
                if stop_loss is not None:
                    sl_side = "sell" if side == "buy" else "buy"
                    self.order_manager.place_order(
                        symbol=symbol,
                        side=sl_side,
                        qty=size,
                        price=stop_loss,
                        order_type="stop",
                        time_in_force="GoodTillCancel",
                        reduce_only=True,
                        close_on_trigger=True,
                        trigger_price=stop_loss,
                        **kwargs
                    )
                
                # Устанавливаем тейк-профит
                if take_profit is not None:
                    tp_side = "sell" if side == "buy" else "buy"
                    self.order_manager.place_order(
                        symbol=symbol,
                        side=tp_side,
                        qty=size,
                        price=take_profit,
                        order_type="take_profit",
                        time_in_force="GoodTillCancel",
                        reduce_only=True,
                        close_on_trigger=True,
                        trigger_price=take_profit,
                        **kwargs
                    )
            except Exception as e:
                logger.error(f"Failed to set SL/TP for {symbol} {side} position: {str(e)}")
        
        # Заставляем обновить кэш после открытия позиции
        self.refresh_positions(force=True)
        
        return order_result
    
    def close_position(
        self, 
        symbol: str, 
        side: str = None, 
        percentage: float = 100.0,
        order_type: str = "market",
        **kwargs
    ) -> Dict:
        """
        Закрывает позицию полностью или частично
        
        Args:
            symbol: Символ торговой пары
            side: Сторона позиции ('buy' или 'sell'). Если не указана и есть 
                  только одна позиция по символу, закрывается она
            percentage: Процент позиции для закрытия (по умолчанию 100%)
            order_type: Тип ордера для закрытия ('market', 'limit')
            **kwargs: Дополнительные параметры для ордера
            
        Returns:
            Dict: Результат размещения ордера на закрытие
        """
        # Получаем информацию о позиции
        position = None
        
        if side:
            # Если указана сторона, получаем конкретную позицию
            position = self.get_position(symbol, side)
        else:
            # Иначе получаем все позиции по символу
            positions = self.get_position(symbol)
            if len(positions) == 1:
                position = positions[0]
            elif len(positions) > 1:
                raise ValueError(f"Multiple positions found for {symbol}. Please specify side ('buy' or 'sell').")
        
        if not position or float(position['size']) == 0:
            logger.warning(f"No active position found for {symbol} {side if side else ''}")
            return {"success": False, "message": "No active position found"}
        
        # Определяем сторону для ордера закрытия (противоположную открытой позиции)
        close_side = "sell" if position['side'].lower() == "buy" else "buy"
        
        # Рассчитываем размер для закрытия
        position_size = float(position['size'])
        close_size = position_size * percentage / 100.0
        
        # Размещаем ордер на закрытие
        order_result = self.order_manager.place_order(
            symbol=symbol,
            side=close_side,
            qty=close_size,
            order_type=order_type,
            reduce_only=True,
            **kwargs
        )
        
        # Заставляем обновить кэш после закрытия
        self.refresh_positions(force=True)
        
        return order_result
    
    def modify_position(
        self, 
        symbol: str, 
        side: str,
        stop_loss: Union[float, Decimal] = None,
        take_profit: Union[float, Decimal] = None,
        trailing_stop: Union[float, Decimal] = None,
        **kwargs
    ) -> Dict:
        """
        Изменяет параметры существующей позиции
        
        Args:
            symbol: Символ торговой пары
            side: Сторона позиции ('buy' или 'sell')
            stop_loss: Новый уровень стоп-лосса
            take_profit: Новый уровень тейк-профита
            trailing_stop: Новое значение trailing stop
            
        Returns:
            Dict: Результат изменения параметров
        """
        # Получаем информацию о позиции
        position = self.get_position(symbol, side)
        
        if not position or float(position['size']) == 0:
            logger.warning(f"No active position found for {symbol} {side}")
            return {"success": False, "message": "No active position found"}
        
        result = {}
        
        # Отменяем существующие стоп-лосс и тейк-профит ордера
        try:
            # Получаем активные ордера
            active_orders = self.client.get_active_orders(symbol)
            
            # Фильтруем ордера SL/TP, связанные с позицией
            sl_tp_orders = [
                order for order in active_orders
                if (order["order_type"] in ["stop", "stop_market", "take_profit", "take_profit_market"])
                and order["reduce_only"] == True
            ]
            
            # Отменяем найденные ордера
            for order in sl_tp_orders:
                self.order_manager.cancel_order(symbol, order["order_id"])
                logger.debug(f"Cancelled {order['order_type']} order {order['order_id']} for {symbol}")
        except Exception as e:
            logger.error(f"Failed to cancel existing SL/TP orders: {str(e)}")
        
        # Устанавливаем новые значения
        try:
            position_size = float(position['size'])
            opposite_side = "sell" if side.lower() == "buy" else "buy"
            
            # Устанавливаем новый стоп-лосс
            if stop_loss is not None:
                sl_result = self.order_manager.place_order(
                    symbol=symbol,
                    side=opposite_side,
                    qty=position_size,
                    price=stop_loss,
                    order_type="stop",
                    time_in_force="GoodTillCancel",
                    reduce_only=True,
                    close_on_trigger=True,
                    trigger_price=stop_loss,
                    **kwargs
                )
                result["stop_loss"] = sl_result
            
            # Устанавливаем новый тейк-профит
            if take_profit is not None:
                tp_result = self.order_manager.place_order(
                    symbol=symbol,
                    side=opposite_side,
                    qty=position_size,
                    price=take_profit,
                    order_type="take_profit",
                    time_in_force="GoodTillCancel",
                    reduce_only=True,
                    close_on_trigger=True,
                    trigger_price=take_profit,
                    **kwargs
                )
                result["take_profit"] = tp_result
            
            # Устанавливаем trailing stop
            if trailing_stop is not None:
                ts_result = self.client.set_trading_stop(
                    symbol=symbol,
                    side=side,
                    trailing_stop=trailing_stop
                )
                result["trailing_stop"] = ts_result
                
        except Exception as e:
            logger.error(f"Failed to modify position parameters: {str(e)}")
            result["error"] = str(e)
        
        return result
    
    def get_position_pnl(self, symbol: str, side: str = None) -> Dict:
        """
        Получает информацию о прибыли/убытке позиции
        
        Args:
            symbol: Символ торговой пары
            side: Сторона позиции ('buy' или 'sell'). Если не указана, 
                  возвращает суммарную P&L по всем позициям
                  
        Returns:
            Dict: Информация о P&L
        """
        if side:
            position = self.get_position(symbol, side)
            if not position:
                return {"unrealized_pnl": 0, "realized_pnl": 0, "total_pnl": 0}
            
            return {
                "unrealized_pnl": float(position.get("unrealised_pnl", 0)),
                "realized_pnl": float(position.get("realised_pnl", 0)),
                "total_pnl": float(position.get("unrealised_pnl", 0)) + float(position.get("realised_pnl", 0)),
                "roe": float(position.get("return_on_equity", 0)) * 100  # ROE в процентах
            }
        else:
            # Получаем все позиции по символу
            positions = self.get_position(symbol)
            
            # Суммируем P&L по всем позициям
            unrealized_pnl = sum(float(p.get("unrealised_pnl", 0)) for p in positions)
            realized_pnl = sum(float(p.get("realised_pnl", 0)) for p in positions)
            
            return {
                "unrealized_pnl": unrealized_pnl,
                "realized_pnl": realized_pnl, 
                "total_pnl": unrealized_pnl + realized_pnl
            }
    
    def calculate_optimal_position_params(
        self,
        symbol: str,
        side: str,
        entry_price: Union[float, Decimal] = None,
        risk_percentage: float = 1.0,
        risk_reward_ratio: float = 2.0,
        atr_multiplier: float = 1.5,
        **kwargs
    ) -> Dict:
        """
        Рассчитывает оптимальные параметры для новой позиции на основе ATR и риска
        
        Args:
            symbol: Символ торговой пары
            side: Сторона ('buy' или 'sell')
            entry_price: Цена входа (если None, используется текущая цена)
            risk_percentage: Процент риска от баланса
            risk_reward_ratio: Соотношение риск/прибыль
            atr_multiplier: Множитель ATR для стоп-лосса
            
        Returns:
            Dict: Оптимальные параметры позиции
        """
        # Получаем текущую цену, если необходимо
        if entry_price is None:
            ticker = self.client.get_ticker(symbol)
            entry_price = float(ticker["last_price"])
        else:
            entry_price = float(entry_price)
        
        # Получаем значение ATR
        # Предполагаем, что у нас есть функция для расчета ATR
        from ..indicators.volatility import get_atr
        atr = get_atr(self.client, symbol, timeframe="1h", length=14)
        
        # Рассчитываем стоп-лосс на основе ATR
        if side.lower() == "buy":
            stop_loss = entry_price - (atr * atr_multiplier)
        else:
            stop_loss = entry_price + (atr * atr_multiplier)
        
        # Рассчитываем тейк-профит на основе риск/прибыль
        risk = abs(entry_price - stop_loss)
        reward = risk * risk_reward_ratio
        
        if side.lower() == "buy":
            take_profit = entry_price + reward
        else:
            take_profit = entry_price - reward
        
        # Получаем баланс аккаунта
        account_info = self.client.get_wallet_balance()
        balance = float(account_info["balance"])
        
        # Получаем текущее плечо
        leverage = self.client.get_leverage(symbol)
        
        # Рассчитываем размер позиции
        size = calculate_position_size(
            balance=balance,
            risk_percentage=risk_percentage,
            entry_price=entry_price,
            stop_loss=stop_loss,
            leverage=leverage
        )
        
        return {
            "symbol": symbol,
            "side": side,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "size": size,
            "leverage": leverage,
            "risk_amount": balance * risk_percentage / 100.0,
            "potential_profit": balance * risk_percentage / 100.0 * risk_reward_ratio,
            "risk_pct": risk_percentage,
            "risk_reward_ratio": risk_reward_ratio
        }


def calculate_position_size(
    balance: float,
    risk_percentage: float,
    entry_price: float,
    stop_loss: float,
    leverage: float = 1.0
) -> float:
    """
    Рассчитывает размер позиции на основе риска
    
    Args:
        balance: Баланс аккаунта
        risk_percentage: Процент риска от баланса
        entry_price: Цена входа
        stop_loss: Уровень стоп-лосса
        leverage: Кредитное плечо
        
    Returns:
        float: Размер позиции в контрактах
    """
    # Рассчитываем сумму риска в валюте
    risk_amount = balance * (risk_percentage / 100.0)
    
    # Рассчитываем риск на единицу (разница между входом и стоп-лоссом)
    price_risk = abs(entry_price - stop_loss)
    
    if price_risk == 0:
        raise ValueError("Entry price cannot be the same as stop loss")
    
    # Рассчитываем размер позиции без учета плеча
    raw_position_size = risk_amount / price_risk
    
    # Учитываем плечо
    position_size = raw_position_size * leverage
    
    return position_size