Bybit Trading Bot
Автоматический торговый бот для криптовалютной биржи Bybit с возможностью настройки различных торговых стратегий.

Возможности
Автоматическая торговля на бирже Bybit на основе настраиваемых стратегий
Поддержка нескольких торговых пар и таймфреймов
Продвинутое управление рисками и капиталом
Трейлинг-стопы для максимизации прибыли
Режим бумажной торговли для тестирования без реальных сделок
Анализ тренда BTC для принятия более точных решений
Блокировка лонг-позиций при нисходящем тренде BTC
Подробное логирование и статистика торговли
Структура проекта
bybit-trading-bot/
├── config/               # Конфигурационные файлы
│   ├── config.yaml       # Основной файл конфигурации
│   └── settings.py       # Утилиты для загрузки конфигурации
├── core/                 # Основные компоненты бота
│   ├── bot.py            # Класс бота
│   ├── market_data.py    # Работа с рыночными данными
│   ├── position_manager.py # Управление позициями
│   └── risk_manager.py   # Управление рисками
├── strategies/           # Торговые стратегии
│   ├── base_strategy.py  # Базовый класс стратегии
│   ├── macd_strategy.py  # Стратегия на основе MACD
│   ├── support_resistance_strategy.py # Стратегия поддержки/сопротивления
│   └── strategy_manager.py # Менеджер стратегий
├── indicators/           # Технические индикаторы
│   └── technical_indicators.py # Расчеты индикаторов
├── utils/                # Вспомогательные функции
│   ├── logger.py         # Настройка логирования
│   └── market_analyzer.py # Анализатор рыночных данных
├── data/                 # Данные рынка
│   └── historical/       # Исторические данные для бэктестинга
├── logs/                 # Логи работы бота
├── main.py               # Основной файл запуска
└── requirements.txt      # Зависимости Python
Установка
Клонировать репозиторий:
bash
git clone https://github.com/yourusername/bybit-trading-bot.git
cd bybit-trading-bot
Создать виртуальное окружение Python и активировать его:
bash
python -m venv venv
# На Windows
venv\Scripts\activate
# На Linux/Mac
source venv/bin/activate
Установить зависимости:
bash
pip install -r requirements.txt
Настроить конфигурационный файл:
bash
cp config/config.yaml.example config/config.yaml
# Отредактировать config.yaml, указав API ключи и настройки
Настройка
Основные настройки производятся в файле config/config.yaml. Необходимо указать:

API ключи для доступа к Bybit (получите их в личном кабинете Bybit):
yaml
api:
  testnet: true  # Использовать тестовую сеть (рекомендуется для начала)
  api_key: "YOUR_API_KEY_HERE"
  api_secret: "YOUR_API_SECRET_HERE"
Торговые пары и таймфреймы:
yaml
trading:
  symbols:
    - "BTCUSDT"
    - "ETHUSDT"
    # Другие пары...
  intervals:
    - "15m"
    - "1h"
    - "4h"
    # Другие таймфреймы...
Настройки риск-менеджмента:
yaml
risk_management:
  max_positions: 5
  max_risk_per_trade: 1.0  # % от баланса
  leverage: 3               # Кредитное плечо
  # Другие параметры...
Параметры стратегий:
yaml
strategies:
  strategies:
    - name: "MACD Strategy"
      class: "MacdStrategy"
      enabled: true
      # Параметры...
Запуск
Режим бумажной торговли (без реальных сделок)
bash
python main.py --paper
Режим бэктестинга (на исторических данных)
bash
python main.py --backtest
Режим реальной торговли
bash
python main.py
Дополнительные параметры
bash
python main.py --config=path/to/config.yaml --debug
Настройка стратегий
Бот поддерживает несколько стратегий торговли. Каждую стратегию можно настроить отдельно в файле конфигурации.

Стратегия MACD
Торговля на основе индикатора MACD с фильтрацией по RSI:

yaml
- name: "MACD Strategy"
  class: "MacdStrategy"
  enabled: true
  symbols:
    - "BTCUSDT"
    - "ETHUSDT"
  timeframes:
    - "15m"
    - "1h"
  params:
    macd_fast: 12
    macd_slow: 26
    macd_signal: 9
    rsi_period: 14
    rsi_overbought: 70
    rsi_oversold: 30
Стратегия поддержки и сопротивления
Торговля на основе уровней поддержки и сопротивления:

yaml
- name: "Support Resistance Strategy"
  class: "SupportResistanceStrategy"
  enabled: true
  symbols:
    - "BTCUSDT"
    - "ETHUSDT"
  timeframes:
    - "1h"
    - "4h"
  params:
    window: 20
    lookback_periods: 100
    rsi_period: 14
    atr_period: 14
    atr_multiplier: 2.0
Настройка анализа BTC
Бот использует анализ тренда BTC для принятия более точных решений. Если BTC находится в нисходящем тренде, то открытие длинных (long) позиций по всем токенам будет заблокировано:

yaml
btc_analysis:
  symbol: "BTCUSDT"
  timeframe: "1h"
  ma_fast_period: 20
  ma_slow_period: 50
  macd_fast: 12
  macd_slow: 26
  macd_signal: 9
  rsi_period: 14
Зависимости
Список основных зависимостей Python:

pybit: API-клиент для Bybit
pandas: Обработка и анализ данных
numpy: Математические вычисления
pyyaml: Работа с YAML-конфигурацией
scipy: Научные вычисления
Полный список зависимостей см. в файле requirements.txt.

Расширение функциональности
Добавление новой стратегии
Создайте новый класс стратегии в папке strategies/, наследующийся от BaseStrategy
Реализуйте методы _initialize(), execute() и analyze()
Добавьте стратегию в конфигурационный файл
Пример шаблона для новой стратегии:

python
from strategies.base_strategy import BaseStrategy

class MyNewStrategy(BaseStrategy):
    def _initialize(self):
        super()._initialize()
        # Инициализация параметров
        
    def execute(self):
        # Логика выполнения стратегии
        
    def analyze(self, symbol, timeframe):
        # Логика анализа и генерации сигналов
        return signal
Добавление нового технического индикатора
Добавьте функцию расчета индикатора в indicators/technical_indicators.py
Используйте индикатор в стратегиях
Советы по безопасности
Начинайте с режима бумажной торговли (--paper)
Используйте testnet: true для тестирования на тестовой сети Bybit
Установите небольшие значения max_risk_per_trade и max_risk_total
Регулярно проверяйте логи на наличие ошибок
Примечания
Этот бот предназначен для образовательных целей
Торговля криптовалютами связана с высоким риском
Используйте на свой страх и риск
Лицензия
MIT

