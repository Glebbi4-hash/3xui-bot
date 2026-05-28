import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import Config
from services import XUIClient
from utils import AdminMiddleware, format_bytes

logger = logging.getLogger(__name__)
router = Router()
router.callback_query.middleware(AdminMiddleware())


def _xui(config):
    return XUIClient(config.PANEL_URL, config.PANEL_USERNAME, config.PANEL_PASSWORD)


@router.callback_query(F.data == "monitor:traffic")
async def cb_monitor_traffic(callback: CallbackQuery, config: Config):
    await callback.answer()
    xui = _xui(config)
    await xui.login()
    inbounds = await xui.get_inbounds()
    await xui.close()

    all_clients = []
    for ib in inbounds:
        remark = ib.get("remark") or f"#{ib['id']}"
        for s in (ib.get("clientStats") or []):
            up = s.get("up", 0)
            down = s.get("down", 0)
            if up + down == 0:
                continue
            all_clients.append({
                "email": s.get("email", "?"),
                "inbound": remark,
                "up": up,
                "down": down,
                "total": up + down,
                "enable": s.get("enable", True),
            })

    all_clients.sort(key=lambda x: x["total"], reverse=True)
    top = all_clients[:15]

    if not top:
        text = "📊 <b>Мониторинг трафика</b>\n\nНет активных клиентов."
    else:
        lines = ["📊 <b>Топ клиентов по трафику (сессия)</b>\n"]
        for i, c in enumerate(top, 1):
            icon = "🟢" if c["enable"] else "🔴"
            lines.append(
                f"{i}. {icon} <b>{c['email']}</b> [{c['inbound']}]\n"
                f"   ⬆️ {format_bytes(c['up'])}  ⬇️ {format_bytes(c['down'])}  "
                f"📦 {format_bytes(c['total'])}"
            )
        text = "\n".join(lines)

    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Обновить", callback_data="monitor:traffic")
    builder.button(text="◀️ В меню",   callback_data="menu:main")
    builder.adjust(2)

    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )
