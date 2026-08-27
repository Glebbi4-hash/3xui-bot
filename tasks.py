import json
import time
import logging

from aiogram.utils.keyboard import InlineKeyboardBuilder
from services import XUIClient

logger = logging.getLogger(__name__)
DAY_MS = 86400000


async def check_expiring(bot, config):
    xui = XUIClient(config.PANEL_URL, config.PANEL_USERNAME, config.PANEL_PASSWORD, config.API_TOKEN)
    try:
        await xui.login()
        inbounds = await xui.get_inbounds()
    finally:
        await xui.close()

    now = int(time.time() * 1000)
    sent = 0
    for ib in inbounds:
        raw = ib.get("settings", "{}")
        try:
            clients = (json.loads(raw) if isinstance(raw, str) else raw).get("clients", [])
        except Exception:
            continue
        for c in clients:
            tg_id = c.get("tgId") or 0
            exp = c.get("expiryTime") or 0
            if not tg_id or not exp or not c.get("enable", True):
                continue
            days_left = (exp - now) // DAY_MS
            if days_left not in (1, 3):
                continue
            uuid = c.get("id")
            email = c.get("email", "?")
            date = time.strftime("%d.%m.%Y %H:%M", time.localtime(exp / 1000))
            kb = InlineKeyboardBuilder()
            kb.button(text="⏳ Продлить", callback_data=f"user:renew:{uuid}")
            text = (
                "⏳ <b>Подписка скоро закончится</b>\n\n"
                f"Подписка: <b>{email}</b>\n"
                f"Осталось: <b>{days_left} дн.</b> (до {date})\n\n"
                "Продлите, чтобы не потерять доступ 👇"
            )
            try:
                await bot.send_message(tg_id, text,
                                       reply_markup=kb.as_markup(), parse_mode="HTML")
                sent += 1
            except Exception as e:
                logger.warning("Expiry notify failed for %s (tg %s): %s", email, tg_id, e)
    logger.info("Expiry check done: %s notifications sent", sent)
