# 3x-ui Telegram Bot

Telegram-бот для управления клиентами панели [3x-ui](https://github.com/MHSanaei/3x-ui) через inline-меню.

## Совместимость

| Версия 3x-ui | Статус |
|---|---|
| 2.x | ✅ Поддерживается |
| 3.x (3.6.0+) | ✅ Поддерживается (Bearer token) |

## Возможности

### Для администратора

| Функция | Описание |
|---|---|
| 📋 Инбаунды | Обзор всех инбаундов с суммарным трафиком и количеством клиентов |
| 👥 Список клиентов | Все клиенты инбаунда с трафиком за сессию |
| ➕ Добавить клиента | Создание через диалог (email, трафик, срок) |
| 🟢/🔴 Вкл/Откл | Включение/отключение одной кнопкой |
| 🗑 Удалить | С подтверждением и уведомлением пользователя в Telegram |
| 🔄 Сбросить трафик | Обнуление счётчика клиента |
| 🔗 Ссылка подключения | Авто-генерация VLESS Reality ссылки со всеми параметрами |
| 📱 QR-код | QR для быстрого подключения в Happ / v2rayNG |
| 🔑 Одобрение заявок | Выбор инбаунда и срока (7/30/90 дней или бессрочно) |
| 🖥 Статистика сервера | CPU, RAM, диск, сеть, аптайм, топ процессов |
| 📊 Мониторинг | Топ-15 клиентов по трафику за текущую сессию |

### Для пользователя

| Функция | Описание |
|---|---|
| 🔑 Запросить доступ | Заявка на подключение — админ одобряет и выбирает срок |
| 📱 Инструкция | Пошаговая инструкция по установке Happ для Android и iOS |

## Быстрый старт

### 1. Получить токен бота

Напишите @BotFather /newbot и скопируйте токен.

### 2. Узнать свой Telegram ID

Напишите @userinfobot — он пришлёт ваш числовой ID.

### 3. Развернуть на сервере

git clone https://github.com/Glebbi4-hash/3xui-bot.git /opt/3xui-bot
cd /opt/3xui-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env

### 4. Получить API токен для 3x-ui v3.x

1. Зайдите в панель 3x-ui
2. Перейдите в Settings - API Tokens
3. Нажмите Create Token
4. Скопируйте токен и вставьте в .env

### 5. Заполнить .env

BOT_TOKEN=1234567890:AAxxxx...
ADMIN_IDS=123456789

PANEL_URL=https://your-domain.com:PORT/WEBPATH
PANEL_USERNAME=admin
PANEL_PASSWORD=yourpassword
API_TOKEN=ваш_api_токен_из_панели

DEFAULT_TRAFFIC_GB=0
DEFAULT_EXPIRE_DAYS=30

### 6. Запустить через systemd

cp 3xui-bot.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now 3xui-bot
systemctl status 3xui-bot
journalctl -u 3xui-bot -f

## Структура проекта

```
3xui-bot/
├── bot.py                   # Точка входа
├── config.py                # Настройки из .env
├── requirements.txt
├── .env.example
├── 3xui-bot.service         # systemd-юнит
├── handlers/
│   ├── start.py             # /start, меню, инбаунды
│   ├── clients.py           # CRUD клиентов + FSM
│   ├── connection.py        # Ссылки подключения
│   ├── server_stats.py      # Статистика сервера
│   ├── monitoring.py        # Мониторинг трафика
│   ├── requests.py          # Запросы доступа + инструкции
│   └── states.py            # FSM-состояния
├── services/
│   └── xui_client.py        # HTTP-клиент 3x-ui REST API
├── keyboards/
│   └── inline.py            # Все inline-клавиатуры
└── utils/
    └── helpers.py           # Middleware, форматирование
```

## Требования к панели

- 3x-ui версии 2.x или 3.x (протестировано на 2.x и 3.6.0)
- SSL включён, доступ по HTTPS
- Для v3.x: API токен из Settings - API Tokens

## Безопасность

- Бот принимает команды только от ADMIN_IDS (AdminMiddleware)
- Публичный доступ только к /start, запросу доступа и инструкции
- Рекомендуется запускать на том же сервере что и 3x-ui

## Прокси для серверов в РФ

Если сервер в России, Telegram API заблокирован. Добавьте в .env:

HTTPS_PROXY=socks5://127.0.0.1:10808

Установите aiohttp-socks:

pip install aiohttp-socks

Настройте mixed-инбаунд в 3x-ui на порту 10808 с routing через зарубежный аутбаунд.
