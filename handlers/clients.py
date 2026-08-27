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
    return XUIClient(config.PANEL_URL, config.PANEL_USERNAME, config.PANEL_PASSWORD, getattr(config, "API_TOKEN", ""))

def _expire_keyboard():
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="1 месяц",  callback_data="exp:30")
    builder.button(text="3 месяца", callback_data="exp:90")
    builder.button(text="6 месяцев", callback_data="exp:180")
    builder.button(text="1 год",    callback_data="exp:365")
    builder.button(text="Бессрочно", callback_data="exp:0")
    builder.adjust(2, 2, 1)
    return builder.as_markup()


@router.callback_query(F.data.startswith("exp:"))
async def cb_expire_choice(callback: CallbackQuery, state: FSMContext, config: Config):
    await callback.answer()
    days = int(callback.data.split(":")[1])
    await state.update_data(expire_days=days)
    await state.set_state(AddClientStates.waiting_expire)
    expire_str = {0: "Бессрочно", 30: "1 месяц", 90: "3 месяца", 180: "6 месяцев", 365: "1 год"}.get(days, f"{days} дн.")
    data2 = await state.get_data()
    email2 = data2.get("email", "")
    limit2 = data2.get("limit_ip", 0)
    access2 = data2.get("access_type", "acc")
    limit_str2 = f"{limit2} уст." if limit2 else "Без лимита"
    type_str2 = "Подписка" if access2 == "sub" else "Доступ"
    await callback.message.edit_text(
        f"Клиент: {email2}\nТип: {type_str2}\nСрок: {expire_str}\nУстройств: {limit_str2}\n\nПодтверждаете создание?")
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Создать", callback_data="exp:confirm")
    builder.button(text="◀️ Назад", callback_data="menu:main")
    builder.adjust(2)
    await callback.message.edit_reply_markup(reply_markup=builder.as_markup())


@router.callback_query(F.data == "exp:confirm")
async def cb_expire_confirm(callback: CallbackQuery, state: FSMContext, config: Config):
    await callback.answer()
    data = await state.get_data()
    await state.clear()
    days = data.get("expire_days", 30)
    access_type = data.get("access_type", "acc")
    inbound_id = data["inbound_id"]
    limit_ip = data.get("limit_ip", 0)
    xui = _xui(config)
    await xui.login()
    uid = await xui.add_client(inbound_id, email=data["email"],
        traffic_gb=0, expire_days=days, limit_ip=limit_ip)
    await xui.close()
    if not uid:
        await callback.message.edit_text("Ошибка создания клиента.")
        return
    expire_str = {0: "Бессрочно", 30: "1 месяц", 90: "3 месяца", 180: "6 месяцев", 365: "1 год"}.get(days, f"{days} дн.")
    if access_type == "sub":
        xui2 = _xui(config)
        await xui2.login()
        clients = await xui2.get_clients(inbound_id)
        await xui2.close()
        client = next((c for c in clients if c.get("id") == uid), {})
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
            await callback.message.answer_photo(
                photo=BufferedInputFile(buf.read(), filename="sub_qr.png"),
                caption=f"Клиент {data['email']} создан!\nСрок: {expire_str}\nПодписка: {sub_link}",
            )
        else:
            await callback.message.answer(f"Клиент {data['email']} создан!\nUID: {uid}")
    else:
        xui3 = _xui(config)
        await xui3.login()
        link = await xui3.get_client_link(inbound_id, uid)
        await xui3.close()
        await callback.message.answer(f"Клиент {data['email']} создан!\nСрок: {expire_str}\nVLESS: {link}")


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
        f"👥 <b>Клиенты — {remark}</b>\nВсего: {len(clients)}\n\n🟢 онлайн  🔴 офлайн  ⚫ отключён",
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
    inbound = await xui.get_inbound(inbound_id)
    await xui.close()
    inbound_remark = (inbound or {}).get("remark") or f"#{inbound_id}"
    if not client:
        await callback.answer("Клиент не найден", show_alert=True)
        return
    client_id = client.get("id", "")
    email = client.get("email", "—")
    tg_id = client.get("tgId", 0)
    tg_name = ""
    if tg_id:
        try:
            chat = await callback.bot.get_chat(tg_id)
            tg_name = f"@{chat.username}" if chat.username else chat.full_name
        except Exception:
            tg_name = str(tg_id)
    s = stats.get(email, {})
    up, down = s.get("up", 0), s.get("down", 0)
    total_raw = client.get("totalGB", 0)
    expire_ms = client.get("expiryTime", 0)
    created_at = client.get("created_at", "")
    enabled = client.get("enable", True)
    limit_ip = client.get("limitIp", 0)
    import time, datetime
    now_ms = int(time.time() * 1000)
    last_online = s.get("lastOnline", 0)
    if not enabled:
        status_icon = "⚫"
        status_str = "Отключён"
    elif last_online and (now_ms - last_online) < 3 * 60 * 1000:
        status_icon = "🟢"
        status_str = "Онлайн"
    else:
        status_icon = "🔴"
        status_str = "Офлайн"
    last_online_str = datetime.datetime.fromtimestamp(last_online/1000).strftime("%d.%m.%Y %H:%M") if last_online else "Нет данных"
    if created_at:
        try:
            ca_ts = int(created_at) // 1000
            created_str = datetime.datetime.fromtimestamp(ca_ts).strftime("%d.%m.%Y")
        except Exception:
            created_str = str(created_at)[:10]
    else:
        created_str = "Нет данных"
    total_str = format_bytes(total_raw) if total_raw else "Безлимит"
    limit_str = f"{limit_ip} уст." if limit_ip else "Без лимита"
    text = (
        f"{status_icon} <b>{email}</b>\n\n"
        f"📋 Инбаунд: {inbound_remark}\n"
        + (f"👤 Telegram: {tg_name}\n" if tg_name else "")
        + f"📱 Устройств: {limit_str}\n\n"
        f"📊 Статус: {status_str}\n"
        f"🕐 Последний онлайн: {last_online_str}\n"
        f"📅 Создан: {created_str}\n\n"
        f"⬆️ {format_bytes(up)}  ⬇️ {format_bytes(down)}\n"
        f"📦 Лимит: {total_str}\n"
        + (f"⏳ Истекает: {format_expire(expire_ms)}\n" if expire_ms else "⏳ Бессрочно\n")
        + f"🆔 <code>{client_id}</code>"
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
    # Get client info before deletion
    client, _ = await _get_client(xui, inbound_id, idx)
    ok = await xui.delete_client(inbound_id, client_id)
    await xui.close()
    if ok:
        await callback.answer("✅ Удалён", show_alert=True)
        # Notify user if tgId is set
        if client:
            tg_id = client.get("tgId")
            email = client.get("email", "")
            if tg_id and str(tg_id) != "0":
                try:
                    await callback.bot.send_message(
                        int(tg_id),
                        "⚠️ <b>Ваш аккаунт удалён</b>\n\n"
                        f"Профиль <b>{email}</b> удалён администратором.\n\n"
                        "Удалите профиль из VPN-приложений:\n"
                        "• Hiddify: Настройки → Профили → удалить\n"
                        "• v2rayNG: долгое нажатие → удалить\n"
                        "• Streisand: смахните влево → удалить\n\n"
                        "Если есть вопросы — обратитесь к администратору.",
                        parse_mode="HTML",
                    )
                except Exception as e:
                    logger.warning("Could not notify user %s: %s", tg_id, e)
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
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="Подписка", callback_data=f"add:type:sub:{inbound_id}")
    builder.button(text="Доступ",   callback_data=f"add:type:acc:{inbound_id}")
    builder.button(text="◀️ Назад",   callback_data=f"inbound:open:{inbound_id}")
    builder.adjust(2, 1)
    await callback.message.edit_text(
        "Новый клиент\n\nВыберите тип:",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(F.data.startswith("add:type:"))
async def cb_add_type(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    parts = callback.data.split(":")
    access_type = parts[2]
    inbound_id = int(parts[3])
    await state.update_data(inbound_id=inbound_id, access_type=access_type)
    await state.set_state(AddClientStates.waiting_email)
    await callback.message.edit_text(
        "Новый клиент\n\nВведите email клиента:",
        reply_markup=cancel_button(),
    )

@router.message(AddClientStates.waiting_email)
async def fsm_email(message: Message, state: FSMContext):
    email = message.text.strip()
    if not email or " " in email:
        await message.answer("❌ Без пробелов, попробуйте ещё раз:")
        return
    await state.update_data(email=email, traffic_gb=0)
    data = await state.get_data()
    access_type = data.get("access_type", "acc")
    if access_type == "sub":
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        builder.button(text="1 уст.", callback_data="add:dev:1")
        builder.button(text="2 уст.", callback_data="add:dev:2")
        builder.button(text="3 уст.", callback_data="add:dev:3")
        builder.button(text="5 уст.", callback_data="add:dev:5")
        builder.button(text="Без лимита", callback_data="add:dev:0")
        builder.adjust(3, 2)
        await state.set_state(AddClientStates.waiting_devices)
        await message.answer("Количество устройств:", reply_markup=builder.as_markup())
    else:
        await state.set_state(AddClientStates.waiting_expire_choice)
        await message.answer("Срок:", reply_markup=_expire_keyboard())

@router.callback_query(F.data.startswith("add:dev:"))
async def cb_add_devices(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    limit_ip = int(callback.data.split(":")[2])
    await state.update_data(limit_ip=limit_ip)
    await state.set_state(AddClientStates.waiting_expire_choice)
    await callback.message.edit_text("Срок:", reply_markup=_expire_keyboard())

@router.message(AddClientStates.waiting_expire)
async def fsm_expire(message: Message, state: FSMContext, config: Config):
    try:
        days = int(message.text.strip())
        assert days >= 0
    except:
        await message.answer("Введите число >= 0:")
        return
    data = await state.get_data()
    await state.clear()
    access_type = data.get("access_type", "acc")
    inbound_id = data["inbound_id"]
    xui = _xui(config)
    await xui.login()
    limit_ip = data.get("limit_ip", 0)
    uid = await xui.add_client(inbound_id, email=data["email"],
        traffic_gb=data["traffic_gb"], expire_days=days, limit_ip=limit_ip)
    await xui.close()
    if not uid:
        await message.answer("Ошибка создания клиента.")
        return
    expire_str = f"{days} дн." if days else "Бессрочно"
    if access_type == "sub":
        xui2 = _xui(config)
        await xui2.login()
        clients = await xui2.get_clients(inbound_id)
        await xui2.close()
        client = next((c for c in clients if c.get("id") == uid), {})
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
            await message.answer_photo(
                photo=BufferedInputFile(buf.read(), filename="sub_qr.png"),
                caption=(
                    f"Клиент {data['email']} создан!\n\n"
                    f"Срок: {expire_str}\n\n"
                    f"Ссылка подписки:\n{sub_link}"
                ),
            )
        else:
            await message.answer(f"Клиент {data['email']} создан!\nUID: {uid}")
    else:
        xui3 = _xui(config)
        await xui3.login()
        link = await xui3.get_client_link(inbound_id, uid)
        await xui3.close()
        if link:
            import qrcode, io
            from aiogram.types import BufferedInputFile
            qr = qrcode.QRCode(box_size=10, border=2)
            qr.add_data(link)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            await message.answer_photo(
                photo=BufferedInputFile(buf.read(), filename="qr.png"),
                caption=(
                    f"Клиент {data['email']} создан!\n\n"
                    f"Срок: {expire_str}\n\n"
                    f"VLESS ссылка:\n{link}"
                ),
            )
        else:
            await message.answer(f"Клиент {data['email']} создан!\nUID: {uid}")

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
        reply_markup=back_button(back_cb, "◀️ Назад"),
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
    inbound = await xui.get_inbound(inbound_id)
    await xui.close()
    inbound_remark = (inbound or {}).get("remark") or f"#{inbound_id}"
    if not client:
        await callback.answer("Клиент не найден", show_alert=True)
        return
    client_id = client.get("id", "")
    email = client.get("email", "—")
    tg_id = client.get("tgId", 0)
    tg_name = ""
    if tg_id:
        try:
            chat = await callback.bot.get_chat(tg_id)
            tg_name = f"@{chat.username}" if chat.username else chat.full_name
        except Exception:
            tg_name = str(tg_id)
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


@router.callback_query(F.data.startswith("cl:s:"))
async def cb_subscription(callback: CallbackQuery, config: Config):
    await callback.answer()
    parts = callback.data.split(":")
    inbound_id, idx = int(parts[2]), int(parts[3])
    xui = _xui(config)
    await xui.login()
    client, _ = await _get_client(xui, inbound_id, idx)
    await xui.close()
    if not client:
        await callback.answer("Клиент не найден", show_alert=True)
        return
    sub_id = client.get("subId", "")
    email = client.get("email", "")
    from keyboards import back_button
    back_cb = f"cl:v:{inbound_id}:{idx}"
    if not sub_id or not config.SUB_URL:
        await callback.message.edit_text(
            "Подписка недоступна — subId или SUB_URL не заполнены.",
            reply_markup=back_button(back_cb, "◀️ Назад")
        )
        return
    link = f"{config.SUB_URL}{sub_id}"
    text = f"Подписка {email}\n\n{link}\n\nДобавьте в Happ или любой клиент поддерживающий подписки."
    await callback.message.edit_text(
        text,
        reply_markup=back_button(back_cb, "◀️ Назад"),
    )


@router.callback_query(F.data.startswith("cl:sq:"))
async def cb_subscription_qr(callback: CallbackQuery, config: Config):
    await callback.answer()
    parts = callback.data.split(":")
    inbound_id, idx = int(parts[2]), int(parts[3])
    xui = _xui(config)
    await xui.login()
    client, _ = await _get_client(xui, inbound_id, idx)
    await xui.close()
    if not client:
        await callback.answer("Клиент не найден", show_alert=True)
        return
    sub_id = client.get("subId", "")
    email = client.get("email", "")
    if not sub_id or not config.SUB_URL:
        await callback.answer("Подписка недоступна", show_alert=True)
        return
    link = f"{config.SUB_URL}{sub_id}"
    import qrcode, io
    from aiogram.types import BufferedInputFile
    from keyboards import back_button
    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(link)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    back_cb = f"cl:qback:{inbound_id}:{idx}"
    await callback.message.answer_photo(
        photo=BufferedInputFile(buf.read(), filename="sub_qr.png"),
        caption=f"QR подписки {email}\n\n{link}",
        reply_markup=back_button(back_cb, "◀️ Назад"),
    )
    await callback.message.delete()


@router.callback_query(F.data.startswith("cl:b:"))
async def cb_block(callback: CallbackQuery, config: Config):
    parts = callback.data.split(":")
    inbound_id, idx = int(parts[2]), int(parts[3])
    xui = _xui(config)
    await xui.login()
    client, _ = await _get_client(xui, inbound_id, idx)
    if not client:
        await xui.close()
        await callback.answer("Клиент не найден", show_alert=True)
        return
    if not client.get("enable", True):
        await xui.close()
        await callback.answer("Клиент уже заблокирован", show_alert=True)
        return
    ok = await xui.toggle_client(inbound_id, client["id"], False)
    await xui.close()
    await callback.answer("🚫 Клиент заблокирован", show_alert=True)
    if ok:
        callback.data = f"cl:v:{inbound_id}:{idx}"
        await cb_client_view(callback, config)
