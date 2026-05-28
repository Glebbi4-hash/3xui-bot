from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List, Dict


# ------------------------------------------------------------------ #
#  Main menu                                                           #
# ------------------------------------------------------------------ #

def main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Инбаунды",          callback_data="inbounds:list")
    builder.button(text="🖥 Статистика сервера", callback_data="server:stats")
    builder.button(text="📊 Мониторинг",         callback_data="monitor:traffic")
    builder.adjust(2, 1)
    return builder.as_markup()


# ------------------------------------------------------------------ #
#  Inbounds                                                            #
# ------------------------------------------------------------------ #

def inbounds_menu(inbounds: List[Dict]) -> InlineKeyboardMarkup:
    """Список инбаундов — каждый открывает управление клиентами."""
    builder = InlineKeyboardBuilder()
    for ib in inbounds:
        icon = "🟢" if ib.get("enable") else "🔴"
        proto = ib.get("protocol", "?").upper()
        remark = ib.get("remark") or f"Inbound #{ib['id']}"
        builder.button(
            text=f"{icon} #{ib['id']} {remark} [{proto}:{ib.get('port')}]",
            callback_data=f"inbound:open:{ib['id']}",
        )
    builder.button(text="◀️ Назад", callback_data="menu:main")
    builder.adjust(1)
    return builder.as_markup()


def inbound_actions(inbound_id: int, remark: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👥 Клиенты",        callback_data=f"clients:list:{inbound_id}")
    builder.button(text="➕ Добавить",        callback_data=f"clients:add:{inbound_id}")
    builder.button(text="◀️ К инбаундам",    callback_data="inbounds:list")
    builder.adjust(2, 1)
    return builder.as_markup()


def inbounds_list_select(inbounds: List[Dict], action: str) -> InlineKeyboardMarkup:
    """Выбор инбаунда для конкретного действия (action = add / list)."""
    builder = InlineKeyboardBuilder()
    for ib in inbounds:
        icon = "🟢" if ib.get("enable") else "🔴"
        remark = ib.get("remark") or f"#{ib['id']}"
        builder.button(
            text=f"{icon} #{ib['id']} {remark}",
            callback_data=f"inbound:{action}:{ib['id']}",
        )
    builder.button(text="❌ Отмена", callback_data="menu:main")
    builder.adjust(1)
    return builder.as_markup()


# ------------------------------------------------------------------ #
#  Clients                                                             #
# ------------------------------------------------------------------ #

def clients_list(clients: List[Dict], stats: Dict, inbound_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for i, client in enumerate(clients):
        email   = client.get("email", "—")
        enabled = client.get("enable", True)
        icon    = "🟢" if enabled else "🔴"
        s       = stats.get(email, {})
        used_gb = round((s.get("up", 0) + s.get("down", 0)) / 1024 ** 3, 2)
        builder.button(
            text=f"{icon} {email}  ({used_gb} GB)",
            callback_data=f"cl:v:{inbound_id}:{i}",
        )
    builder.button(text="➕ Добавить",      callback_data=f"clients:add:{inbound_id}")
    builder.button(text="◀️ К инбаунду",   callback_data=f"inbound:open:{inbound_id}")
    builder.adjust(1)
    return builder.as_markup()


def client_actions(inbound_id: int, idx: int, client_id: str, email: str, enabled: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    toggle_text = "🔴 Отключить" if enabled else "🟢 Включить"
    builder.button(text=toggle_text,            callback_data=f"cl:t:{inbound_id}:{idx}")
    builder.button(text="🔄 Сбросить трафик",   callback_data=f"cl:r:{inbound_id}:{idx}")
    builder.button(text="🔗 Ссылка",            callback_data=f"cl:l:{inbound_id}:{idx}")
    builder.button(text="📱 QR-код",            callback_data=f"cl:q:{inbound_id}:{idx}")
    builder.button(text="🗑 Удалить",           callback_data=f"cl:d:{inbound_id}:{idx}")
    builder.button(text="◀️ К списку",          callback_data=f"clients:list:{inbound_id}")
    builder.adjust(2, 2, 1, 1)
    return builder.as_markup()


def confirm_delete(inbound_id: int, idx: int, client_id: str, email: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, удалить", callback_data=f"cl:dc:{inbound_id}:{idx}:{client_id}")
    builder.button(text="❌ Отмена",      callback_data=f"cl:v:{inbound_id}:{idx}")
    builder.adjust(2)
    return builder.as_markup()


# ------------------------------------------------------------------ #
#  Misc                                                                #
# ------------------------------------------------------------------ #

def cancel_button(back: str = "menu:main") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data=back)
    return builder.as_markup()


def back_button(target: str, label: str = "◀️ Назад") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=label, callback_data=target)
    return builder.as_markup()
