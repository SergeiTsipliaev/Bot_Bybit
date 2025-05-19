# -*- coding: utf-8 -*-

"""
Стратегия на основе уровней поддержки и сопротивления
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from strategies.base_strategy import BaseStrategy
from indicators.technical_indicators import (
    calculate_support_resistance, calculate_rsi, calculate_bollinger_bands, calculate_atr
)

class SupportResistanceStrategy(BaseStrategy):
    """Стратегия торговли на основе уровней поддержки и сопротивления"""
    
    def _initialize(self):
        """Инициализация настроек стратегии"""
        super()._initialize()
        
        # Загрузка параметров стратегии из конфигурации
        self.window = self.params.get('window', 20)
        self.lookback_periods = self.params.get('lookback_periods', 100)
        
        self.rsi_period = self.params.get('rsi_period', 14)
        self.rsi_overbought = self.params.get('rsi_overbought', 70)
        self.rsi_oversold = self.params.get('rsi_oversold', 30)
        
        self.atr_period = self.params.get('atr_period', 14)
        self.atr_multiplier = self.params.get('atr_multiplier', 2.0)
        
        # Параметры для управления позициями
        self.max_positions = self.params.get('max_positions', 5)
        
        # Хранение найденных уровней поддержки и сопротивления
        self.sr_levels = {}
    
    def execute(self):
        """Выполнение стратегии"""
        try:
            # Проверка активности стратегии
            if not self.is_enabled():
                return
            
            # Перебор всех символов и таймфреймов
            for symbol in self.symbols:
                for timeframe in self.timeframes:
                    # Проверка необходимости анализа таймфрейма
                    if not self.should_check_timeframe(symbol, timeframe):
                        continue
                    
                    # Анализ рыночных данных и получение сигналов
                    signal = self.analyze(symbol, timeframe)
                    
                    # Обработка полученного сигнала
                    if signal:
                        result = self.process_signal(signal)
                        
                        # Если позиция открыта успешно, обновляем статистику
                        if result:
                            self.logger.info(f"Позиция открыта по стратегии поддержка/сопротивление: {symbol} {signal['side']}")
        
        except Exception as e:
            self.logger.error(f"Ошибка при выполнении стратегии поддержка/сопротивление: {str(e)}")
    
    def analyze(self, symbol, timeframe):
        """
        Анализ рыночных данных и генерация сигналов
        
        Args:
            symbol (str): торговая пара
            timeframe (str): временной интервал
        
        Returns:
            dict: сигнал для торговли или None
        """
        try:
            # Получение свечей
            df = self.market_data.get_candles(symbol, timeframe)
            if df.empty or len(df) < self.lookback_periods:
                return None
            
            # Если в кэше нет записей для этой пары и таймфрейма, создаем их
            if symbol not in self.sr_levels:
                self.sr_levels[symbol] = {}
            
            if timeframe not in self.sr_levels[symbol]:
                self.sr_levels[symbol][timeframe] = {
                    'support': [],
                    'resistance': [],
                    'last_update': datetime.now() - timedelta(days=1)
                }
            
            # Проверяем, нужно ли обновить уровни поддержки и сопротивления
            # Обновляем их не слишком часто, чтобы избежать частых колебаний
            sr_data = self.sr_levels[symbol][timeframe]
            now = datetime.now()
            
            # Определяем интервал обновления в зависимости от таймфрейма
            update_interval = timedelta(hours=1)
            if timeframe in ['1h', '4h', '1d']:
                update_interval = timedelta(hours=4)
            
            # Обновление уровней поддержки и сопротивления
            if now - sr_data['last_update'] > update_interval:
                support, resistance = calculate_support_resistance(df, self.window)
                
                # Обновляем уровни только если они существенно изменились
                # или если это первое обновление
                if not sr_data['support'] or not sr_data['resistance'] or \
                   abs(support - sr_data['support'][-1]) / sr_data['support'][-1] > 0.02 or \
                   abs(resistance - sr_data['resistance'][-1]) / sr_data['resistance'][-1] > 0.02:
                    
                    sr_data['support'].append(support)
                    sr_data['resistance'].append(resistance)
                    
                    # Ограничиваем количество хранимых уровней
                    max_levels = 10
                    if len(sr_data['support']) > max_levels:
                        sr_data['support'] = sr_data['support'][-max_levels:]
                    
                    if len(sr_data['resistance']) > max_levels:
                        sr_data['resistance'] = sr_data['resistance'][-max_levels:]
                
                sr_data['last_update'] = now
            
            # Получение текущих уровней поддержки и сопротивления
            current_support = sr_data['support'][-1] if sr_data['support'] else None
            current_resistance = sr_data['resistance'][-1] if sr_data['resistance'] else None
            
            if not current_support or not current_resistance:
                return None
            
            # Расчет дополнительных индикаторов
            df['rsi'] = calculate_rsi(df, self.rsi_period, 'close')
            df['atr'] = calculate_atr(df, self.atr_period)
            
            # Получение текущих значений
            current_close = df['close'].iloc[-1]
            current_rsi = df['rsi'].iloc[-1]
            current_atr = df['atr'].iloc[-1]
            
            # Логика формирования сигналов
            
            # Определение близости цены к уровням поддержки/сопротивления
            # Используем ATR для динамического определения "близости"
            atr_threshold = current_atr * self.atr_multiplier
            
            # Проверка близости к поддержке
            near_support = abs(current_close - current_support) < atr_threshold
            
            # Проверка близости к сопротивлению
            near_resistance = abs(current_close - current_resistance) < atr_threshold
            
            # Определение силы отскока от уровня
            bounce_threshold = 0.005  # 0.5%
            
            # Long сигнал (покупка)
            long_signal = False
            long_reason = ""
            
            # Short сигнал (продажа)
            short_signal = False
            short_reason = ""
            
            # Проверка свечных паттернов для определения отскока
            
            # Если цена близка к поддержке и RSI перепродан, это сигнал на покупку
            if near_support and current_rsi < self.rsi_oversold:
                # Проверка последних нескольких свечей для подтверждения отскока
                last_candles = df.iloc[-3:]
                
                # Если последняя свеча зеленая (close > open) после нескольких красных,
                # это может указывать на разворот
                if last_candles['close'].iloc[-1] > last_candles['open'].iloc[-1] and \
                   last_candles['close'].iloc[-2] < last_candles['open'].iloc[-2]:
                    
                    long_signal = True
                    long_reason = "Отскок от уровня поддержки, RSI перепродан"
            
            # Если цена близка к сопротивлению и RSI перекуплен, это сигнал на продажу
            if near_resistance and current_rsi > self.rsi_overbought:
                # Проверка последних нескольких свечей для подтверждения отскока
                last_candles = df.iloc[-3:]
                
                # Если последняя свеча красная (close < open) после нескольких зеленых,
                # это может указывать на разворот
                if last_candles['close'].iloc[-1] < last_candles['open'].iloc[-1] and \
                   last_candles['close'].iloc[-2] > last_candles['open'].iloc[-2]:
                    
                    short_signal = True
                    short_reason = "Отскок от уровня сопротивления, RSI перекуплен"
            
            # Формирование сигнала
            signal = None
            
            # Если есть сигнал на покупку и лонг-позиции не заблокированы
            if long_signal and not self.block_long_entries:
                # Расчет уровней стоп-лосса и тейк-профита
                stop_loss = current_support - current_atr  # Стоп-лосс ниже уровня поддержки на величину ATR
                take_profit = current_close + (current_close - stop_loss) * 2  # RR = 1:2
                
                signal = {
                    'symbol': symbol,
                    'timeframe': timeframe,
                    'side': 'long',
                    'entry_price': current_close,
                    'stop_loss': stop_loss,
                    'take_profit': take_profit,
                    'reason': long_reason,
                    'time': datetime.now()
                }
            
            # Если есть сигнал на продажу
            elif short_signal:
                # Расчет уровней стоп-лосса и тейк-профита
                stop_loss = current_resistance + current_atr  # Стоп-лосс выше уровня сопротивления на величину ATR
                take_profit = current_close - (stop_loss - current_close) * 2  # RR = 1:2
                
                signal = {
                    'symbol': symbol,
                    'timeframe': timeframe,
                    'side': 'short',
                    'entry_price': current_close,
                    'stop_loss': stop_loss,
                    'take_profit': take_profit,
                    'reason': short_reason,
                    'time': datetime.now()
                }
            
            # Фильтрация сигналов на основе тренда BTC
            if signal:
                btc_trend = self.market_analyzer.btc_trend
                
                # Если тренд BTC медвежий, блокируем лонг-сигналы
                if btc_trend == 'bearish' and signal['side'] == 'long':
                    self.logger.info(f"Лонг-сигнал по {symbol} заблокирован из-за медвежьего тренда BTC")
                    return None
                
                # Если тренд BTC бычий, уменьшаем размер шорт-позиций
                if btc_trend == 'bullish' and signal['side'] == 'short':
                    # Уменьшаем размер позиции для шортов при бычьем тренде BTC
                    signal['size_adjustment'] = 0.5  # Размер позиции будет уменьшен вдвое
            
            return signal
        
        except Exception as e:
            self.logger.error(f"Ошибка при анализе поддержки/сопротивления для {symbol} {timeframe}: {str(e)}")
            return None