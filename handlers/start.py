import logging
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery

from config import Config
from keyboards import main_menu, inbounds_menu, inbound_actions
from services import XUIClient
from utils import AdminMiddleware

logger = logging.getLogger(__name__)
router = Router()


def _xui(config: Config) -> XUIClient:
    return XUIClient(config.PANEL_URL, config.PANEL_USERNAME, config.PANEL_PASSWORD, getattr(config, "API_TOKEN", ""))


# ------------------------------------------------------------------ #
#  /start  &  main menu                                               #
# ------------------------------------------------------------------ #

@router.message(CommandStart())
async def cmd_start(message: Message, config: Config):
    if message.from_user.id not in config.ADMIN_IDS:
        return
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Инбаунды"), KeyboardButton(text="🖥 Статистика")],
            [KeyboardButton(text="📊 Мониторинг"), KeyboardButton(text="📁 Бэкап")],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )
    await message.answer(
        "👋 <b>3x-ui Manager</b>\n\nВыберите действие:",
        reply_markup=kb,
        parse_mode="HTML",
    )
@router.callback_query(F.data == "menu:main")
async def cb_main_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "👋 <b>3x-ui Manager</b>\n\nВыберите действие:",
        reply_markup=main_menu(),
        parse_mode="HTML",
    )
    await callback.answer()


# ------------------------------------------------------------------ #
#  Inbounds list                                                       #
# ------------------------------------------------------------------ #

@router.callback_query(F.data == "inbounds:list")
async def cb_inbounds_list(callback: CallbackQuery, config: Config):
    await callback.answer()
    xui = _xui(config)
    await xui.login()
    inbounds = await xui.get_inbounds()
    await xui.close()

    if not inbounds:
        await callback.message.edit_text(
            "📭 Инбаунды не найдены. Создайте их в панели 3x-ui.",
            reply_markup=main_menu(),
        )
        return

    lines = []
    for ib in inbounds:
        icon  = "🟢" if ib.get("enable") else "🔴"
        proto = ib.get("protocol", "?").upper()
        port  = ib.get("port", "?")
        remark = ib.get("remark") or f"Inbound #{ib['id']}"
        clients_count = len(ib.get("clientStats") or [])
        lines.append(f"{icon} <b>#{ib['id']}</b> {remark} [{proto}:{port}] — {clients_count} кл.")

    await callback.message.edit_text(
        "📋 <b>Инбаунды панели:</b>\n\n" + "\n".join(lines),
        reply_markup=inbounds_menu(inbounds),
        parse_mode="HTML",
    )


# ------------------------------------------------------------------ #
#  Open single inbound                                                 #
# ------------------------------------------------------------------ #

@router.callback_query(F.data.startswith("inbound:open:"))
async def cb_inbound_open(callback: CallbackQuery, config: Config):
    await callback.answer()
    inbound_id = int(callback.data.split(":")[2])

    xui = _xui(config)
    await xui.login()
    inbounds = await xui.get_inbounds()
    await xui.close()
    inbound = next((i for i in inbounds if i["id"] == inbound_id), None)

    if not inbound:
        await callback.answer("Инбаунд не найден", show_alert=True)
        return

    icon   = "🟢" if inbound.get("enable") else "🔴"
    proto  = inbound.get("protocol", "?").upper()
    port   = inbound.get("port", "?")
    remark = inbound.get("remark") or f"Inbound #{inbound_id}"
    

    stats  = inbound.get("clientStats") or []

    up_total   = sum(s.get("up", 0)   for s in stats)
    down_total = sum(s.get("down", 0) for s in stats)
    from utils import format_bytes
    text = (
        f"{icon} <b>{remark}</b>\n\n"
        f"🔌 Протокол: <code>{proto}</code>  Порт: <code>{port}</code>\n"
        f"👥 Клиентов: {len(stats)}\n"
        f"⬆️ Отправлено (всего): {format_bytes(up_total)}\n"
        f"⬇️ Получено (всего): {format_bytes(down_total)}"
    )
    await callback.message.edit_text(
        text,
        reply_markup=inbound_actions(inbound_id, remark),
        parse_mode="HTML",
    )


@router.message(F.text == "📋 Инбаунды")
async def reply_inbounds(message: Message, config: Config):
    xui = _xui(config)
    await xui.login()
    inbounds = await xui.get_inbounds()
    await xui.close()
    if not inbounds:
        await message.answer("Инбаунды не найдены.")
        return
    from keyboards import inbounds_menu
    lines = []
    for ib in inbounds:
        icon = "🟢" if ib.get("enable") else "🔴"
        proto = ib.get("protocol", "?").upper()
        remark = ib.get("remark") or f"#{ib['id']}"
        clients_count = len(ib.get("clientStats") or [])
        lines.append(f"{icon} <b>#{ib['id']}</b> {remark} [{proto}:{ib.get('port')}] — {clients_count} кл.")
    await message.answer(
        "📋 <b>Инбаунды панели:</b>\n\n" + "\n".join(lines),
        reply_markup=inbounds_menu(inbounds),
        parse_mode="HTML",
    )


@router.message(F.text == "🖥 Статистика")
async def reply_stats(message: Message, config: Config):
    await message.answer("Собираю статистику...")
    from handlers.server_stats import _collect_system_stats, _collect_panel_stats, _build_message
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    import asyncio
    sys_stats, panel_stats = await asyncio.gather(
        _collect_system_stats(),
        _collect_panel_stats(config),
    )
    text = _build_message(sys_stats, panel_stats)
    builder = InlineKeyboardBuilder()
    builder.button(text="Обновить", callback_data="server:stats")
    await message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())


@router.message(F.text == "📊 Мониторинг")
async def reply_monitoring(message: Message, config: Config):
    await message.answer("Загружаю мониторинг...")
    xui = _xui(config)
    await xui.login()
    inbounds = await xui.get_inbounds()
    await xui.close()
    from utils import format_bytes
    all_clients = []
    for ib in inbounds:
        remark = ib.get("remark") or f"#{ib['id']}"
        for s in (ib.get("clientStats") or []):
            up = s.get("up", 0)
            down = s.get("down", 0)
            if up + down == 0:
                continue
            all_clients.append({"email": s.get("email","?"), "inbound": remark,
                "up": up, "down": down, "total": up+down, "enable": s.get("enable", True)})
    all_clients.sort(key=lambda x: x["total"], reverse=True)
    top = all_clients[:15]
    if not top:
        await message.answer("Нет активных клиентов.")
        return
    lines = ["Топ клиентов по трафику\n"]
    for i, c in enumerate(top, 1):
        icon = "🟢" if c["enable"] else "🔴"
        lines.append(f"{i}. {icon} {c['email']} [{c['inbound']}]\n"
                     f"   {format_bytes(c['up'])} / {format_bytes(c['down'])}")
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="Обновить", callback_data="monitor:traffic")
    await message.answer("\n".join(lines), parse_mode="HTML", reply_markup=builder.as_markup())


@router.message(F.text == "📁 Бэкап")
async def reply_backup(message: Message, config: Config):
    await message.answer("Создаю бэкап...")
    import os, shutil
    from aiogram.types import FSInputFile
    backup_path = "/tmp/3xui-backup.db"
    db_path = "/etc/x-ui/x-ui.db"
    try:
        shutil.copy2(db_path, backup_path)
        doc = FSInputFile(backup_path, filename="x-ui-backup.db")
        await message.answer_document(
            document=doc,
            caption="Бэкап базы данных 3x-ui",
        )
        os.remove(backup_path)
    except Exception as e:
        await message.answer(f"Ошибка создания бэкапа: {e}")


@router.callback_query(F.data == "backup:create")
async def cb_backup(callback: CallbackQuery, config: Config):
    await callback.answer()
    await callback.message.answer("Создаю бэкап...")
    import shutil, os
    from aiogram.types import FSInputFile
    db_path = "/etc/x-ui/x-ui.db"
    backup_path = "/tmp/x-ui-backup.db"
    try:
        shutil.copy2(db_path, backup_path)
        doc = FSInputFile(backup_path, filename="x-ui-backup.db")
        await callback.message.answer_document(
            document=doc,
            caption="Бэкап базы данных 3x-ui",
        )
        os.remove(backup_path)
    except Exception as e:
        await callback.message.answer(f"Ошибка: {e}")


@router.message(F.document)
async def cb_restore_backup(message: Message, config: Config):
    if message.from_user.id not in config.ADMIN_IDS:
        return
    doc = message.document
    if not doc.file_name.endswith('.db'):
        await message.answer("Отправьте файл с расширением .db")
        return
    await message.answer("Восстанавливаю бэкап...")
    import shutil, os
    from aiogram.types import FSInputFile
    db_path = "/etc/x-ui/x-ui.db"
    backup_path = "/tmp/restore.db"
    try:
        # Download file
        file = await message.bot.get_file(doc.file_id)
        await message.bot.download_file(file.file_path, backup_path)
        # Backup current db
        shutil.copy2(db_path, f"{db_path}.bak")
        # Replace db
        shutil.copy2(backup_path, db_path)
        os.remove(backup_path)
        await message.answer(
            "Бэкап восстановлен!\n\n"
            "x-ui перезапускается. Подождите 10-15 секунд и проверьте панель."
        )
        # Restart x-ui after sending message
        import asyncio
        await asyncio.sleep(1)
        os.system("systemctl restart x-ui")
    except Exception as e:
        await message.answer(f"Ошибка восстановления: {e}")


@router.callback_query(F.data == "backup:menu")
async def cb_backup_menu(callback: CallbackQuery):
    await callback.answer()
    from keyboards.inline import backup_menu
    await callback.message.edit_text(
        "📁 <b>Бэкап</b>\n\nВыберите действие:",
        reply_markup=backup_menu(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "backup:restore")
async def cb_backup_restore(callback: CallbackQuery):
    await callback.answer()
    from keyboards import back_button
    await callback.message.edit_text(
        "♻️ <b>Восстановление бэкапа</b>\n\n"
        "Отправьте файл <code>x-ui-backup.db</code> в этот чат.\n\n"
        "⚠️ Текущая база данных будет заменена!",
        reply_markup=back_button("backup:menu", "◀️ Назад"),
        parse_mode="HTML",
    )


@router.message(F.text == "/preview_client")
async def cmd_preview_client(message: Message, config: Config):
    if message.from_user.id not in config.ADMIN_IDS:
        return
    text = (
        "Шаг 1. Клиент пишет /start:\n"
        "Кнопки: Запросить доступ / Инструкция\n\n"
        "Шаг 2. Нажимает Запросить доступ:\n"
        "Вводит имя латиницей (пример: Ivan_P)\n\n"
        "Шаг 3. Выбирает количество устройств:\n"
        "1 / 2 / 3 устройства\n\n"
        "Шаг 4. Клиент получает:\n"
        "Заявка отправлена! Ожидайте подтверждения.\n\n"
        "Админ получает:\n"
        "Новая заявка\n"
        "Имя: Ivan  TG ID: 123456789\n"
        "Запрошено устройств: 2\n"
        "Кнопки: Одобрить / Отклонить\n\n"
        "При одобрении админ выбирает:\n"
        "1. Инбаунд\n"
        "2. Срок (7/30/90 дней / Бессрочно)\n"
        "3. Количество устройств (1/2/3/5 / Без лимита)\n\n"
        "Клиент получает:\n"
        "Доступ одобрен!\n"
        "Срок: 30 дн.\n"
        "По данной подписке вы можете подключить 2 устройства\n"
        "Ссылка подписки + QR-код"
    )
    await message.answer(text)


@router.callback_query(F.data == "restart:menu")
async def cb_restart_menu(callback: CallbackQuery):
    await callback.answer()
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="⚡ Перезапустить Xray",  callback_data="restart:xray")
    builder.button(text="🔄 Перезапустить панель", callback_data="restart:panel")
    builder.button(text="◀️ Назад",               callback_data="menu:main")
    builder.adjust(1)
    await callback.message.edit_text(
        "🔄 <b>Перезапуск</b>\n\nВыберите действие:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "restart:xray")
async def cb_restart_xray(callback: CallbackQuery, config: Config):
    await callback.answer()
    xui = _xui(config)
    await xui.login()
    result = await xui._request("POST", "/panel/api/server/restartXrayService")
    await xui.close()
    if result and result.get("success"):
        await callback.message.edit_text(
            "✅ Xray успешно перезапущен!",
            reply_markup=None,
        )
    else:
        await callback.message.edit_text(
            "❌ Ошибка перезапуска Xray",
            reply_markup=None,
        )


@router.callback_query(F.data == "restart:panel")
async def cb_restart_panel(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        "🔄 Панель перезапускается...\n\nПодождите 10-15 секунд.",
        reply_markup=None,
    )
    import os
    os.system("systemctl restart x-ui")
