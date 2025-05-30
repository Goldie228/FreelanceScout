# 🚀 Freelance Projects Tracker Bot

Бот для отслеживания новых проектов на фриланс-платформах с фильтрацией по ключевым словам. Получайте уведомления в Telegram о свежих проектах с Kwork.ru, FL.ru и Freelancer.com.

## ✨ Основные возможности

- 🔔 Уведомления о новых проектах в реальном времени
- ⚙️ Гибкая настройка отслеживаемых платформ
- 🔍 Фильтрация проектов по ключевым словам
- 👤 Персонализированные настройки для каждого пользователя
- 🛠️ Административные функции управления ботом

## ⚙️ Технологический стек

- **Язык программирования:** Python 3.13
- **Базы данных:**
  - PostgreSQL (основное хранилище)
  - Redis (управление процессами парсеров)

## 📦 Структура проекта
```
src
├── config
│   ├── initializers
│   │   ├── __init__.py
│   │   ├── __pycache__
│   │   │   ├── __init__.cpython-313.pyc
│   │   │   └── redis.cpython-313.pyc
│   │   └── redis.py
│   ├── __init__.py
│   └── __pycache__
│       └── __init__.cpython-313.pyc
├── db
│   ├── database.py
│   ├── __init__.py
│   ├── __pycache__
│   │   ├── database.cpython-313.pyc
│   │   └── __init__.cpython-313.pyc
│   ├── schema.sql
│   └── seeds.sql
├── __init__.py
├── notifications
│   ├── __init__.py
│   ├── notification_service.py
│   └── __pycache__
│       ├── __init__.cpython-313.pyc
│       └── notification_service.cpython-313.pyc
├── parsers
│   ├── application_parser.py
│   ├── fl_parser.py
│   ├── freelancer_parser.py
│   ├── __init__.py
│   ├── kwork_parser.py
│   └── __pycache__
│       ├── application_parser.cpython-313.pyc
│       ├── fl_parser.cpython-313.pyc
│       ├── freelancer_parser.cpython-313.pyc
│       ├── __init__.cpython-313.pyc
│       └── kwork_parser.cpython-313.pyc
└── __pycache__
    └── __init__.cpython-313.pyc
```

##🌟 Особенности реализации
1. Многопоточная архитектура:
  - Основной бот работает в главном потоке
  - Парсеры запускаются в отдельных процессах
  - Уведомления обрабатываются асинхронно

2. Гибкая система фильтрации:
  - Ключевые слова настраиваются для каждого пользователя
  - Возможность включения/отключения платформ
  - Поддержка сложных запросов с несколькими ключевыми словами

3. Административный контроль:
  - Команда /shutdown для безопасной остановки
  - Логирование всех действий
  - Ограниченный доступ к управлению
