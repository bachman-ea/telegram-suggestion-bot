import logging
from aiogram import Bot
from aiogram.enums import ChatMemberStatus

logger = logging.getLogger(__name__)


async def check_channel_subscription(bot: Bot, channel_id: int | str, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        return member.status not in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED)
    except Exception as e:
        logger.warning(f"Failed to check subscription for {user_id} in {channel_id}: {e}")
        return False


async def get_channel_link(bot: Bot, channel_id: int | str) -> str:
    if isinstance(channel_id, str) and channel_id.startswith("@"):
        return f"https://t.me/{channel_id[1:]}"
    try:
        chat = await bot.get_chat(channel_id)
        if chat.username:
            return f"https://t.me/{chat.username}"
        if chat.invite_link:
            return chat.invite_link
        export = await bot.export_chat_invite_link(channel_id)
        return export
    except Exception:
        return "https://t.me"
