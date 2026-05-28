import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery

from config import Config
from keyboards import back_button
from services import XUIClient
from utils import AdminMiddleware

logger = logging.getLogger(__name__)
router = Router()
router.callback_query.middleware(AdminMiddleware())


def _xui(config: Config) -> XUIClient:
    return XUIClient(config.PANEL_URL, config.PANEL_USERNAME, config.PANEL_PASSWORD)


@router.callback_query(F.data.startswith("client:link:"))
async def cb_client_link(callback: CallbackQuery, config: Config):
    await callback.answer()
    # format: client:link:{inbound_id}:{client_id}:{email}
    parts      = callback.data.split(":")
    inbound_id = int(parts[2])
    client_id  = parts[3]
    email      = parts[4]

    xui = _xui(config)
    await xui.login()
    link    = await xui.get_client_link(inbound_id, client_id)
    inbound = await xui.get_inbound(inbound_id)
    await xui.close()

    back_cb = f"client:view:{inbound_id}:{client_id}:{email}"

    if link:
        text = (
            f"🔗 <b>Ссылка подключения — {email}</b>\n\n"
            f"<code>{link}</code>\n\n"
            "Скопируйте и вставьте в VPN-клиент (v2rayNG, Hiddify, Sing-Box и др.)"
        )
    elif inbound:
        proto  = inbound.get("protocol", "?").upper()
        port   = inbound.get("port", "?")
        remark = inbound.get("remark", "")
        text = (
            f"🔗 <b>Подключение {email}</b>\n\n"
            f"<b>Протокол:</b> {proto}\n"
            f"<b>Порт:</b> {port}\n"
            f"<b>UUID:</b> <code>{client_id}</code>\n"
            f"<b>Remark:</b> {remark}\n\n"
            "⚠️ Для данного протокола авто-генерация ссылки недоступна.\n"
            "Настройте клиент вручную или через панель 3x-ui."
        )
    else:
        text = "❌ Не удалось получить данные инбаунда."

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=back_button(back_cb, "◀️ Назад к клиенту"),
    )
