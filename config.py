import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()


def _parse_chat_id(val: str | None) -> int | str | None:
    if not val:
        return None
    val = val.strip()
    try:
        return int(val)
    except ValueError:
        return val


@dataclass(frozen=True)
class Config:
    bot_token: str
    admin_chat_id: int | str
    channel_id: int | str
    timezone: ZoneInfo
    db_path: str


def load_config() -> Config:
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        raise ValueError("BOT_TOKEN is not set in .env")

    admin_chat_raw = os.getenv("ADMIN_CHAT_ID")
    if not admin_chat_raw:
        raise ValueError("ADMIN_CHAT_ID is not set in .env")
    admin_chat_id = _parse_chat_id(admin_chat_raw)

    channel_raw = os.getenv("CHANNEL_ID")
    if not channel_raw:
        raise ValueError("CHANNEL_ID is not set in .env")
    channel_id = _parse_chat_id(channel_raw)

    tz_str = os.getenv("TIMEZONE", "Europe/Moscow")
    try:
        tz = ZoneInfo(tz_str)
    except Exception:
        tz = ZoneInfo("Europe/Moscow")

    db_path = os.getenv("DB_PATH", "bot.db")

    return Config(
        bot_token=bot_token,
        admin_chat_id=admin_chat_id,
        channel_id=channel_id,
        timezone=tz,
        db_path=db_path,
    )
