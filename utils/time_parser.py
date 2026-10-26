import html
import re
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo


def format_author_tag(user_name: str, user_username: Optional[str], user_id: int) -> str:
    if user_username:
        clean_user = user_username.lstrip("@")
        return f"От: @{clean_user}"
    safe_name = html.escape(user_name or "Пользователь")
    return f'От: <a href="tg://user?id={user_id}">{safe_name}</a>'


def append_author_tag(content_text: Optional[str], author_tag: str) -> str:
    if content_text and content_text.strip():
        return f"{content_text.strip()}\n\n{author_tag}"
    return author_tag


def parse_msk_time(text: str, tz: ZoneInfo) -> Optional[datetime]:
    text = text.strip()
    now = datetime.now(tz)

    m1 = re.fullmatch(r"(\d{1,2}):(\d{2})", text)
    if m1:
        h, mn = int(m1.group(1)), int(m1.group(2))
        if 0 <= h < 24 and 0 <= mn < 60:
            target = now.replace(hour=h, minute=mn, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=1)
            return target

    m2 = re.fullmatch(r"(\d{1,2})[./-](\d{1,2})\s+(\d{1,2}):(\d{2})", text)
    if m2:
        d, mon, h, mn = int(m2.group(1)), int(m2.group(2)), int(m2.group(3)), int(m2.group(4))
        try:
            target = datetime(now.year, mon, d, h, mn, 0, tzinfo=tz)
            if target <= now:
                target = datetime(now.year + 1, mon, d, h, mn, 0, tzinfo=tz)
            return target
        except ValueError:
            pass

    m3 = re.fullmatch(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})\s+(\d{1,2}):(\d{2})", text)
    if m3:
        d, mon, y, h, mn = (
            int(m3.group(1)),
            int(m3.group(2)),
            int(m3.group(3)),
            int(m3.group(4)),
            int(m3.group(5)),
        )
        try:
            target = datetime(y, mon, d, h, mn, 0, tzinfo=tz)
            if target > now:
                return target
        except ValueError:
            pass

    return None


def format_msk_datetime(dt_or_iso: datetime | str, tz: ZoneInfo) -> str:
    if isinstance(dt_or_iso, str):
        try:
            dt = datetime.fromisoformat(dt_or_iso)
        except Exception:
            return dt_or_iso
    else:
        dt = dt_or_iso

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    else:
        dt = dt.astimezone(tz)

    return dt.strftime("%d.%m.%Y %H:%M")
