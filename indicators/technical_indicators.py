# -*- coding: utf-8 -*-

"""
Технические индикаторы для анализа рынка
"""

import pandas as pd
import numpy as np
from scipy.signal import argrelextrema

def calculate_ma(df, period, source_column='close'):
    """
    Расчет простой скользящей средней (Simple Moving Average)
    
    Args:
        df (pandas.DataFrame): DataFrame со свечами
        period (int): период скользящей средней
        source_column (str): колонка-источник данных
    
    Returns:
        pandas.Series: значения MA
    """
    return df[source_column].rolling(window=period).mean()

def calculate_ema(df, period, source_column='close'):
    """
    Расчет экспоненциальной скользящей средней (Exponential Moving Average)
    
    Args:
        df (pandas.DataFrame): DataFrame со свечами
        period (int): период скользящей средней
        source_column (str): колонка-источник данных
    
    Returns:
        pandas.Series: значения EMA
    """
    return df[source_column].ewm(span=period, adjust=False).mean()

def calculate_macd(df, fast_period=12, slow_period=26, signal_period=9, source_column='close'):
    """
    Расчет MACD (Moving Average Convergence Divergence)
    
    Args:
        df (pandas.DataFrame): DataFrame со свечами
        fast_period (int): период быстрой EMA
        slow_period (int): период медленной EMA
        signal_period (int): период сигнальной линии
        source_column (str): колонка-источник данных
    
    Returns:
        tuple: (MACD, Signal, Histogram)
    """
    ema_fast = calculate_ema(df, fast_period, source_column)
    ema_slow = calculate_ema(df, slow_period, source_column)
    
    macd = ema_fast - ema_slow
    signal = macd.ewm(span=signal_period, adjust=False).mean()
    histogram = macd - signal
    
    return macd, signal, histogram

def calculate_rsi(df, period=14, source_column='close'):
    """
    Расчет RSI (Relative Strength Index)
    
    Args:
        df (pandas.DataFrame): DataFrame со свечами
        period (int): период RSI
        source_column (str): колонка-источник данных
    
    Returns:
        pandas.Series: значения RSI
    """
    delta = df[source_column].diff()
    
    up = delta.copy()
    up[up < 0] = 0
    
    down = -delta.copy()
    down[down < 0] = 0
    
    avg_gain = up.rolling(window=period).mean()
    avg_loss = down.rolling(window=period).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi

def calculate_stochastic(df, k_period=14, d_period=3, slowing=3):
    """
    Расчет Stochastic Oscillator
    
    Args:
        df (pandas.DataFrame): DataFrame со свечами
        k_period (int): период %K
        d_period (int): период %D
        slowing (int): период сглаживания
    
    Returns:
        tuple: (%K, %D)
    """
    low_min = df['low'].rolling(window=k_period).min()
    high_max = df['high'].rolling(window=k_period).max()
    
    k = 100 * ((df['close'] - low_min) / (high_max - low_min))
    k = k.rolling(window=slowing).mean()
    d = k.rolling(window=d_period).mean()
    
    return k, d

def calculate_bollinger_bands(df, period=20, std_dev=2, source_column='close'):
    """
    Расчет Bollinger Bands
    
    Args:
        df (pandas.DataFrame): DataFrame со свечами
        period (int): период скользящей средней
        std_dev (float): множитель стандартного отклонения
        source_column (str): колонка-источник данных
    
    Returns:
        tuple: (Upper Band, Middle Band, Lower Band)
    """
    middle = calculate_ma(df, period, source_column)
    std = df[source_column].rolling(window=period).std()
    
    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)
    
    return upper, middle, lower

def calculate_atr(df, period=14):
    """
    Расчет ATR (Average True Range)
    
    Args:
        df (pandas.DataFrame): DataFrame со свечами
        period (int): период ATR
    
    Returns:
        pandas.Series: значения ATR
    """
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    
    atr = true_range.rolling(window=period).mean()
    
    return atr

def calculate_support_resistance(df, window=10):
    """
    Расчет уровней поддержки и сопротивления
    
    Args:
        df (pandas.DataFrame): DataFrame со свечами
        window (int): размер окна для поиска экстремумов
    
    Returns:
        tuple: (Поддержка, Сопротивление)
    """
    # Находим локальные минимумы и максимумы
    local_min_idx = argrelextrema(df['low'].values, np.less, order=window)[0]
    local_max_idx = argrelextrema(df['high'].values, np.greater, order=window)[0]
    
    # Получаем значения цен на этих точках
    local_min = df['low'].iloc[local_min_idx]
    local_max = df['high'].iloc[local_max_idx]
    
    # Используем недавние уровни
    if len(local_min) > 0:
        support = local_min.iloc[-1]
    else:
        support = df['low'].min()
    
    if len(local_max) > 0:
        resistance = local_max.iloc[-1]
    else:
        resistance = df['high'].max()
    
    return support, resistance

def identify_patterns(df, patterns_list=None):
    """
    Идентификация свечных паттернов
    
    Args:
        df (pandas.DataFrame): DataFrame со свечами
        patterns_list (list, optional): список паттернов для поиска
    
    Returns:
        dict: найденные паттерны
    """
    if patterns_list is None:
        patterns_list = ['doji', 'hammer', 'engulfing', 'harami', 'morningstar', 'eveningstar']
    
    patterns = {}
    
    # Минимальное количество свечей для анализа паттернов
    if len(df) < 3:
        return patterns
    
    # Получаем последние свечи
    candles = df.iloc[-3:]
    
    # Проверяем каждый паттерн
    for pattern in patterns_list:
        if pattern == 'doji':
            # Doji: тело свечи очень маленькое
            last_candle = df.iloc[-1]
            body_size = abs(last_candle['open'] - last_candle['close'])
            candle_range = last_candle['high'] - last_candle['low']
            
            if candle_range > 0 and body_size / candle_range < 0.1:
                patterns['doji'] = True
        
        elif pattern == 'hammer':
            # Hammer: длинная нижняя тень, маленькое тело вверху
            last_candle = df.iloc[-1]
            body_size = abs(last_candle['open'] - last_candle['close'])
            candle_range = last_candle['high'] - last_candle['low']
            lower_shadow = min(last_candle['open'], last_candle['close']) - last_candle['low']
            upper_shadow = last_candle['high'] - max(last_candle['open'], last_candle['close'])
            
            if (candle_range > 0 and 
                body_size / candle_range < 0.3 and 
                lower_shadow / candle_range > 0.6 and 
                upper_shadow / candle_range < 0.1):
                patterns['hammer'] = True
        
        elif pattern == 'engulfing':
            # Engulfing: текущая свеча полностью поглощает предыдущую
            curr_candle = df.iloc[-1]
            prev_candle = df.iloc[-2]
            
            # Бычье поглощение
            if (curr_candle['close'] > curr_candle['open'] and  # текущая - зеленая
                prev_candle['close'] < prev_candle['open'] and  # предыдущая - красная
                curr_candle['close'] > prev_candle['open'] and  # текущая закрылась выше открытия предыдущей
                curr_candle['open'] < prev_candle['close']):    # текущая открылась ниже закрытия предыдущей
                patterns['bullish_engulfing'] = True
            
            # Медвежье поглощение
            if (curr_candle['close'] < curr_candle['open'] and  # текущая - красная
                prev_candle['close'] > prev_candle['open'] and  # предыдущая - зеленая
                curr_candle['close'] < prev_candle['open'] and  # текущая закрылась ниже открытия предыдущей
                curr_candle['open'] > prev_candle['close']):    # текущая открылась выше закрытия предыдущей
                patterns['bearish_engulfing'] = True
        
        elif pattern == 'harami':
            # Harami: текущая свеча полностью внутри предыдущей
            curr_candle = df.iloc[-1]
            prev_candle = df.iloc[-2]
            
            # Бычий харами
            if (curr_candle['close'] > curr_candle['open'] and  # текущая - зеленая
                prev_candle['close'] < prev_candle['open'] and  # предыдущая - красная
                curr_candle['high'] < prev_candle['open'] and   # верх текущей ниже открытия предыдущей
                curr_candle['low'] > prev_candle['close']):     # низ текущей выше закрытия предыдущей
                patterns['bullish_harami'] = True
            
            # Медвежий харами
            if (curr_candle['close'] < curr_candle['open'] and  # текущая - красная
                prev_candle['close'] > prev_candle['open'] and  # предыдущая - зеленая
                curr_candle['high'] < prev_candle['close'] and  # верх текущей ниже закрытия предыдущей
                curr_candle['low'] > prev_candle['open']):      # низ текущей выше открытия предыдущей
                patterns['bearish_harami'] = True
        
        elif pattern == 'morningstar':
            # Morning Star: нисходящая свеча, затем маленькая свеча, затем восходящая свеча
            if len(df) >= 3:
                first_candle = df.iloc[-3]
                second_candle = df.iloc[-2]
                third_candle = df.iloc[-1]
                
                first_body_size = abs(first_candle['open'] - first_candle['close'])
                second_body_size = abs(second_candle['open'] - second_candle['close'])
                third_body_size = abs(third_candle['open'] - third_candle['close'])
                
                if (first_candle['close'] < first_candle['open'] and    # первая - красная
                    third_candle['close'] > third_candle['open'] and    # третья - зеленая
                    second_body_size < first_body_size * 0.3 and       # вторая - маленькая
                    second_body_size < third_body_size * 0.3 and
                    third_candle['close'] > (first_candle['open'] + first_candle['close']) / 2):  # третья закрылась выше середины первой
                    patterns['morningstar'] = True
        
        elif pattern == 'eveningstar':
            # Evening Star: восходящая свеча, затем маленькая свеча, затем нисходящая свеча
            if len(df) >= 3:
                first_candle = df.iloc[-3]
                second_candle = df.iloc[-2]
                third_candle = df.iloc[-1]
                
                first_body_size = abs(first_candle['open'] - first_candle['close'])
                second_body_size = abs(second_candle['open'] - second_candle['close'])
                third_body_size = abs(third_candle['open'] - third_candle['close'])
                
                if (first_candle['close'] > first_candle['open'] and    # первая - зеленая
                    third_candle['close'] < third_candle['open'] and    # третья - красная
                    second_body_size < first_body_size * 0.3 and       # вторая - маленькая
                    second_body_size < third_body_size * 0.3 and
                    third_candle['close'] < (first_candle['open'] + first_candle['close']) / 2):  # третья закрылась ниже середины первой
                    patterns['eveningstar'] = True
    
    return patterns

def calculate_volume_indicators(df, period=20):
    """
    Расчет индикаторов объема
    
    Args:
        df (pandas.DataFrame): DataFrame со свечами
        period (int): период для расчета
    
    Returns:
        tuple: (Volume MA, Volume OBV)
    """
    # Скользящая средняя объема
    volume_ma = df['volume'].rolling(window=period).mean()
    
    # On-Balance Volume (OBV)
    obv = pd.Series(0, index=df.index)
    for i in range(1, len(df)):
        if df['close'].iloc[i] > df['close'].iloc[i-1]:
            obv.iloc[i] = obv.iloc[i-1] + df['volume'].iloc[i]
        elif df['close'].iloc[i] < df['close'].iloc[i-1]:
            obv.iloc[i] = obv.iloc[i-1] - df['volume'].iloc[i]
        else:
            obv.iloc[i] = obv.iloc[i-1]
    
    return volume_ma, obv

def calculate_ichimoku(df, tenkan_period=9, kijun_period=26, senkou_period=52, displacement=26):
    """
    Расчет Ichimoku Cloud
    
    Args:
        df (pandas.DataFrame): DataFrame со свечами
        tenkan_period (int): период для Tenkan-sen
        kijun_period (int): период для Kijun-sen
        senkou_period (int): период для Senkou Span B
        displacement (int): период смещения (Chikou Span)
    
    Returns:
        tuple: (Tenkan-sen, Kijun-sen, Senkou Span A, Senkou Span B, Chikou Span)
    """
    # Tenkan-sen (Conversion Line)
    tenkan_high = df['high'].rolling(window=tenkan_period).max()
    tenkan_low = df['low'].rolling(window=tenkan_period).min()
    tenkan_sen = (tenkan_high + tenkan_low) / 2
    
    # Kijun-sen (Base Line)
    kijun_high = df['high'].rolling(window=kijun_period).max()
    kijun_low = df['low'].rolling(window=kijun_period).min()
    kijun_sen = (kijun_high + kijun_low) / 2
    
    # Senkou Span A (Leading Span A)
    senkou_span_a = ((tenkan_sen + kijun_sen) / 2).shift(displacement)
    
    # Senkou Span B (Leading Span B)
    senkou_high = df['high'].rolling(window=senkou_period).max()
    senkou_low = df['low'].rolling(window=senkou_period).min()
    senkou_span_b = ((senkou_high + senkou_low) / 2).shift(displacement)
    
    # Chikou Span (Lagging Span)
    chikou_span = df['close'].shift(-displacement)
    
    return tenkan_sen, kijun_sen, senkou_span_a, senkou_span_b, chikou_span