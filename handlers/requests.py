import logging
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import Config
from services import XUIClient
from utils import AdminMiddleware

logger = logging.getLogger(__name__)
router = Router()
# No AdminMiddleware here — this router is for all users

class RequestStates(StatesGroup):
    waiting_name = State()


def _xui(config):
    return XUIClient(config.PANEL_URL, config.PANEL_USERNAME, config.PANEL_PASSWORD)


@router.message(CommandStart())
async def cmd_start_user(message: Message, state: FSMContext, config: Config):
    # If admin — skip, handled by start.py
    if message.from_user.id in config.ADMIN_IDS:
        return

    builder = InlineKeyboardBuilder()
    builder.button(text="🔑 Запросить доступ", callback_data="user:request")
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
    await callback.message.edit_text(
        "✏️ Введите ваше имя (как к вам обращаться):"
    )

@router.message(RequestStates.waiting_name)
async def fsm_request_name(message: Message, state: FSMContext, config: Config):
    if message.from_user.id in config.ADMIN_IDS:
        return
    name = message.text.strip()
    if not name:
        await message.answer("❌ Имя не может быть пустым:")
        return
    await state.clear()

    user = message.from_user
    username = f"@{user.username}" if user.username else "нет username"

    # Notify all admins
    bot = message.bot
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Одобрить", callback_data=f"req:approve:{user.id}:{name[:20]}")
    builder.button(text="❌ Отклонить", callback_data=f"req:deny:{user.id}")
    builder.adjust(2)

    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"🔔 <b>Новая заявка на доступ</b>\n\n"
                f"👤 Имя: <b>{name}</b>\n"
                f"🆔 TG ID: <code>{user.id}</code>\n"
                f"📎 Username: {username}\n"
                f"👁 Полное имя: {user.full_name}",
                reply_markup=builder.as_markup(),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error("Failed to notify admin %s: %s", admin_id, e)

    await message.answer(
        "✅ Заявка отправлена! Ожидайте подтверждения от администратора."
    )

@router.callback_query(F.data.startswith("req:deny:"))
async def cb_req_deny(callback: CallbackQuery):
    if not await _check_admin(callback):
        return
    user_id = int(callback.data.split(":")[2])
    try:
        await callback.bot.send_message(
            user_id,
            "❌ К сожалению, ваша заявка на доступ отклонена."
        )
    except Exception:
        pass
    await callback.message.edit_text(
        callback.message.text + "\n\n❌ <b>Отклонено</b>",
        parse_mode="HTML",
        reply_markup=None,
    )
    await callback.answer("Заявка отклонена")


async def _check_admin(callback: CallbackQuery) -> bool:
    from config import Config
    # Check via bot data
    if hasattr(callback, '_bot_config'):
        return callback.from_user.id in callback._bot_config.ADMIN_IDS
    return True  # fallback — middleware handles it

@router.callback_query(F.data.startswith("req:approve:"))
async def cb_req_approve(callback: CallbackQuery, config: Config):
    await callback.answer()
    parts = callback.data.split(":")
    user_id = int(parts[2])
    name = parts[3]

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
            callback_data=f"req:inbound:{user_id}:{name[:20]}:{ib['id']}",
        )
    builder.button(text="❌ Отмена", callback_data=f"req:deny:{user_id}")
    builder.adjust(1)

    await callback.message.edit_text(
        callback.message.text + "\n\n✅ <b>Выберите инбаунд:</b>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )

@router.callback_query(F.data.startswith("req:inbound:"))
async def cb_req_inbound(callback: CallbackQuery, config: Config):
    await callback.answer()
    parts = callback.data.split(":")
    user_id = int(parts[2])
    name = parts[3]
    inbound_id = int(parts[4])

    import re
    safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    email = f"{safe_name}_{user_id}"

    xui = _xui(config)
    await xui.login()
    client_uuid = await xui.add_client(
        inbound_id, email=email,
        traffic_gb=config.DEFAULT_TRAFFIC_GB,
        expire_days=config.DEFAULT_EXPIRE_DAYS,
    )
    link = await xui.get_client_link(inbound_id, client_uuid) if client_uuid else None
    await xui.close()

    if not client_uuid:
        await callback.message.edit_text(
            callback.message.text + "\n\n❌ <b>Ошибка создания клиента</b>",
            parse_mode="HTML", reply_markup=None,
        )
        return

    import qrcode, io
    if link:
        qr = qrcode.QRCode(box_size=10, border=2)
        qr.add_data(link)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        from aiogram.types import BufferedInputFile
        try:
            await callback.bot.send_photo(
                user_id,
                photo=BufferedInputFile(buf.read(), filename="qr.png"),
                caption=(
                    f"✅ <b>Доступ одобрен!</b>\n\n"
                    f"🔗 VLESS ссылка:\n<code>{link}</code>\n\n"
                    "📱 Отсканируйте QR в v2rayNG или Hiddify"
                ),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error("Failed to send QR to user %s: %s", user_id, e)
    else:
        try:
            await callback.bot.send_message(
                user_id,
                f"✅ <b>Доступ одобрен!</b>\n\n🆔 UUID: <code>{client_uuid}</code>",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error("Failed to notify user %s: %s", user_id, e)

    await callback.message.edit_text(
        callback.message.text + f"\n\n✅ <b>Одобрено</b> → инбаунд #{inbound_id}\n📧 {email}",
        parse_mode="HTML", reply_markup=None,
    )
