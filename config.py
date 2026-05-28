import os
from dataclasses import dataclass, field
from typing import List
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    # Telegram
    BOT_TOKEN: str = field(default_factory=lambda: os.getenv("BOT_TOKEN", ""))
    ADMIN_IDS: List[int] = field(
        default_factory=lambda: [
            int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()
        ]
    )

    # 3x-ui panel
    PANEL_URL: str = field(default_factory=lambda: os.getenv("PANEL_URL", "http://localhost:2053"))
    PANEL_USERNAME: str = field(default_factory=lambda: os.getenv("PANEL_USERNAME", "admin"))
    PANEL_PASSWORD: str = field(default_factory=lambda: os.getenv("PANEL_PASSWORD", "admin"))

    # Default traffic limit in GB (0 = unlimited)
    DEFAULT_TRAFFIC_GB: int = field(
        default_factory=lambda: int(os.getenv("DEFAULT_TRAFFIC_GB", "0"))
    )

    # Default expire days (0 = never)
    DEFAULT_EXPIRE_DAYS: int = field(
        default_factory=lambda: int(os.getenv("DEFAULT_EXPIRE_DAYS", "30"))
    )
