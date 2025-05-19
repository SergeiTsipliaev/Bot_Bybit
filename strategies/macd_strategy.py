# -*- coding: utf-8 -*-

"""
Стратегия на основе MACD (Moving Average Convergence Divergence)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from strategies.base_strategy import BaseStrategy
from indicators.technical_indicators import calculate_macd, calculate_rsi, calculate_bollinger_bands

class MacdStrategy(BaseStrategy):
    """Стратегия торговли на основе MACD и RSI"""
    
    def _initialize(self):
        """Инициализация настроек стратегии"""
        super()._initialize()
        
        # Загрузка параметров стратегии из конфигурации
        self.macd_fast = self.params.get('macd_fast', 12)
        self.macd_slow = self.params.get('macd_slow', 26)
        self.macd_signal = self.params.get('macd_signal', 9)
        
        self.rsi_period = self.params.get('rsi_period', 14)
        self.rsi_overbought = self.params.get('rsi_overbought', 70)
        self.rsi_oversold = self.params.get('rsi_oversold', 30)
        
        # Параметры для управления позициями
        self.max_positions = self.params.get('max_positions', 5)
        self.position_size_pct = self.params.get('position_size_pct', 2.0)  # процент от баланса
        
        # Накопленные данные для анализа
        self.historical_signals = {}
    
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
                            self.logger.info(f"Позиция открыта по стратегии MACD: {symbol} {signal['side']}")
        
        except Exception as e:
            self.logger.error(f"Ошибка при выполнении стратегии MACD: {str(e)}")
    
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
            if df.empty:
                return None
            
            # Минимальное количество свечей для анализа
            min_candles = max(self.macd_slow, self.rsi_period) + 20
            if len(df) < min_candles:
                return None
            
            # Расчет индикаторов
            # 1. MACD
            df['macd'], df['macd_signal'], df['macd_hist'] = calculate_macd(
                df, self.macd_fast, self.macd_slow, self.macd_signal, 'close'
            )
            
            # 2. RSI
            df['rsi'] = calculate_rsi(df, self.rsi_period, 'close')
            
            # 3. Bollinger Bands для определения волатильности
            df['bb_upper'], df['bb_middle'], df['bb_lower'] = calculate_bollinger_bands(
                df, 20, 2, 'close'
            )
            
            # Получение значений индикаторов
            current_macd = df['macd'].iloc[-1]
            current_signal = df['macd_signal'].iloc[-1]
            current_hist = df['macd_hist'].iloc[-1]
            prev_hist = df['macd_hist'].iloc[-2]
            
            current_rsi = df['rsi'].iloc[-1]
            prev_rsi = df['rsi'].iloc[-2]
            
            current_close = df['close'].iloc[-1]
            current_bb_upper = df['bb_upper'].iloc[-1]
            current_bb_lower = df['bb_lower'].iloc[-1]
            current_bb_middle = df['bb_middle'].iloc[-1]
            
            # Логика формирования сигналов
            
            # Long сигнал (покупка)
            long_signal = False
            long_reason = ""
            
            # MACD пересекает сигнальную линию снизу вверх
            macd_long_cross = current_macd > current_signal and df['macd'].iloc[-2] < df['macd_signal'].iloc[-2]
            
            # MACD гистограмма разворачивается вверх из отрицательной зоны
            macd_long_hist = current_hist > prev_hist and prev_hist < 0
            
            # RSI вышел из перепроданной зоны
            rsi_long = prev_rsi < self.rsi_oversold and current_rsi > self.rsi_oversold
            
            # Комбинированный сигнал на вход в длинную позицию
            if (macd_long_cross or macd_long_hist) and current_rsi < 60:
                long_signal = True
                long_reason = "MACD сигнал на покупку, RSI не перекуплен"
            
            elif rsi_long and current_macd > current_signal:
                long_signal = True
                long_reason = "RSI вышел из перепроданной зоны, MACD положительный"
            
            # Short сигнал (продажа)
            short_signal = False
            short_reason = ""
            
            # MACD пересекает сигнальную линию сверху вниз
            macd_short_cross = current_macd < current_signal and df['macd'].iloc[-2] > df['macd_signal'].iloc[-2]
            
            # MACD гистограмма разворачивается вниз из положительной зоны
            macd_short_hist = current_hist < prev_hist and prev_hist > 0
            
            # RSI вышел из перекупленной зоны
            rsi_short = prev_rsi > self.rsi_overbought and current_rsi < self.rsi_overbought
            
            # Комбинированный сигнал на вход в короткую позицию
            if (macd_short_cross or macd_short_hist) and current_rsi > 40:
                short_signal = True
                short_reason = "MACD сигнал на продажу, RSI не перепродан"
            
            elif rsi_short and current_macd < current_signal:
                short_signal = True
                short_reason = "RSI вышел из перекупленной зоны, MACD отрицательный"
            
            # Формирование сигнала
            signal = None
            
            # Если есть сигнал на покупку и лонг-позиции не заблокированы
            if long_signal and not self.block_long_entries:
                # Расчет уровней стоп-лосса и тейк-профита
                stop_loss = current_close * 0.97  # -3%
                take_profit = current_close * 1.06  # +6%
                
                # Более точная настройка стоп-лосса на основе ATR или волатильности
                # можно реализовать с помощью Bollinger Bands
                volatility = (current_bb_upper - current_bb_lower) / current_bb_middle
                
                if volatility > 0.05:  # Высокая волатильность
                    stop_loss = current_close * 0.96  # Увеличиваем стоп-лосс
                    take_profit = current_close * 1.08  # Увеличиваем тейк-профит
                
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
                stop_loss = current_close * 1.03  # +3%
                take_profit = current_close * 0.94  # -6%
                
                # Адаптация к волатильности
                volatility = (current_bb_upper - current_bb_lower) / current_bb_middle
                
                if volatility > 0.05:  # Высокая волатильность
                    stop_loss = current_close * 1.04  # Увеличиваем стоп-лосс
                    take_profit = current_close * 0.92  # Увеличиваем тейк-профит
                
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
                
                # Если тренд BTC бычий, уменьшаем стоп-лосс для шорт-позиций
                if btc_trend == 'bullish' and signal['side'] == 'short':
                    signal['stop_loss'] = current_close * 1.02  # Уменьшаем стоп-лосс для шортов
            
            return signal
        
        except Exception as e:
            self.logger.error(f"Ошибка при анализе MACD для {symbol} {timeframe}: {str(e)}")
            return None