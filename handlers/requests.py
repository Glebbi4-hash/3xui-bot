import logging
import re
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import Config
from services import XUIClient

logger = logging.getLogger(__name__)
router = Router()


class RequestStates(StatesGroup):
    waiting_name = State()
    waiting_devices = State()


def _xui(config):
    return XUIClient(config.PANEL_URL, config.PANEL_USERNAME, config.PANEL_PASSWORD, getattr(config, "API_TOKEN", ""))


@router.message(CommandStart())
async def cmd_start_user(message: Message, state: FSMContext, config: Config):
    if message.from_user.id in config.ADMIN_IDS:
        from keyboards import main_menu
        await message.answer(
            "👋 <b>3x-ui Manager</b>\n\nВыберите действие:",
            reply_markup=main_menu(),
            parse_mode="HTML",
        )
        return
    builder = InlineKeyboardBuilder()
    builder.button(text="🔑 Запросить доступ", callback_data="user:request")
    builder.button(text="📱 Инструкция", callback_data="user:instructions")
    builder.adjust(1)
    await message.answer(
        "👋 Добро пожаловать!\n\nДля получения доступа к VPN нажмите кнопку ниже.",
        reply_markup=builder.as_markup(),
    )

@router.callback_query(F.data == "user:request")
async def cb_user_request(callback: CallbackQuery, state: FSMContext, config: Config):
    if callback.from_user.id in config.ADMIN_IDS:
        await callback.answer()
        return
    await callback.answer()
    await state.set_state(RequestStates.waiting_name)
    await callback.message.edit_text("✏️ Как вас зовут?\n\n""Введите имя латинскими буквами — так администратор сможет вас идентифицировать.\n""Пример: Ivan, Anna_P, John_Smith")


@router.message(RequestStates.waiting_name)
async def fsm_request_name(message: Message, state: FSMContext, config: Config):
    if message.from_user.id in config.ADMIN_IDS:
        return
    name = message.text.strip()
    if not name:
        await message.answer("Имя не может быть пустым:")
        return
    await state.update_data(name=name)
    await state.set_state(RequestStates.waiting_devices)
    builder = InlineKeyboardBuilder()
    builder.button(text="1 устройство",  callback_data="req:devices_req:1")
    builder.button(text="2 устройства",  callback_data="req:devices_req:2")
    builder.button(text="3 устройства",  callback_data="req:devices_req:3")
    builder.adjust(3)
    await message.answer(
        "Сколько устройств хотите подключить?",
        reply_markup=builder.as_markup(),
    )



@router.callback_query(F.data.startswith("req:devices_req:"))
async def cb_devices_req(callback: CallbackQuery, state: FSMContext, config: Config):
    await callback.answer()
    devices = int(callback.data.split(":")[2])
    data = await state.get_data()
    await state.clear()
    name = data.get("name", "Unknown")
    user = callback.from_user
    username = f"@{user.username}" if user.username else "нет username"
    builder = InlineKeyboardBuilder()
    builder.button(text="Одобрить", callback_data=f"req:approve:{user.id}:{name[:20]}:{devices}")
    builder.button(text="Отклонить", callback_data=f"req:deny:{user.id}")
    builder.adjust(2)
    for admin_id in config.ADMIN_IDS:
        try:
            await callback.bot.send_message(
                admin_id,
                f"Новая заявка на доступ\n\nИмя: {name}\nTG ID: {user.id}\nUsername: {username}\nЗапрошено устройств: {devices}",
                reply_markup=builder.as_markup(),
            )
        except Exception as e:
            logger.error("Failed to notify admin %s: %s", admin_id, e)
    await callback.message.edit_text(
        "Заявка отправлена! Ожидайте подтверждения от администратора."
    )
@router.callback_query(F.data.startswith("req:deny:"))
async def cb_req_deny(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[2])
    try:
        await callback.bot.send_message(user_id, "❌ К сожалению, ваша заявка на доступ отклонена.")
    except Exception:
        pass
    await callback.message.edit_text(
        callback.message.text + "\n\n❌ <b>Отклонено</b>",
        reply_markup=None,
    )
    await callback.answer("Заявка отклонена")


@router.callback_query(F.data.startswith("req:approve:"))
async def cb_req_approve(callback: CallbackQuery, config: Config):
    await callback.answer()
    parts = callback.data.split(":")
    user_id = int(parts[2])
    name = parts[3]
    requested_devices = int(parts[4]) if len(parts) > 4 else 3
    xui = _xui(config)
    await xui.login()
    inbounds = await xui.get_inbounds()
    await xui.close()
    builder = InlineKeyboardBuilder()
    for ib in inbounds:
        if not ib.get("enable"):
            continue
        proto = ib.get("protocol", "?").upper()
        remark = ib.get("remark") or f"#{ib['id']}"
        builder.button(
            text=f"#{ib['id']} {remark} [{proto}]",
            callback_data=f"req:inbound:sub:{user_id}:{name[:20]}:{ib['id']}:{requested_devices}",
        )
    builder.button(text="Отмена", callback_data=f"req:deny:{user_id}")
    builder.adjust(1)
    await callback.message.edit_text(
        callback.message.text + f"\n\nВыберите инбаунд (запрошено устройств: {requested_devices}):",
        reply_markup=builder.as_markup(),
    )

@router.callback_query(F.data.startswith("req:type:sub:"))
async def cb_req_type_sub(callback: CallbackQuery, config: Config):
    await callback.answer()
    parts = callback.data.split(":")
    user_id = int(parts[3])
    name = parts[4]
    builder = InlineKeyboardBuilder()
    builder.button(text="1️⃣",          callback_data=f"req:devices:{user_id}:{name[:20]}:1")
    builder.button(text="2️⃣",          callback_data=f"req:devices:{user_id}:{name[:20]}:2")
    builder.button(text="3️⃣",          callback_data=f"req:devices:{user_id}:{name[:20]}:3")
    builder.button(text="5️⃣",          callback_data=f"req:devices:{user_id}:{name[:20]}:5")
    builder.button(text="∞ Без лимита", callback_data=f"req:devices:{user_id}:{name[:20]}:0")
    builder.button(text="❌ Отмена",    callback_data=f"req:deny:{user_id}")
    builder.adjust(5, 1)
    await callback.message.edit_text(
        callback.message.text + "\n\n📱 <b>Количество устройств:</b>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )

@router.callback_query(F.data.startswith("req:type:acc:"))
async def cb_req_type_acc(callback: CallbackQuery, config: Config):
    await callback.answer()
    parts = callback.data.split(":")
    user_id = int(parts[3])
    name = parts[4]
    xui = _xui(config)
    await xui.login()
    inbounds = await xui.get_inbounds()
    await xui.close()
    builder = InlineKeyboardBuilder()
    for ib in inbounds:
        if not ib.get("enable"):
            continue
        proto = ib.get("protocol", "?").upper()
        remark = ib.get("remark") or f"#{ib['id']}"
        builder.button(
            text=f"#{ib['id']} {remark} [{proto}]",
            callback_data=f"req:inbound:acc:{user_id}:{name[:20]}:{ib['id']}",
        )
    builder.button(text="❌ Отмена", callback_data=f"req:deny:{user_id}")
    builder.adjust(1)
    await callback.message.edit_text(
        callback.message.text + "\n\n🔑 <b>Выберите инбаунд:</b>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )

@router.callback_query(F.data.startswith("req:devices:"))
async def cb_req_devices(callback: CallbackQuery, config: Config):
    await callback.answer()
    parts = callback.data.split(":")
    user_id = int(parts[2])
    name = parts[3]
    limit_ip = int(parts[4])
    xui = _xui(config)
    await xui.login()
    inbounds = await xui.get_inbounds()
    await xui.close()
    builder = InlineKeyboardBuilder()
    for ib in inbounds:
        if not ib.get("enable"):
            continue
        proto = ib.get("protocol", "?").upper()
        remark = ib.get("remark") or f"#{ib['id']}"
        builder.button(
            text=f"#{ib['id']} {remark} [{proto}]",
            callback_data=f"req:inbound:sub:{user_id}:{name[:20]}:{ib['id']}:{limit_ip}",
        )
    builder.button(text="❌ Отмена", callback_data=f"req:deny:{user_id}")
    builder.adjust(1)
    await callback.message.edit_text(
        callback.message.text + "\n\n📋 <b>Выберите инбаунд:</b>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )

@router.callback_query(F.data.startswith("req:inbound:"))
async def cb_req_inbound(callback: CallbackQuery, config: Config):
    await callback.answer()
    parts = callback.data.split(":")
    access_type = parts[2]
    user_id = int(parts[3])
    name = parts[4]
    inbound_id = int(parts[5])
    requested_devices = int(parts[6]) if len(parts) > 6 else 3
    builder = InlineKeyboardBuilder()
    builder.button(text="7 дней",    callback_data=f"req:expire:{access_type}:{user_id}:{name}:{inbound_id}:7:{requested_devices}")
    builder.button(text="30 дней",   callback_data=f"req:expire:{access_type}:{user_id}:{name}:{inbound_id}:30:{requested_devices}")
    builder.button(text="90 дней",   callback_data=f"req:expire:{access_type}:{user_id}:{name}:{inbound_id}:90:{requested_devices}")
    builder.button(text="Бессрочно", callback_data=f"req:expire:{access_type}:{user_id}:{name}:{inbound_id}:0:{requested_devices}")
    builder.adjust(2, 2)
    await callback.message.edit_text(
        callback.message.text + "\n\nВыберите срок доступа:",
        reply_markup=builder.as_markup(),
    )

@router.callback_query(F.data.startswith("req:expire:"))
async def cb_req_expire(callback: CallbackQuery, config: Config):
    await callback.answer()
    parts = callback.data.split(":")
    access_type = parts[2]
    user_id = int(parts[3])
    name = parts[4]
    inbound_id = int(parts[5])
    expire_days = int(parts[6])
    requested_devices = int(parts[7]) if len(parts) > 7 else 3
    builder = InlineKeyboardBuilder()
    builder.button(text=f"1 уст.", callback_data=f"req:create:{user_id}:{name}:{inbound_id}:{expire_days}:1")
    builder.button(text=f"2 уст.", callback_data=f"req:create:{user_id}:{name}:{inbound_id}:{expire_days}:2")
    builder.button(text=f"3 уст.", callback_data=f"req:create:{user_id}:{name}:{inbound_id}:{expire_days}:3")
    builder.button(text=f"5 уст.", callback_data=f"req:create:{user_id}:{name}:{inbound_id}:{expire_days}:5")
    builder.button(text="Без лимита", callback_data=f"req:create:{user_id}:{name}:{inbound_id}:{expire_days}:0")
    builder.adjust(3, 2)
    expire_str = f"{expire_days} дн." if expire_days else "Бессрочно"
    await callback.message.edit_text(
        callback.message.text + f"\n\nСрок: {expire_str}\nКлиент запросил: {requested_devices} уст.\n\nВыберите количество устройств:",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(F.data.startswith("req:create:"))
async def cb_req_create(callback: CallbackQuery, config: Config):
    await callback.answer()
    parts = callback.data.split(":")
    user_id = int(parts[2])
    name = parts[3]
    inbound_id = int(parts[4])
    expire_days = int(parts[5])
    limit_ip = int(parts[6])
    safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    email = f"{safe_name}_{user_id}"
    xui = _xui(config)
    await xui.login()
    client_uuid = await xui.add_client(
        inbound_id, email=email,
        traffic_gb=config.DEFAULT_TRAFFIC_GB,
        expire_days=expire_days,
        tg_id=user_id,
        limit_ip=limit_ip,
    )
    await xui.close()
    if not client_uuid:
        await callback.message.edit_text(
            callback.message.text + "\n\nОшибка создания клиента",
            reply_markup=None,
        )
        return
    expire_str = f"{expire_days} дн." if expire_days else "Бессрочно"
    limit_str = f"{limit_ip} устройства" if limit_ip else "Без лимита"
    xui2 = _xui(config)
    await xui2.login()
    clients = await xui2.get_clients(inbound_id)
    await xui2.close()
    client = next((c for c in clients if c.get("id") == client_uuid), {})
    sub_id = client.get("subId", "")
    sub_link = f"{config.SUB_URL}{sub_id}" if sub_id and config.SUB_URL else None
    if sub_link:
        import qrcode, io
        from aiogram.types import BufferedInputFile
        qr = qrcode.QRCode(box_size=10, border=2)
        qr.add_data(sub_link)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        try:
            await callback.bot.send_photo(
                user_id,
                photo=BufferedInputFile(buf.read(), filename="sub_qr.png"),
                caption=(
                    f"✅ Доступ одобрен!\n\n"
                    f"⏳ Срок: {expire_str}\n"
                    f"📱 По данной подписке вы можете подключить {limit_str}\n\n"
                    f"📋 Ссылка подписки:\n{sub_link}\n\n"
                    f"Как добавить в Happ:\n"
                    f"Нажмите + → Импорт из буфера обмена\n"
                    f"или отсканируйте QR-код"
                ),
            )
        except Exception as e:
            logger.error("Failed to send to user %s: %s", user_id, e)
    await callback.message.edit_text(
        callback.message.text + f"\n\n✅ Одобрено\n📧 {email}\n⏳ {expire_str}\n📱 {limit_str}",
        reply_markup=None,
    )

@router.callback_query(F.data == "user:instructions")
async def cb_instructions(callback: CallbackQuery):
    await callback.answer()
    builder = InlineKeyboardBuilder()
    builder.button(text="🤖 Android", callback_data="instr:android")
    builder.button(text="🍎 iOS",     callback_data="instr:ios")
    builder.adjust(2)
    await callback.message.edit_text(
        "📱 <b>Инструкция по установке Happ</b>\n\nВыберите вашу платформу:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "instr:android")
async def cb_instr_android(callback: CallbackQuery):
    await callback.answer()
    builder = InlineKeyboardBuilder()
    builder.button(text="⬇️ Скачать Happ для Android",
                   url="https://play.google.com/store/apps/details?id=com.happproxy")
    builder.button(text="◀️ Назад", callback_data="user:instructions")
    builder.adjust(1)
    text = (
        "🤖 <b>Установка Happ на Android</b>\n\n"
        "<b>Шаг 1.</b> Скачайте Happ из Google Play\n\n"
        "<b>Шаг 2.</b> Запросите доступ в боте\n"
        "Нажмите 🔑 <b>Запросить доступ</b>\n\n"
        "<b>Шаг 3.</b> После одобрения получите ссылку и QR\n\n"
        "<b>Шаг 4.</b> Откройте Happ → нажмите <b>+</b>\n\n"
        "<b>Шаг 5.</b> Выберите <b>Импорт из буфера обмена</b>\n"
        "или <b>Сканировать QR-код</b>\n\n"
        "<b>Шаг 6.</b> Вставьте ссылку → <b>Сохранить</b>\n\n"
        "<b>Шаг 7.</b> Нажмите <b>Подключить</b> ✅\n\n"
        "⚠️ Разрешите приложению создать VPN-соединение."
    )
    await callback.message.edit_text(
        text, reply_markup=builder.as_markup(), parse_mode="HTML"
    )


@router.callback_query(F.data == "instr:ios")
async def cb_instr_ios(callback: CallbackQuery):
    await callback.answer()
    builder = InlineKeyboardBuilder()
    builder.button(text="⬇️ Скачать Happ для iOS",
                   url="https://apps.apple.com/us/app/happ-proxy-utility/id6504287215")
    builder.button(text="◀️ Назад", callback_data="user:instructions")
    builder.adjust(1)
    text = (
        "🍎 <b>Установка Happ на iPhone / iPad</b>\n\n"
        "<b>Шаг 1.</b> Скачайте Happ из App Store\n\n"
        "<b>Шаг 2.</b> Запросите доступ в боте\n"
        "Нажмите 🔑 <b>Запросить доступ</b>\n\n"
        "<b>Шаг 3.</b> После одобрения получите ссылку и QR\n\n"
        "<b>Шаг 4.</b> Откройте Happ → нажмите <b>+</b>\n\n"
        "<b>Шаг 5.</b> Выберите <b>Импорт из буфера обмена</b>\n"
        "или <b>Сканировать QR-код</b>\n\n"
        "<b>Шаг 6.</b> Вставьте ссылку → <b>Сохранить</b>\n\n"
        "<b>Шаг 7.</b> Нажмите <b>Подключить</b> ✅\n\n"
        "⚠️ Разрешите приложению добавить VPN-конфигурацию."
    )
    await callback.message.edit_text(
        text, reply_markup=builder.as_markup(), parse_mode="HTML"
    )
