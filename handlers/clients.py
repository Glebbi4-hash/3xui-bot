import logging
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from config import Config
from keyboards import clients_list, cancel_button
from keyboards.inline import client_actions as ca, confirm_delete as cd
from services import XUIClient
from utils import AdminMiddleware, format_bytes, format_expire
from handlers.states import AddClientStates

logger = logging.getLogger(__name__)
router = Router()
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())

def _xui(config):
    return XUIClient(config.PANEL_URL, config.PANEL_USERNAME, config.PANEL_PASSWORD)

async def _get_client(xui, inbound_id, idx):
    clients = await xui.get_clients(inbound_id)
    if idx >= len(clients):
        return None, clients
    return clients[idx], clients

@router.callback_query(F.data.startswith("clients:list:"))
async def cb_clients_list(callback: CallbackQuery, config: Config):
    await callback.answer()
    inbound_id = int(callback.data.split(":")[2])
    xui = _xui(config)
    await xui.login()
    inbound = await xui.get_inbound(inbound_id)
    clients = await xui.get_clients(inbound_id)
    stats = await xui.get_client_traffics(inbound_id)
    await xui.close()
    remark = (inbound or {}).get("remark") or f"#{inbound_id}"
    await callback.message.edit_text(
        f"👥 <b>Клиенты — {remark}</b>\nВсего: {len(clients)}",
        reply_markup=clients_list(clients, stats, inbound_id),
        parse_mode="HTML",
    )
@router.callback_query(F.data.startswith("cl:v:"))
async def cb_client_view(callback: CallbackQuery, config: Config):
    await callback.answer()
    parts = callback.data.split(":")
    inbound_id, idx = int(parts[2]), int(parts[3])
    xui = _xui(config)
    await xui.login()
    client, _ = await _get_client(xui, inbound_id, idx)
    stats = await xui.get_client_traffics(inbound_id)
    await xui.close()
    if not client:
        await callback.answer("Клиент не найден", show_alert=True)
        return
    client_id = client.get("id", "")
    email = client.get("email", "—")
    s = stats.get(email, {})
    up, down = s.get("up", 0), s.get("down", 0)
    total_raw = client.get("totalGB", 0)
    expire_ms = client.get("expiryTime", 0)
    enabled = client.get("enable", True)
    total_str = format_bytes(total_raw) if total_raw else "Безлимит"
    text = (
        f"{'🟢' if enabled else '🔴'} <b>{email}</b>\n\n"
        f"⬆️ {format_bytes(up)}  ⬇️ {format_bytes(down)}\n"
        f"📦 Лимит: {total_str}\n"
        f"⏳ {format_expire(expire_ms)}\n"
        f"🆔 <code>{client_id}</code>"
    )
    await callback.message.edit_text(
        text, reply_markup=ca(inbound_id, idx, client_id, email, enabled), parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("cl:t:"))
async def cb_toggle(callback: CallbackQuery, config: Config):
    parts = callback.data.split(":")
    inbound_id, idx = int(parts[2]), int(parts[3])
    xui = _xui(config)
    await xui.login()
    client, _ = await _get_client(xui, inbound_id, idx)
    if not client:
        await xui.close()
        await callback.answer("Клиент не найден", show_alert=True)
        return
    new_state = not client.get("enable", True)
    await xui.toggle_client(inbound_id, client["id"], new_state)
    await xui.close()
    await callback.answer(f"{'🟢 Включён' if new_state else '🔴 Отключён'}", show_alert=True)
    callback.data = f"cl:v:{inbound_id}:{idx}"
    await cb_client_view(callback, config)
@router.callback_query(F.data.startswith("cl:d:"))
async def cb_delete(callback: CallbackQuery, config: Config):
    parts = callback.data.split(":")
    inbound_id, idx = int(parts[2]), int(parts[3])
    xui = _xui(config)
    await xui.login()
    client, _ = await _get_client(xui, inbound_id, idx)
    await xui.close()
    if not client:
        await callback.answer("Клиент не найден", show_alert=True)
        return
    await callback.answer()
    await callback.message.edit_text(
        f"⚠️ Удалить <b>{client.get('email')}</b>?",
        reply_markup=cd(inbound_id, idx, client["id"], client.get("email","")),
        parse_mode="HTML",
    )

@router.callback_query(F.data.startswith("cl:dc:"))
async def cb_delete_confirm(callback: CallbackQuery, config: Config):
    parts = callback.data.split(":")
    inbound_id, idx, client_id = int(parts[2]), int(parts[3]), parts[4]
    xui = _xui(config)
    await xui.login()
    ok = await xui.delete_client(inbound_id, client_id)
    await xui.close()
    if ok:
        await callback.answer("✅ Удалён", show_alert=True)
        callback.data = f"clients:list:{inbound_id}"
        await cb_clients_list(callback, config)
    else:
        await callback.answer("❌ Ошибка", show_alert=True)

@router.callback_query(F.data.startswith("cl:r:"))
async def cb_reset(callback: CallbackQuery, config: Config):
    parts = callback.data.split(":")
    inbound_id, idx = int(parts[2]), int(parts[3])
    xui = _xui(config)
    await xui.login()
    client, _ = await _get_client(xui, inbound_id, idx)
    if not client:
        await xui.close()
        await callback.answer("Клиент не найден", show_alert=True)
        return
    ok = await xui.reset_client_traffic(inbound_id, client.get("email",""))
    await xui.close()
    await callback.answer("✅ Трафик сброшен" if ok else "❌ Ошибка", show_alert=True)
    if ok:
        callback.data = f"cl:v:{inbound_id}:{idx}"
        await cb_client_view(callback, config)
@router.callback_query(F.data.startswith("cl:l:"))
async def cb_link(callback: CallbackQuery, config: Config):
    await callback.answer()
    parts = callback.data.split(":")
    inbound_id, idx = int(parts[2]), int(parts[3])
    xui = _xui(config)
    await xui.login()
    client, _ = await _get_client(xui, inbound_id, idx)
    inbound = await xui.get_inbound(inbound_id)
    link = await xui.get_client_link(inbound_id, client["id"]) if client else None
    await xui.close()
    from keyboards import back_button
    back_cb = f"cl:v:{inbound_id}:{idx}"
    if link:
        text = f"🔗 <b>{client.get('email')}</b>\n\n<code>{link}</code>\n\nВставьте в VPN-клиент"
    elif inbound and client:
        text = (f"🔗 <b>{client.get('email')}</b>\n\n"
                f"Протокол: {inbound.get('protocol','?').upper()}\n"
                f"UUID: <code>{client['id']}</code>\n\nНастройте вручную.")
    else:
        text = "❌ Не удалось получить данные."
    await callback.message.edit_text(text, parse_mode="HTML",
        reply_markup=back_button(back_cb, "◀️ Назад"))

@router.callback_query(F.data.startswith("clients:add:"))
async def cb_add(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    inbound_id = int(callback.data.split(":")[2])
    await state.update_data(inbound_id=inbound_id)
    await state.set_state(AddClientStates.waiting_email)
    await callback.message.edit_text(
        "➕ <b>Новый клиент</b>\n\nВведите email клиента:",
        reply_markup=cancel_button(), parse_mode="HTML",
    )
@router.message(AddClientStates.waiting_email)
async def fsm_email(message: Message, state: FSMContext):
    email = message.text.strip()
    if not email or " " in email:
        await message.answer("❌ Без пробелов, попробуйте ещё раз:")
        return
    await state.update_data(email=email)
    await state.set_state(AddClientStates.waiting_traffic)
    await message.answer(f"📦 Лимит GB (0 = безлимит):",
        reply_markup=cancel_button(), parse_mode="HTML")

@router.message(AddClientStates.waiting_traffic)
async def fsm_traffic(message: Message, state: FSMContext):
    try:
        gb = int(message.text.strip())
        assert gb >= 0
    except:
        await message.answer("❌ Введите число ≥ 0:")
        return
    await state.update_data(traffic_gb=gb)
    await state.set_state(AddClientStates.waiting_expire)
    await message.answer("⏳ Срок в днях (0 = бессрочно):", reply_markup=cancel_button())

@router.message(AddClientStates.waiting_expire)
async def fsm_expire(message: Message, state: FSMContext, config: Config):
    try:
        days = int(message.text.strip())
        assert days >= 0
    except:
        await message.answer("❌ Введите число ≥ 0:")
        return
    data = await state.get_data()
    await state.clear()
    xui = _xui(config)
    await xui.login()
    uid = await xui.add_client(data["inbound_id"], email=data["email"],
        traffic_gb=data["traffic_gb"], expire_days=days)
    await xui.close()
    if uid:
        await message.answer(
            f"✅ <b>{data['email']}</b> создан!\n🆔 <code>{uid}</code>\n/start",
            parse_mode="HTML")
    else:
        await message.answer("❌ Ошибка создания клиента.")

@router.callback_query(F.data.startswith("cl:q:"))
async def cb_qr(callback: CallbackQuery, config: Config):
    await callback.answer()
    parts = callback.data.split(":")
    inbound_id, idx = int(parts[2]), int(parts[3])
    xui = _xui(config)
    await xui.login()
    client, _ = await _get_client(xui, inbound_id, idx)
    link = await xui.get_client_link(inbound_id, client["id"]) if client else None
    await xui.close()

    from keyboards import back_button
    back_cb = f"cl:qback:{inbound_id}:{idx}"

    if not link:
        await callback.message.answer("❌ Не удалось получить ссылку для QR-кода.")
        return

    import qrcode
    import io
    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(link)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    from aiogram.types import BufferedInputFile
    from aiogram.methods import EditMessageMedia
    from aiogram.types import InputMediaPhoto
    email = client.get("email", "") if client else ""
    photo = BufferedInputFile(buf.read(), filename="qr.png")
    await callback.message.answer_photo(
        photo=photo,
        caption=f"📱 <b>QR-код — {email}</b>\n\n<code>{link}</code>",
        parse_mode="HTML",
        reply_markup=back_button(back_cb, "◀️ Назад к клиенту"),
    )
    await callback.message.delete()

@router.callback_query(F.data.startswith("cl:qback:"))
async def cb_qr_back(callback: CallbackQuery, config: Config):
    parts = callback.data.split(":")
    inbound_id, idx = int(parts[2]), int(parts[3])
    await callback.message.delete()
    xui = _xui(config)
    await xui.login()
    client, _ = await _get_client(xui, inbound_id, idx)
    stats = await xui.get_client_traffics(inbound_id)
    await xui.close()
    if not client:
        await callback.answer("Клиент не найден", show_alert=True)
        return
    client_id = client.get("id", "")
    email = client.get("email", "—")
    s = stats.get(email, {})
    up, down = s.get("up", 0), s.get("down", 0)
    total_raw = client.get("totalGB", 0)
    expire_ms = client.get("expiryTime", 0)
    enabled = client.get("enable", True)
    total_str = format_bytes(total_raw) if total_raw else "Безлимит"
    from keyboards.inline import client_actions as ca
    text = (
        f"{'🟢' if enabled else '🔴'} <b>{email}</b>\n\n"
        f"⬆️ {format_bytes(up)}  ⬇️ {format_bytes(down)}\n"
        f"📦 Лимит: {total_str}\n"
        f"⏳ {format_expire(expire_ms)}\n"
        f"🆔 <code>{client_id}</code>"
    )
    await callback.message.answer(
        text, reply_markup=ca(inbound_id, idx, client_id, email, enabled), parse_mode="HTML"
    )
    await callback.answer()
