import logging
from typing import Optional
from aiogram import Bot

logger = logging.getLogger(__name__)


async def update_user_status(
    bot: Bot,
    user_id: int,
    status_message_id: Optional[int],
    reply_to_message_id: int,
    text: str,
) -> None:
    if status_message_id:
        try:
            await bot.edit_message_text(
                chat_id=user_id,
                message_id=status_message_id,
                text=text,
                parse_mode="HTML",
            )
            return
        except Exception as e:
            logger.warning(f"Could not edit user status message {status_message_id}: {e}")

    try:
        await bot.send_message(
            chat_id=user_id,
            text=text,
            reply_to_message_id=reply_to_message_id,
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning(f"Could not send fallback message to user {user_id}: {e}")
