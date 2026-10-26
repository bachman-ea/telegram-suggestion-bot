<div align="center">

# 📬 Telegram Suggestion Bot (Предложка для канала)

Асинхронный Telegram-бот предложки для каналов с модерацией в закрытой группе, отложенной публикацией и поддержкой медиагрупп.

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![aiogram](https://img.shields.io/badge/aiogram-3.x-2CA5E0?style=flat&logo=telegram&logoColor=white)](https://github.com/aiogram/aiogram)
[![APScheduler](https://img.shields.io/badge/APScheduler-3.11+-orange?style=flat)](https://github.com/agronholm/apscheduler)
[![SQLite](https://img.shields.io/badge/SQLite-WAL_Mode-003B57?style=flat&logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)

</div>

---

## 📋 Оглавление

- [Возможности](#-возможности)
- [Архитектура проекта](#-архитектура-проекта)
- [Быстрый старт](#-быстрый-старт)
  - [Локальный запуск](#1-локальный-запуск)
  - [Запуск через Docker Compose](#2-запуск-через-docker-compose)
  - [Настройка Systemd (Linux VPS)](#3-настройка-systemd-сервиса-linux-vps)
- [Конфигурация (.env)](#-конфигурация-env)
- [Команды администраторов](#-команды-администраторов)

---

## ✨ Возможности

- **Обязательная подписка на канал:** бот автоматически проверяет статус членства пользователя перед приемом материалов.
- **Поддержка любых форматов контента:** текст, одиночные фото, видео, GIF, аудио, документы, голосовые сообщения.
- **Работа с коллажами (альбомами):** на базе `MediaGroupMiddleware` альбом из 2–10 фото/видео буферизируется и отправляется цельным постом.
- **Модерация в админ-чате:** карточка с интерактивными кнопками («Принять», «Отклонить», «Отклонить и заблокировать»).
- **Гибкое планирование публикаций:**
  - Немедленная публикация
  - Через 30 минут
  - Через 1 час
  - Произвольное время по МСК (`ЧЧ:ММ`, `ДД.ММ ЧЧ:ММ`, `ДД.ММ.ГГГГ ЧЧ:ММ`)
- **Управление очередью (/scheduled):** перенос времени публикации и отмена запланированных постов в один клик.
- **Система блокировок (/banned):** бан спамеров с фиксацией причины, модератора и даты, а также возможность быстрой разблокировки.
- **Динамический статус в ЛС автора:** бот обновляет одно исходное сообщение вместо спама новыми уведомлениями.
- **Публикация от лица канала:** в конце поста автоматически проставляется автор (`От: @username` или кликабельная ссылка).
- **Отказоустойчивость:** задачи сохраняются в SQLite (WAL mode) и восстанавливаются при перезапуске.

---

## 📂 Архитектура проекта

```
├── .github/workflows/
│   └── lint.yml          # Автоматический CI-тест синтаксиса
├── handlers/
│   ├── admin.py          # Модерация, блокировки, расписание, очередь
│   └── user.py           # Проверка подписки, приём постов и альбомов
├── middlewares/
│   └── media_group.py    # Буферизация и сборка альбомов Telegram
├── utils/
│   ├── notifications.py  # Обновление статуса в ЛС автора
│   ├── subscription.py   # Проверка подписки и генерация ссылок
│   └── time_parser.py    # Парсинг времени МСК и подписи автора
├── config.py             # Строгая валидация окружения (.env)
├── database.py           # Потокобезопасная SQLite БД (WAL mode)
├── docker-compose.yml    # Готовый сценарий запуска в Docker
├── Dockerfile            # Контейнеризация проекта
├── filters.py            # Фильтр доступа к админ-группе
├── keyboards.py          # Инлайн-клавиатуры
├── main.py               # Инициализация, диспетчер и polling
├── scheduler.py          # Публикация в канал и планировщик
├── requirements.txt      # Зависимости Python
└── .env.example          # Пример файла настроек
```

---

## 🚀 Быстрый старт

### 1. Локальный запуск

1. Склонируйте репозиторий:
   ```bash
   git clone https://github.com/your-username/telegram-suggestion-bot.git
   cd telegram-suggestion-bot
   ```

2. Создайте и активируйте виртуальное окружение:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/macOS
   # .venv\Scripts\activate   # Windows PowerShell
   ```

3. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```

4. Скопируйте `.env.example` в `.env` и заполните параметры:
   ```bash
   cp .env.example .env
   ```

5. Запустите бота:
   ```bash
   python main.py
   ```

---

### 2. Запуск через Docker Compose

```bash
docker compose up -d --build
```

Просмотр логов:
```bash
docker compose logs -f
```

---

### 3. Настройка Systemd сервиса (Linux VPS)

Создайте файл `/etc/systemd/system/tg-suggestion-bot.service`:

```ini
[Unit]
Description=Telegram Suggestion Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/path/to/telegram-suggestion-bot
ExecStart=/path/to/telegram-suggestion-bot/.venv/bin/python main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Активация и запуск:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now tg-suggestion-bot
```

---

## ⚙️ Конфигурация (.env)

| Переменная | Описание | Пример |
|---|---|---|
| `BOT_TOKEN` | Токен бота от [@BotFather](https://t.me/BotFather) | `123456789:ABCdefGhI...` |
| `ADMIN_CHAT_ID` | ID группы администраторов для модерации | `-1001234567890` |
| `CHANNEL_ID` | ID или @username канала для публикаций | `@my_channel` или `-1009876543210` |
| `TIMEZONE` | Часовой пояс (по умолчанию Московское время) | `Europe/Moscow` |
| `DB_PATH` | Путь к файлу базы данных SQLite | `bot.db` |

> [!IMPORTANT]
> Бот должен быть назначен **Администратором** канала с правом публикации сообщений, а также добавлен в группу модераторов.

---

## 🛠 Команды администраторов

Команды работают **только** в чате группы администраторов (`ADMIN_CHAT_ID`):

- `/help` — список доступных команд модератора.
- `/scheduled` (или `/queue`) — очередь запланированных постов с возможностью изменения времени и отмены.
- `/banned` (или `/banlist`) — список заблокированных пользователей с кнопками мгновенной разблокировки.
- `/unban <user_id>` — снятие блокировки по ID пользователя.
- `/stats` — сводная статистика постов и блокировок.
