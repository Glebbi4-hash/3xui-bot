# 3x-ui Telegram Bot

Telegram-бот для управления клиентами панели [3x-ui](https://github.com/MHSanaei/3x-ui).

## Совместимость

| Версия 3x-ui | Статус |
|---|---|
| 2.x | Поддерживается |
| 3.x (3.6.0+) | Поддерживается (Bearer token) |

## Возможности

### Для администратора

| Функция | Описание |
|---|---|
| 📋 Инбаунды | Обзор всех инбаундов с трафиком и клиентами |
| 👥 Список клиентов | Клиенты инбаунда с трафиком за сессию |
| ➕ Добавить клиента | Тип (Подписка/Доступ), email, трафик, устройства, срок |
| 🟢/🔴 Вкл/Откл | Включение/отключение одной кнопкой |
| 🗑 Удалить | С подтверждением и уведомлением пользователя |
| 🔄 Сбросить трафик | Обнуление счётчика клиента |
| 📋 Подписка | Ссылка подписки для клиента |
| 📱 QR подписки | QR-код подписки |
| 🔗 Ссылка | VLESS Reality ссылка со всеми параметрами |
| 📱 QR ссылки | QR-код VLESS ссылки |
| 🔑 Одобрение заявок | Выбор инбаунда, срока и устройств |
| 🖥 Статистика сервера | CPU, RAM, диск, сеть, аптайм |
| 📊 Мониторинг | Топ-15 клиентов по трафику |
| 📁 Бэкап | Создание и восстановление базы данных |
| 🔄 Перезапуск | Перезапуск Xray или панели |

### Для пользователя

| Функция | Описание |
|---|---|
| 🔑 Запросить доступ | Имя + количество устройств (1/2/3) |
| 📱 Инструкция | Установка Happ для Android и iOS |

## Клиентский flow

1. /start → Запросить доступ / Инструкция
2. Вводит имя латиницей
3. Выбирает устройств: 1 / 2 / 3
4. Получает: Заявка отправлена!

Админ одобряет → выбирает инбаунд, срок, устройства → клиент получает подписку + QR.

## Быстрый старт

### 1. Получить токен бота

Напишите @BotFather /newbot и скопируйте токен.

### 2. Узнать свой Telegram ID

Напишите @userinfobot — он пришлёт ваш числовой ID.

### 3. Развернуть на сервере

```bash
git clone https://github.com/Glebbi4-hash/3xui-bot.git /opt/3xui-bot
cd /opt/3xui-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env && nano .env
```

### 4. Получить API токен для 3x-ui v3.x

1. Зайдите в панель 3x-ui
2. Перейдите в Settings - Security - API Token
3. Нажмите New Token и скопируйте значение

### 5. Заполнить .env

```
BOT_TOKEN=1234567890:AAxxxx...
ADMIN_IDS=123456789

PANEL_URL=https://your-domain.com:PORT/WEBPATH
PANEL_USERNAME=admin
PANEL_PASSWORD=yourpassword
API_TOKEN=ваш_api_токен
SUB_URL=https://your-domain.com:SUB_PORT/SUB_PATH/

DEFAULT_TRAFFIC_GB=0
DEFAULT_EXPIRE_DAYS=30
```

### 6. Запустить через systemd

```bash
cp 3xui-bot.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now 3xui-bot
systemctl status 3xui-bot
journalctl -u 3xui-bot -f
```

## Структура проекта

```
3xui-bot/
├── bot.py
├── config.py
├── requirements.txt
├── .env.example
├── 3xui-bot.service
├── handlers/
│   ├── start.py
│   ├── clients.py
│   ├── server_stats.py
│   ├── monitoring.py
│   ├── requests.py
│   └── states.py
├── services/
│   └── xui_client.py
├── keyboards/
│   └── inline.py
└── utils/
    └── helpers.py
```

## Требования к панели

- 3x-ui версии 2.x или 3.x (протестировано на 3.6.0)
- SSL включён, доступ по HTTPS
- Для v3.x: API токен из Settings - Security - API Token
- Подписки включены в Settings - Subscription

## Безопасность

- Бот принимает команды только от ADMIN_IDS
- Публичный доступ только к /start и запросу доступа
- Рекомендуется запускать на том же сервере что и 3x-ui

## Прокси для серверов в РФ

Если сервер в России, добавьте в .env:

```
HTTPS_PROXY=socks5://127.0.0.1:10808
```

Установите aiohttp-socks и настройте mixed-инбаунд в 3x-ui на порту 10808.
