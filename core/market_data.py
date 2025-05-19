# -*- coding: utf-8 -*-

"""
Класс для работы с рыночными данными
"""

import os
import time
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import threading

class MarketData:
    """Класс для сбора и хранения рыночных данных"""
    
    def __init__(self, api_client, ws_client, symbols, intervals, logger):
        """
        Инициализация объекта для работы с рыночными данными
        
        Args:
            api_client: HTTP-клиент API Bybit
            ws_client: WebSocket-клиент Bybit
            symbols (list): список торговых пар
            intervals (list): список временных интервалов для свечей
            logger: объект логгера
        """
        self.api_client = api_client
        self.ws_client = ws_client
        self.symbols = symbols
        self.intervals = intervals
        self.logger = logger
        
        # Словарь для хранения данных свечей в формате:
        # {symbol: {interval: DataFrame}}
        self.candles = {}
        
        # Словарь для хранения книги ордеров:
        # {symbol: DataFrame}
        self.orderbooks = {}
        
        # Словарь для хранения тикеров:
        # {symbol: dict}
        self.tickers = {}
        
        # Блокировки для безопасного обновления данных
        self.candles_lock = threading.RLock()
        self.orderbooks_lock = threading.RLock()
        self.tickers_lock = threading.RLock()
        
        # Подготовка хранилища данных
        self._initialize_data_storage()
    
    def _initialize_data_storage(self):
        """Инициализация хранилища данных"""
        # Создаем папку для данных, если её нет
        if not os.path.exists('data'):
            os.makedirs('data')
        
        # Инициализация структур данных для каждого символа и интервала
        for symbol in self.symbols:
            self.candles[symbol] = {}
            self.orderbooks[symbol] = pd.DataFrame()
            self.tickers[symbol] = {}
            
            for interval in self.intervals:
                self.candles[symbol][interval] = pd.DataFrame()
    
    def start(self):
        """Запуск сбора рыночных данных"""
        self.logger.info("Запуск сбора рыночных данных")
        
        # Получение исторических данных для всех символов и интервалов
        self._load_initial_data()
        
        # Настройка WebSocket для получения обновлений в реальном времени
        self._setup_websocket_feeds()
    
    def _load_initial_data(self):
        """Загрузка начальных исторических данных"""
        for symbol in self.symbols:
            self.logger.info(f"Загрузка исторических данных для {symbol}")
            
            for interval in self.intervals:
                try:
                    # Получение исторических данных свечей
                    klines = self._get_historical_klines(symbol, interval)
                    
                    with self.candles_lock:
                        self.candles[symbol][interval] = klines
                        
                    self.logger.info(f"Загружено {len(klines)} свечей для {symbol} ({interval})")
                except Exception as e:
                    self.logger.error(f"Ошибка при загрузке исторических данных для {symbol} ({interval}): {str(e)}")
    
    def _get_historical_klines(self, symbol, interval, limit=1000):
        """
        Получение исторических свечей
        
        Args:
            symbol (str): торговая пара
            interval (str): интервал свечей
            limit (int): количество свечей
            
        Returns:
            pandas.DataFrame: DataFrame со свечами
        """
        try:
            # Получаем данные через API
            response = self.api_client.get_kline(
                category="linear",
                symbol=symbol,
                interval=interval,
                limit=limit
            )
            
            # Проверка на ошибки в ответе
            if response['retCode'] != 0:
                self.logger.error(f"API error: {response['retMsg']}")
                return pd.DataFrame()
            
            # Преобразование данных в DataFrame
            data = response['result']['list']
            if not data:
                return pd.DataFrame()
            
            # В Bybit API данные возвращаются в обратном порядке (новые в начале)
            data.reverse()
            
            df = pd.DataFrame(data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'
            ])
            
            # Преобразование типов данных
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            for col in ['open', 'high', 'low', 'close', 'volume', 'turnover']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Установка timestamp в качестве индекса
            df.set_index('timestamp', inplace=True)
            
            return df
        
        except Exception as e:
            self.logger.error(f"Ошибка при получении исторических данных: {str(e)}")
            return pd.DataFrame()
    
    def _setup_websocket_feeds(self):
        """Настройка WebSocket для получения обновлений в реальном времени"""
        try:
            # Подписка на свечи для всех символов и интервалов
            for symbol in self.symbols:
                for interval in self.intervals:
                    self.ws_client.kline_stream(
                        interval=interval,
                        symbol=symbol,
                        callback=self._handle_kline_update
                    )
                    self.logger.debug(f"Подписка на свечи {symbol} ({interval})")
                
                # Подписка на книгу ордеров
                self.ws_client.orderbook_stream(
                    depth=50,
                    symbol=symbol,
                    callback=self._handle_orderbook_update
                )
                self.logger.debug(f"Подписка на книгу ордеров {symbol}")
                
                # Подписка на тикеры
                self.ws_client.ticker_stream(
                    symbol=symbol,
                    callback=self._handle_ticker_update
                )
                self.logger.debug(f"Подписка на тикеры {symbol}")
                
            self.logger.info("WebSocket подписки настроены")
        
        except Exception as e:
            self.logger.error(f"Ошибка при настройке WebSocket: {str(e)}")
    
    def _handle_kline_update(self, message):
        """
        Обработчик обновлений свечей
        
        Args:
            message (dict): сообщение WebSocket
        """
        try:
            data = message.get('data', {})
            if not data:
                return
            
            symbol = data.get('symbol')
            interval = data.get('interval')
            
            if not symbol or not interval:
                return
            
            # Преобразование данных
            kline_data = {
                'timestamp': pd.to_datetime(data['timestamp'], unit='ms'),
                'open': float(data['open']),
                'high': float(data['high']),
                'low': float(data['low']),
                'close': float(data['close']),
                'volume': float(data['volume']),
                'turnover': float(data['turnover'])
            }
            
            new_row = pd.DataFrame([kline_data]).set_index('timestamp')
            
            with self.candles_lock:
                # Проверяем, существует ли свеча с таким временем
                if kline_data['timestamp'] in self.candles[symbol][interval].index:
                    # Обновляем существующую свечу
                    self.candles[symbol][interval].loc[kline_data['timestamp']] = new_row.loc[kline_data['timestamp']]
                else:
                    # Добавляем новую свечу
                    self.candles[symbol][interval] = pd.concat([self.candles[symbol][interval], new_row])
                    # Сортируем по времени
                    self.candles[symbol][interval].sort_index(inplace=True)
                    # Ограничиваем максимальное количество свечей
                    max_candles = 1000
                    if len(self.candles[symbol][interval]) > max_candles:
                        self.candles[symbol][interval] = self.candles[symbol][interval].iloc[-max_candles:]
            
        except Exception as e:
            self.logger.error(f"Ошибка при обработке обновления свечи: {str(e)}")
    
    def _handle_orderbook_update(self, message):
        """
        Обработчик обновлений книги ордеров
        
        Args:
            message (dict): сообщение WebSocket
        """
        try:
            data = message.get('data', {})
            if not data:
                return
            
            symbol = data.get('s')
            
            if not symbol:
                return
            
            # Получаем данные
            timestamp = pd.to_datetime(data.get('ts', int(time.time() * 1000)), unit='ms')
            bids = data.get('b', [])  # [[price, quantity], ...]
            asks = data.get('a', [])  # [[price, quantity], ...]
            
            # Преобразование в DataFrame
            bids_df = pd.DataFrame(bids, columns=['price', 'quantity'])
            asks_df = pd.DataFrame(asks, columns=['price', 'quantity'])
            
            # Преобразование типов
            bids_df['price'] = pd.to_numeric(bids_df['price'])
            bids_df['quantity'] = pd.to_numeric(bids_df['quantity'])
            asks_df['price'] = pd.to_numeric(asks_df['price'])
            asks_df['quantity'] = pd.to_numeric(asks_df['quantity'])
            
            # Добавление метки типа
            bids_df['type'] = 'bid'
            asks_df['type'] = 'ask'
            
            # Объединение
            orderbook = pd.concat([bids_df, asks_df])
            orderbook['timestamp'] = timestamp
            
            with self.orderbooks_lock:
                self.orderbooks[symbol] = orderbook
            
        except Exception as e:
            self.logger.error(f"Ошибка при обработке обновления книги ордеров: {str(e)}")
    
    def _handle_ticker_update(self, message):
        """
        Обработчик обновлений тикеров
        
        Args:
            message (dict): сообщение WebSocket
        """
        try:
            data = message.get('data', {})
            if not data:
                return
            
            symbol = data.get('symbol')
            
            if not symbol:
                return
            
            # Обновляем данные тикера
            with self.tickers_lock:
                self.tickers[symbol] = {
                    'last_price': float(data.get('lastPrice', 0)),
                    'high_price_24h': float(data.get('highPrice24h', 0)),
                    'low_price_24h': float(data.get('lowPrice24h', 0)),
                    'price_24h_pcnt': float(data.get('price24hPcnt', 0)),
                    'volume_24h': float(data.get('volume24h', 0)),
                    'timestamp': pd.to_datetime(data.get('timestamp', int(time.time() * 1000)), unit='ms')
                }
            
        except Exception as e:
            self.logger.error(f"Ошибка при обработке обновления тикера: {str(e)}")
    
    def get_candles(self, symbol, interval, lookback=None):
        """
        Получение свечей для заданного символа и интервала
        
        Args:
            symbol (str): торговая пара
            interval (str): интервал свечей
            lookback (int, optional): количество свечей для возврата
        
        Returns:
            pandas.DataFrame: DataFrame со свечами
        """
        with self.candles_lock:
            if symbol not in self.candles or interval not in self.candles[symbol]:
                return pd.DataFrame()
            
            df = self.candles[symbol][interval].copy()
            
            if lookback and len(df) > lookback:
                return df.iloc[-lookback:]
            
            return df
    
    def get_ticker(self, symbol):
        """
        Получение текущего тикера для символа
        
        Args:
            symbol (str): торговая пара
        
        Returns:
            dict: данные тикера
        """
        with self.tickers_lock:
            return self.tickers.get(symbol, {})
    
    def get_orderbook(self, symbol):
        """
        Получение текущей книги ордеров для символа
        
        Args:
            symbol (str): торговая пара
        
        Returns:
            pandas.DataFrame: книга ордеров
        """
        with self.orderbooks_lock:
            return self.orderbooks.get(symbol, pd.DataFrame())
    
    def load_historical_data(self):
        """Загрузка исторических данных для бэктестинга"""
        # Путь к папке с историческими данными
        data_dir = 'data/historical'
        
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
            self.logger.warning(f"Папка {data_dir} не существует. Создана новая папка.")
            self.logger.warning("Исторические данные отсутствуют. Загрузите их вручную.")
            return
        
        for symbol in self.symbols:
            for interval in self.intervals:
                file_path = f"{data_dir}/{symbol}_{interval}.csv"
                
                if not os.path.exists(file_path):
                    self.logger.warning(f"Файл с историческими данными не найден: {file_path}")
                    continue
                
                try:
                    df = pd.read_csv(file_path)
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    df.set_index('timestamp', inplace=True)
                    
                    # Преобразование типов данных
                    for col in ['open', 'high', 'low', 'close', 'volume', 'turnover']:
                        if col in df.columns:
                            df[col] = pd.to_numeric(df[col], errors='coerce')
                    
                    with self.candles_lock:
                        self.candles[symbol][interval] = df
                        
                    self.logger.info(f"Загружено {len(df)} исторических свечей для {symbol} ({interval})")
                
                except Exception as e:
                    self.logger.error(f"Ошибка при загрузке исторических данных из {file_path}: {str(e)}")
    
    def save_candles_to_csv(self, symbol, interval):
        """
        Сохранение свечей в CSV-файл
        
        Args:
            symbol (str): торговая пара
            interval (str): интервал свечей
        """
        with self.candles_lock:
            if symbol not in self.candles or interval not in self.candles[symbol]:
                return
            
            df = self.candles[symbol][interval]
            if df.empty:
                return
            
            # Создаем папку для данных, если её нет
            if not os.path.exists('data'):
                os.makedirs('data')
            
            # Сохраняем данные в файл
            file_path = f"data/{symbol}_{interval}.csv"
            df.to_csv(file_path)
            self.logger.info(f"Сохранено {len(df)} свечей для {symbol} ({interval}) в {file_path}")
    
    def save_all_candles(self):
        """Сохранение всех свечей в CSV-файлы"""
        for symbol in self.symbols:
            for interval in self.intervals:
                self.save_candles_to_csv(symbol, interval)