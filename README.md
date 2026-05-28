# 3x-ui Telegram Bot

Telegram-бот для управления клиентами панели [3x-ui](https://github.com/MHSanaei/3x-ui) через inline-меню.

## Возможности

| Функция | Описание |
|---|---|
| 👥 Список клиентов | Все клиенты инбаунда с онлайн-трафиком |
| ➕ Добавить клиента | Создание через FSM-диалог (email, трафик, срок) |
| 🟢/🔴 Вкл/Откл | Включение/отключение одной кнопкой |
| 🗑 Удалить | С подтверждением |
| 🔄 Сбросить трафик | Обнуление счётчика |
| 🔗 Ссылка подключения | Авто-генерация VLESS/VMess ссылки |
| 📋 Инбаунды | Обзор всех инбаундов панели |

## Быстрый старт

### 1. Получить токен бота

Напишите [@BotFather](https://t.me/BotFather) → `/newbot` → скопируйте токен.

### 2. Узнать свой Telegram ID

Напишите [@userinfobot](https://t.me/userinfobot) — он пришлёт ваш числовой ID.

### 3. Развернуть на сервере

```bash
# Клонировать / скопировать файлы
mkdir -p /opt/3xui-bot
cp -r . /opt/3xui-bot/
cd /opt/3xui-bot

# Создать виртуальное окружение
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Настроить конфиг
cp .env.example .env
nano .env
```

### 4. Заполнить .env

```env
BOT_TOKEN=1234567890:AAxxxx...
ADMIN_IDS=123456789          # ваш Telegram ID
PANEL_URL=http://localhost:2053
PANEL_USERNAME=admin
PANEL_PASSWORD=yourpassword
DEFAULT_INBOUND_ID=1         # ID нужного инбаунда
DEFAULT_TRAFFIC_GB=0         # 0 = безлимит
DEFAULT_EXPIRE_DAYS=30
```

### 5. Запустить через systemd

```bash
cp 3xui-bot.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable 3xui-bot
systemctl start 3xui-bot

# Проверить статус
systemctl status 3xui-bot
journalctl -u 3xui-bot -f
```

## Структура проекта

```
3xui-bot/
├── bot.py                  # Точка входа
├── config.py               # Настройки из .env
├── requirements.txt
├── .env.example
├── 3xui-bot.service        # systemd-юнит
├── handlers/
│   ├── start.py            # /start, меню, инбаунды
│   ├── clients.py          # CRUD клиентов + FSM
│   ├── connection.py       # Ссылки подключения
│   └── states.py           # FSM-состояния
├── services/
│   └── xui_client.py       # HTTP-клиент 3x-ui REST API
├── keyboards/
│   └── inline.py           # Все inline-клавиатуры
└── utils/
    └── helpers.py          # Middleware, форматирование
```

## Требования к панели

- 3x-ui версии **2.x** и выше  
- REST API доступен по `PANEL_URL/xui/API/...`  
- Пользователь с правами на создание/удаление клиентов

## Безопасность

- Бот принимает команды **только от ADMIN_IDS** (AdminMiddleware)  
- Никаких публичных команд — весь бот закрыт  
- Рекомендуется запускать на том же сервере без открытия порта 2053 наружу

## Расширение

Хотите добавить больше инбаундов? Измените `DEFAULT_INBOUND_ID` на нужный или добавьте выбор инбаунда через команду `/inbound <id>`.

Хотите уведомления об истечении срока? Добавьте `aiogram_dialog` или `apscheduler` для фоновых задач.
