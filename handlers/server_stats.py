"""
Server statistics handler.
Collects CPU, RAM, disk, network, uptime via psutil.
Also fetches 3x-ui panel summary (total clients, total traffic).
"""
import asyncio
import logging
import time
from datetime import timedelta

from aiogram import Router, F
from aiogram.types import CallbackQuery

from config import Config
from keyboards import back_button
from services import XUIClient
from utils import AdminMiddleware, format_bytes

logger = logging.getLogger(__name__)
router = Router()
router.callback_query.middleware(AdminMiddleware())


def _xui(config: Config) -> XUIClient:
    return XUIClient(config.PANEL_URL, config.PANEL_USERNAME, config.PANEL_PASSWORD)


async def _collect_system_stats() -> dict:
    """Run psutil calls in executor to avoid blocking event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _psutil_snapshot)


def _psutil_snapshot() -> dict:
    import psutil

    # CPU — measure over 0.5s interval (non-blocking in executor)
    cpu_pct = psutil.cpu_percent(interval=0.5)
    cpu_count = psutil.cpu_count(logical=True)

    # Memory
    mem = psutil.virtual_memory()

    # Swap
    swap = psutil.swap_memory()

    # Disk (root partition)
    disk = psutil.disk_usage("/")

    # Network (cumulative since boot)
    net = psutil.net_io_counters()

    # Uptime
    boot_ts = psutil.boot_time()
    uptime_sec = int(time.time() - boot_ts)
    uptime = str(timedelta(seconds=uptime_sec))

    # Load average (Unix only)
    try:
        load1, load5, load15 = psutil.getloadavg()
        load_str = f"{load1:.2f}  {load5:.2f}  {load15:.2f}"
    except AttributeError:
        load_str = "N/A"

    # Top-5 CPU processes
    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            procs.append(p.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    top_procs = sorted(procs, key=lambda x: x.get("cpu_percent") or 0, reverse=True)[:5]

    return dict(
        cpu_pct=cpu_pct,
        cpu_count=cpu_count,
        load_str=load_str,
        mem_total=mem.total,
        mem_used=mem.used,
        mem_pct=mem.percent,
        swap_total=swap.total,
        swap_used=swap.used,
        swap_pct=swap.percent,
        disk_total=disk.total,
        disk_used=disk.used,
        disk_pct=disk.percent,
        net_sent=net.bytes_sent,
        net_recv=net.bytes_recv,
        uptime=uptime,
        top_procs=top_procs,
    )


def _bar(pct: float, width: int = 10) -> str:
    filled = round(pct / 100 * width)
    return "█" * filled + "░" * (width - filled)


async def _collect_panel_stats(config: Config) -> dict:
    xui = _xui(config)
    await xui.login()
    inbounds = await xui.get_inbounds()
    await xui.close()

    total_clients  = 0
    active_clients = 0
    total_up       = 0
    total_down     = 0
    inbound_rows   = []

    for ib in inbounds:
        stats = ib.get("clientStats", [])
        ib_up   = sum(s.get("up", 0)   for s in stats)
        ib_down = sum(s.get("down", 0) for s in stats)
        active  = sum(1 for s in stats if s.get("enable", True))
        total_clients  += len(stats)
        active_clients += active
        total_up       += ib_up
        total_down     += ib_down
        inbound_rows.append(dict(
            id=ib["id"],
            remark=ib.get("remark") or f"#{ib['id']}",
            protocol=ib.get("protocol", "?").upper(),
            port=ib.get("port", "?"),
            enable=ib.get("enable", True),
            clients=len(stats),
            active=active,
            up=ib_up,
            down=ib_down,
        ))

    return dict(
        inbounds=inbound_rows,
        total_clients=total_clients,
        active_clients=active_clients,
        total_up=total_up,
        total_down=total_down,
    )


def _build_message(sys: dict, panel: dict) -> str:
    lines = []

    # ── System ──
    lines.append("🖥 <b>Статистика сервера</b>")
    lines.append("")

    # CPU
    cpu_bar = _bar(sys["cpu_pct"])
    lines.append(
        f"⚙️ <b>CPU</b>  {sys['cpu_pct']:.1f}%  <code>{cpu_bar}</code>  "
        f"({sys['cpu_count']} ядер)"
    )
    lines.append(f"   Нагрузка (1/5/15 мин): <code>{sys['load_str']}</code>")
    lines.append("")

    # RAM
    mem_bar = _bar(sys["mem_pct"])
    lines.append(
        f"💾 <b>RAM</b>  {sys['mem_pct']:.1f}%  <code>{mem_bar}</code>  "
        f"{format_bytes(sys['mem_used'])} / {format_bytes(sys['mem_total'])}"
    )
    if sys["swap_total"]:
        swap_bar = _bar(sys["swap_pct"])
        lines.append(
            f"   Swap  {sys['swap_pct']:.1f}%  <code>{swap_bar}</code>  "
            f"{format_bytes(sys['swap_used'])} / {format_bytes(sys['swap_total'])}"
        )
    lines.append("")

    # Disk
    disk_bar = _bar(sys["disk_pct"])
    lines.append(
        f"💿 <b>Диск</b>  {sys['disk_pct']:.1f}%  <code>{disk_bar}</code>  "
        f"{format_bytes(sys['disk_used'])} / {format_bytes(sys['disk_total'])}"
    )
    lines.append("")

    # Network
    lines.append(
        f"🌐 <b>Сеть</b>  ⬆️ {format_bytes(sys['net_sent'])}  "
        f"⬇️ {format_bytes(sys['net_recv'])}  <i>(с момента загрузки)</i>"
    )
    lines.append(f"⏱ Аптайм: <code>{sys['uptime']}</code>")
    lines.append("")

    # Top processes
    if sys["top_procs"]:
        lines.append("📊 <b>Топ процессов по CPU:</b>")
        for p in sys["top_procs"]:
            name = (p.get("name") or "?")[:20]
            cpu  = p.get("cpu_percent") or 0.0
            mem  = p.get("memory_percent") or 0.0
            lines.append(f"  • <code>{name:<20}</code>  CPU {cpu:5.1f}%  MEM {mem:4.1f}%")
        lines.append("")

    # ── Panel ──
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("📡 <b>Панель 3x-ui</b>")
    lines.append("")
    lines.append(
        f"👥 Клиентов: <b>{panel['active_clients']}</b> активных "
        f"из <b>{panel['total_clients']}</b> всего"
    )
    lines.append(
        f"📦 Трафик (всего): ⬆️ {format_bytes(panel['total_up'])}  "
        f"⬇️ {format_bytes(panel['total_down'])}"
    )
    lines.append("")

    # Per-inbound table
    if panel["inbounds"]:
        lines.append("<b>Инбаунды:</b>")
        for ib in panel["inbounds"]:
            icon   = "🟢" if ib["enable"] else "🔴"
            remark = ib["remark"][:18]
            lines.append(
                f"{icon} <b>#{ib['id']}</b> {remark} "
                f"[{ib['protocol']}:{ib['port']}]  "
                f"👤 {ib['active']}/{ib['clients']}  "
                f"⬆️{format_bytes(ib['up'])} ⬇️{format_bytes(ib['down'])}"
            )

    return "\n".join(lines)


@router.callback_query(F.data == "server:stats")
async def cb_server_stats(callback: CallbackQuery, config: Config):
    await callback.answer()
    await callback.message.edit_text("⏳ Собираю статистику…")

    try:
        sys_stats, panel_stats = await asyncio.gather(
            _collect_system_stats(),
            _collect_panel_stats(config),
        )
        text = _build_message(sys_stats, panel_stats)
    except Exception as exc:
        logger.exception("server_stats error: %s", exc)
        text = f"❌ Ошибка при сборе статистики:\n<code>{exc}</code>"

    from keyboards import back_button, main_menu
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Обновить",  callback_data="server:stats")
    builder.button(text="◀️ В меню",    callback_data="menu:main")
    builder.adjust(2)

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )
