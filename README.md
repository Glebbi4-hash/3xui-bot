# 3x-ui Telegram Bot

Telegram-бот для управления клиентами панели [3x-ui](https://github.com/MHSanaei/3x-ui) через inline-меню.

## Возможности

| Функция | Описание |
|---|---|
| 📋 Инбаунды | Обзор всех инбаундов с суммарным трафиком и количеством клиентов |
| 👥 Список клиентов | Все клиенты инбаунда с трафиком за сессию |
| ➕ Добавить клиента | Создание через диалог (email, трафик, срок) |
| 🟢/🔴 Вкл/Откл | Включение/отключение одной кнопкой |
| 🗑 Удалить | С подтверждением и уведомлением пользователя |
| 🔄 Сбросить трафик | Обнуление счётчика клиента |
| 🔗 Ссылка подключения | Авто-генерация VLESS Reality ссылки |
| 📱 QR-код | QR для быстрого подключения в v2rayNG / Hiddify |
| 🔑 Запрос доступа | Пользователь запрашивает доступ, админ выбирает инбаунд и срок — клиент получает ссылку и QR |
| 🖥 Статистика сервера | CPU, RAM, диск, сеть, аптайм, топ процессов + сводка по панели |
| 📊 Мониторинг | Топ-15 клиентов по трафику за текущую сессию по всем инбаундам |

## Быстрый старт

### 1. Получить токен бота

Напишите [@BotFather](https://t.me/BotFather) → `/newbot` → скопируйте токен.

### 2. Узнать свой Telegram ID

Напишите [@userinfobot](https://t.me/userinfobot) — он пришлёт ваш числовой ID.

### 3. Развернуть на сервере

```bash
git clone https://github.com/Glebbi4-hash/3xui-bot.git /opt/3xui-bot
cd /opt/3xui-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env
```

### 4. Заполнить .env

```env
BOT_TOKEN=1234567890:AAxxxx...
ADMIN_IDS=123456789

PANEL_URL=https://your-domain.com:PORT/WEBPATH
PANEL_USERNAME=admin
PANEL_PASSWORD=yourpassword

DEFAULT_TRAFFIC_GB=0
DEFAULT_EXPIRE_DAYS=30
```

### 5. Запустить через systemd

```bash
cp 3xui-bot.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now 3xui-bot
systemctl status 3xui-bot
journalctl -u 3xui-bot -f
```

## Структура проекта
## Требования к панели

- 3x-ui версии **2.x** и выше (протестировано на 26.x)
- SSL включён, доступ по HTTPS
- Пользователь с правами на создание/удаление клиентов

## Безопасность

- Бот принимает команды **только от ADMIN_IDS** (AdminMiddleware)
- Публичный доступ только к команде `/start` и запросу доступа
- Рекомендуется запускать на том же сервере что и 3x-ui

## Прокси для серверов в РФ

Если сервер в России, Telegram API заблокирован. Добавьте в `.env`:

```env
HTTPS_PROXY=socks5://127.0.0.1:10808
```

И установите `aiohttp-socks`:

```bash
pip install aiohttp-socks
```
