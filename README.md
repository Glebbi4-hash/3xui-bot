# 3x-ui Telegram Bot

Telegram-бот для управления клиентами панели [3x-ui](https://github.com/MHSanaei/3x-ui) через inline-меню.

## Совместимость

| Версия 3x-ui | Статус |
|---|---|
| 2.x | Поддерживается |
| 3.x (3.6.0+) | Поддерживается (Bearer token) |

## Возможности

### Для администратора

| Функция | Описание |
|---|---|
| 📋 Инбаунды | Обзор всех инбаундов с суммарным трафиком и количеством клиентов |
| 👥 Список клиентов | Все клиенты инбаунда с трафиком за сессию |
| ➕ Добавить клиента | Выбор типа (Подписка/Доступ), email, трафик, устройства, срок |
| 🟢/🔴 Вкл/Откл | Включение/отключение одной кнопкой |
| 🗑 Удалить | С подтверждением и уведомлением пользователя в Telegram |
| 🔄 Сбросить трафик | Обнуление счётчика клиента |
| 📋 Подписка | Ссылка подписки для клиента |
| 📱 QR подписки | QR-код подписки для быстрого импорта |
| 🔗 Ссылка | Авто-генерация VLESS Reality ссылки со всеми параметрами |
| 📱 QR ссылки | QR-код VLESS ссылки |
| 🔑 Одобрение заявок | Выбор инбаунда, срока и устройств при одобрении |
| 🖥 Статистика сервера | CPU, RAM, диск, сеть, аптайм, топ процессов |
| 📊 Мониторинг | Топ-15 клиентов по трафику за текущую сессию |
| 📁 Бэкап | Создание и восстановление базы данных 3x-ui |
| 🔄 Перезапуск | Перезапуск Xray или панели 3x-ui |

### Для пользователя

| Функция | Описание |
|---|---|
| 🔑 Запросить доступ | Вводит имя и выбирает количество устройств (1/2/3) |
| 📱 Инструкция | Пошаговая инструкция по установке Happ для Android и iOS |

## Клиентский flow

1. Клиент пишет /start → кнопки Запросить доступ / Инструкция
2. Нажимает Запросить доступ → вводит имя латиницей
3. Выбирает количество устройств (1 / 2 / 3)
4. Получает: Заявка отправлена!

Админ получает уведомление с именем, TG ID и количеством устройств.
При одобрении выбирает инбаунд, срок и количество устройств.
Клиент получает ссылку подписки + QR-код.

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
2. Перейдите в Settings - Security - API Token
3. Нажмите New Token
4. Скопируйте токен и вставьте в .env

### 5. Заполнить .env

BOT_TOKEN=1234567890:AAxxxx...
ADMIN_IDS=123456789

PANEL_URL=https://your-domain.com:PORT/WEBPATH
PANEL_USERNAME=admin
PANEL_PASSWORD=yourpassword
API_TOKEN=ваш_api_токен_из_панели
SUB_URL=https://your-domain.com:SUB_PORT/SUB_PATH/
DEFAULT_TRAFFIC_GB=0
DEFAULT_EXPIRE_DAYS=30

### 6. Запустить через systemd

cp 3xui-bot.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now 3xui-bot
systemctl status 3xui-bot
journalctl -u 3xui-bot -f

## Структура проекта

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

Если сервер в России добавьте в .env:

HTTPS_PROXY=socks5://127.0.0.1:10808

Установите aiohttp-socks и настройте mixed-инбаунд в 3x-ui на порту 10808.
