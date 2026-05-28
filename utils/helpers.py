from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from typing import Callable, Dict, Any, Awaitable


class AdminMiddleware(BaseMiddleware):
    """Reject all updates from non-admin users."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        config = data.get("config")
        if not config:
            return await handler(event, data)

        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user

        if user and user.id not in config.ADMIN_IDS:
            if isinstance(event, Message):
                await event.answer("⛔️ Доступ запрещён.")
            elif isinstance(event, CallbackQuery):
                await event.answer("⛔️ Доступ запрещён.", show_alert=True)
            return

        return await handler(event, data)


def format_bytes(n: int) -> str:
    """Human-readable bytes."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def format_expire(expire_ms: int) -> str:
    """Format expiry timestamp (ms) to human string."""
    if not expire_ms:
        return "∞ Бессрочно"
    import datetime
    ts = expire_ms / 1000
    dt = datetime.datetime.fromtimestamp(ts)
    now = datetime.datetime.now()
    diff = dt - now
    if diff.total_seconds() < 0:
        return f"❌ Истёк {dt.strftime('%d.%m.%Y')}"
    days = diff.days
    return f"📅 {dt.strftime('%d.%m.%Y')} (через {days} дн.)"
