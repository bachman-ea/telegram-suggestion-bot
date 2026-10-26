from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

from config import Config


class AdminChatFilter(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery, config: Config) -> bool:
        chat = event.chat if isinstance(event, Message) else (event.message.chat if event.message else None)
        return chat is not None and str(chat.id) == str(config.admin_chat_id)
