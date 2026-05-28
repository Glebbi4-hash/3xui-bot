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
router.callback_query.middleware(AdminMiddleware())


def _xui(config: Config) -> XUIClient:
    return XUIClient(config.PANEL_URL, config.PANEL_USERNAME, config.PANEL_PASSWORD)


# ------------------------------------------------------------------ #
#  /start  &  main menu                                               #
# ------------------------------------------------------------------ #

@router.message(CommandStart())
async def cmd_start(message: Message, config: Config):
    if message.from_user.id not in config.ADMIN_IDS:
        return
    await message.answer(
        "👋 <b>3x-ui Manager</b>\n\nВыберите действие:",
        reply_markup=main_menu(),
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
