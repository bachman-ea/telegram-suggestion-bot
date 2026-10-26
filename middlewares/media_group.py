import asyncio
from typing import Any, Awaitable, Callable
from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject


class MediaGroupMiddleware(BaseMiddleware):
    def __init__(self, latency: float = 0.6):
        self.latency = latency
        self.album_data: dict[str, list[Message]] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message) or not event.media_group_id:
            return await handler(event, data)

        mg_id = event.media_group_id

        if mg_id not in self.album_data:
            self.album_data[mg_id] = [event]
            try:
                await asyncio.sleep(self.latency)
            finally:
                album = self.album_data.pop(mg_id, [])

            if not album:
                return

            album.sort(key=lambda m: m.message_id)
            data["album"] = album
            return await handler(album[0], data)
        else:
            self.album_data[mg_id].append(event)
            return
