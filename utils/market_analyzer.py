# -*- coding: utf-8 -*-

"""
Класс для анализа рыночных данных
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from indicators.technical_indicators import (
    calculate_ma, calculate_ema, calculate_macd, calculate_rsi, 
    calculate_stochastic, calculate_bollinger_bands, calculate_atr, 
    calculate_support_resistance, identify_patterns
)

class MarketAnalyzer:
    """Класс для анализа рыночных данных и определения торговых сигналов"""
    
    def __init__(self, config, logger=None):
        """
        Инициализация анализатора рынка
        
        Args:
            config (dict): конфигурация бота
            logger: объект логгера
        """
        self.config = config
        self.logger = logger
        
        # Загрузка настроек анализа
        self.btc_analysis_config = config.get('btc_analysis', {})
        self.analysis_config = config.get('market_analysis', {})
        
        # Кэш результатов анализа
        # {symbol: {timeframe: {indicator: value}}}
        self.analysis_cache = {}
        
        # Информация о текущем тренде BTC
        self.btc_trend = "neutral"
        self.btc_trend_strength = 0.0
        self.btc_trend_updated = datetime.now()
    
    def update(self, market_data):
        """
        Обновление анализа рыночных данных
        
        Args:
            market_data: объект с рыночными данными
        """
        try:
            # Обновление анализа тренда BTC
            self.analyze_btc_trend(market_data)
            
            # Анализ всех отслеживаемых символов
            for symbol in market_data.symbols:
                self._analyze_symbol(symbol, market_data)
        
        except Exception as e:
            self.logger.error(f"Ошибка при обновлении анализа рынка: {str(e)}")
    
    def analyze_btc_trend(self, market_data=None):
        """
        Анализ тренда BTC
        
        Args:
            market_data: объект с рыночными данными
        
        Returns:
            str: тренд BTC ('bullish', 'bearish', 'neutral')
        """
        try:
            # Если нет данных или прошло мало времени с последнего обновления,
            # возвращаем текущий тренд
            if market_data is None or (datetime.now() - self.btc_trend_updated).total_seconds() < 300:
                return self.btc_trend
            
            # Получение настроек для анализа BTC
            btc_symbol = self.btc_analysis_config.get('symbol', 'BTCUSDT')
            timeframe = self.btc_analysis_config.get('timeframe', '1h')
            
            # Получение данных
            df = market_data.get_candles(btc_symbol, timeframe)
            if df.empty:
                self.logger.warning(f"Нет данных для анализа тренда BTC")
                return self.btc_trend
            
            # Расчет индикаторов
            # 1. Скользящие средние
            ma_fast_period = self.btc_analysis_config.get('ma_fast_period', 20)
            ma_slow_period = self.btc_analysis_config.get('ma_slow_period', 50)
            
            df['ma_fast'] = calculate_ma(df, ma_fast_period, 'close')
            df['ma_slow'] = calculate_ma(df, ma_slow_period, 'close')
            
            # 2. MACD
            macd_fast = self.btc_analysis_config.get('macd_fast', 12)
            macd_slow = self.btc_analysis_config.get('macd_slow', 26)
            macd_signal = self.btc_analysis_config.get('macd_signal', 9)
            
            df['macd'], df['macd_signal'], df['macd_hist'] = calculate_macd(
                df, macd_fast, macd_slow, macd_signal, 'close'
            )
            
            # 3. RSI
            rsi_period = self.btc_analysis_config.get('rsi_period', 14)
            
            df['rsi'] = calculate_rsi(df, rsi_period, 'close')
            
            # Анализ тренда на основе индикаторов
            
            # Последние значения
            last_close = df['close'].iloc[-1]
            last_ma_fast = df['ma_fast'].iloc[-1]
            last_ma_slow = df['ma_slow'].iloc[-1]
            last_macd = df['macd'].iloc[-1]
            last_macd_signal = df['macd_signal'].iloc[-1]
            last_macd_hist = df['macd_hist'].iloc[-1]
            last_rsi = df['rsi'].iloc[-1]
            
            # Предыдущие значения
            prev_macd_hist = df['macd_hist'].iloc[-2]
            
            # Счетчики силы тренда
            bullish_points = 0
            bearish_points = 0
            
            # 1. MA Crossover
            if last_ma_fast > last_ma_slow:
                bullish_points += 2
            elif last_ma_fast < last_ma_slow:
                bearish_points += 2
            
            # 2. Цена относительно MA
            if last_close > last_ma_fast:
                bullish_points += 1
            elif last_close < last_ma_fast:
                bearish_points += 1
            
            if last_close > last_ma_slow:
                bullish_points += 1
            elif last_close < last_ma_slow:
                bearish_points += 1
            
            # 3. MACD
            if last_macd > last_macd_signal:
                bullish_points += 1
            elif last_macd < last_macd_signal:
                bearish_points += 1
            
            if last_macd_hist > 0 and prev_macd_hist < last_macd_hist:
                bullish_points += 1
            elif last_macd_hist < 0 and prev_macd_hist > last_macd_hist:
                bearish_points += 1
            
            # 4. RSI
            if last_rsi > 50:
                bullish_points += 1
            elif last_rsi < 50:
                bearish_points += 1
            
            if last_rsi > 70:
                bullish_points += 1
            elif last_rsi < 30:
                bearish_points += 1
            
            # Определение тренда
            total_points = bullish_points + bearish_points
            if total_points > 0:
                trend_strength = max(bullish_points, bearish_points) / total_points
            else:
                trend_strength = 0
            
            # Обновление информации о тренде
            if bullish_points > bearish_points and trend_strength >= 0.6:
                self.btc_trend = "bullish"
            elif bearish_points > bullish_points and trend_strength >= 0.6:
                self.btc_trend = "bearish"
            else:
                self.btc_trend = "neutral"
            
            self.btc_trend_strength = trend_strength
            self.btc_trend_updated = datetime.now()
            
            self.logger.info(f"Тренд BTC: {self.btc_trend}, сила: {self.btc_trend_strength:.2f}")
            
            # Сохранение результатов анализа в кэш
            if btc_symbol not in self.analysis_cache:
                self.analysis_cache[btc_symbol] = {}
            
            if timeframe not in self.analysis_cache[btc_symbol]:
                self.analysis_cache[btc_symbol][timeframe] = {}
            
            self.analysis_cache[btc_symbol][timeframe]['trend'] = self.btc_trend
            self.analysis_cache[btc_symbol][timeframe]['trend_strength'] = self.btc_trend_strength
            
            # Добавляем базовые индикаторы в кэш
            self.analysis_cache[btc_symbol][timeframe]['ma_fast'] = last_ma_fast
            self.analysis_cache[btc_symbol][timeframe]['ma_slow'] = last_ma_slow
            self.analysis_cache[btc_symbol][timeframe]['macd'] = last_macd
            self.analysis_cache[btc_symbol][timeframe]['macd_signal'] = last_macd_signal
            self.analysis_cache[btc_symbol][timeframe]['macd_hist'] = last_macd_hist
            self.analysis_cache[btc_symbol][timeframe]['rsi'] = last_rsi
            
            return self.btc_trend
        
        except Exception as e:
            self.logger.error(f"Ошибка при анализе тренда BTC: {str(e)}")
            return "neutral"
    
    def _analyze_symbol(self, symbol, market_data):
        """
        Анализ конкретного символа
        
        Args:
            symbol (str): торговая пара
            market_data: объект с рыночными данными
        """
        try:
            # Создаем запись в кэше для символа, если ее нет
            if symbol not in self.analysis_cache:
                self.analysis_cache[symbol] = {}
            
            # Получаем данные для всех таймфреймов и обновляем индикаторы
            for timeframe in market_data.intervals:
                df = market_data.get_candles(symbol, timeframe)
                if df.empty:
                    continue
                
                # Создаем запись для таймфрейма
                if timeframe not in self.analysis_cache[symbol]:
                    self.analysis_cache[symbol][timeframe] = {}
                
                # Рассчитываем индикаторы в соответствии с конфигурацией
                self._calculate_indicators(df, symbol, timeframe)
                
        except Exception as e:
            self.logger.error(f"Ошибка при анализе символа {symbol}: {str(e)}")
    
    def _calculate_indicators(self, df, symbol, timeframe):
        """
        Расчет индикаторов для конкретного символа и таймфрейма
        
        Args:
            df (pandas.DataFrame): DataFrame со свечами
            symbol (str): торговая пара
            timeframe (str): таймфрейм
        """
        try:
            # Получаем настройки индикаторов из конфигурации
            indicators_config = self.analysis_config.get('indicators', {})
            
            # Создаем словарь для хранения результатов
            indicators = {}
            
            # 1. Скользящие средние (MA)
            if 'ma' in indicators_config:
                for ma_config in indicators_config['ma']:
                    period = ma_config.get('period', 20)
                    ma_type = ma_config.get('type', 'simple')
                    source = ma_config.get('source', 'close')
                    
                    if ma_type == 'simple':
                        indicators[f'ma_{period}'] = calculate_ma(df, period, source).iloc[-1]
                    elif ma_type == 'exponential':
                        indicators[f'ema_{period}'] = calculate_ema(df, period, source).iloc[-1]
            
            # 2. MACD
            if 'macd' in indicators_config:
                macd_config = indicators_config['macd']
                fast_period = macd_config.get('fast_period', 12)
                slow_period = macd_config.get('slow_period', 26)
                signal_period = macd_config.get('signal_period', 9)
                source = macd_config.get('source', 'close')
                
                macd, signal, hist = calculate_macd(df, fast_period, slow_period, signal_period, source)
                indicators['macd'] = macd.iloc[-1]
                indicators['macd_signal'] = signal.iloc[-1]
                indicators['macd_hist'] = hist.iloc[-1]
            
            # 3. RSI
            if 'rsi' in indicators_config:
                rsi_config = indicators_config['rsi']
                period = rsi_config.get('period', 14)
                source = rsi_config.get('source', 'close')
                
                indicators['rsi'] = calculate_rsi(df, period, source).iloc[-1]
            
            # 4. Stochastic
            if 'stochastic' in indicators_config:
                stochastic_config = indicators_config['stochastic']
                k_period = stochastic_config.get('k_period', 14)
                d_period = stochastic_config.get('d_period', 3)
                slowing = stochastic_config.get('slowing', 3)
                
                k, d = calculate_stochastic(df, k_period, d_period, slowing)
                indicators['stoch_k'] = k.iloc[-1]
                indicators['stoch_d'] = d.iloc[-1]
            
            # 5. Bollinger Bands
            if 'bollinger_bands' in indicators_config:
                bb_config = indicators_config['bollinger_bands']
                period = bb_config.get('period', 20)
                std_dev = bb_config.get('std_dev', 2)
                source = bb_config.get('source', 'close')
                
                upper, middle, lower = calculate_bollinger_bands(df, period, std_dev, source)
                indicators['bb_upper'] = upper.iloc[-1]
                indicators['bb_middle'] = middle.iloc[-1]
                indicators['bb_lower'] = lower.iloc[-1]
            
            # 6. ATR
            if 'atr' in indicators_config:
                atr_config = indicators_config['atr']
                period = atr_config.get('period', 14)
                
                indicators['atr'] = calculate_atr(df, period).iloc[-1]
            
            # 7. Поддержка и сопротивление
            if 'support_resistance' in indicators_config:
                sr_config = indicators_config['support_resistance']
                window = sr_config.get('window', 10)
                
                support, resistance = calculate_support_resistance(df, window)
                indicators['support'] = support
                indicators['resistance'] = resistance
            
            # 8. Паттерны свечей
            if 'patterns' in indicators_config:
                patterns_config = indicators_config['patterns']
                patterns_list = patterns_config.get('patterns', ['doji', 'hammer', 'engulfing'])
                
                patterns = identify_patterns(df, patterns_list)
                indicators['patterns'] = patterns
            
            # Сохраняем результаты в кэше
            self.analysis_cache[symbol][timeframe].update(indicators)
            
        except Exception as e:
            self.logger.error(f"Ошибка при расчете индикаторов для {symbol} {timeframe}: {str(e)}")
    
    def get_analysis(self, symbol, timeframe):
        """
        Получение результатов анализа для конкретного символа и таймфрейма
        
        Args:
            symbol (str): торговая пара
            timeframe (str): таймфрейм
        
        Returns:
            dict: результаты анализа или пустой словарь, если анализ не найден
        """
        if (symbol in self.analysis_cache and 
            timeframe in self.analysis_cache[symbol]):
            return self.analysis_cache[symbol][timeframe]
        else:
            return {}
    
    def get_signal(self, symbol, timeframe, strategy_name):
        """
        Получение торгового сигнала для конкретной стратегии
        
        Args:
            symbol (str): торговая пара
            timeframe (str): таймфрейм
            strategy_name (str): название стратегии
        
        Returns:
            dict: торговый сигнал или None, если сигнала нет
        """
        # Этот метод будет вызываться из менеджера стратегий
        # Здесь мы просто возвращаем результаты анализа, а логика 
        # формирования сигналов будет в конкретных стратегиях
        return self.get_analysis(symbol, timeframe)