import json
from typing import Any
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_review_keyboard(post_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Принять", callback_data=f"rev:acc:{post_id}"),
                InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit:open:{post_id}:rev"),
            ],
            [
                InlineKeyboardButton(text="🔄 На доработку", callback_data=f"rev:rev:{post_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"rev:rej:{post_id}"),
            ],
            [
                InlineKeyboardButton(text="🚫 Отклонить и бан", callback_data=f"rev:ban:{post_id}"),
            ],
        ]
    )


def get_schedule_keyboard(post_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🚀 Опубликовать сейчас", callback_data=f"sch:now:{post_id}")
            ],
            [
                InlineKeyboardButton(text="⏱ Через 30 минут", callback_data=f"sch:30m:{post_id}"),
                InlineKeyboardButton(text="⏰ Через 1 час", callback_data=f"sch:60m:{post_id}"),
            ],
            [
                InlineKeyboardButton(text="📅 Произвольное время (МСК)", callback_data=f"sch:custom:{post_id}")
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад (подумать ещё раз)", callback_data=f"sch:back:{post_id}")
            ],
        ]
    )


def get_reschedule_keyboard(post_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🚀 Опубликовать сейчас", callback_data=f"sch:now:{post_id}")
            ],
            [
                InlineKeyboardButton(text="⏱ Через 30 минут", callback_data=f"sch:30m:{post_id}"),
                InlineKeyboardButton(text="⏰ Через 1 час", callback_data=f"sch:60m:{post_id}"),
            ],
            [
                InlineKeyboardButton(text="📅 Произвольное время (МСК)", callback_data=f"sch:custom:{post_id}")
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад к очереди", callback_data="back_to_queue")
            ],
        ]
    )


def get_cancel_custom_keyboard(post_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="❌ Отменить выбор времени", callback_data=f"sch:cancel_custom:{post_id}")
            ]
        ]
    )


def get_cancel_ban_keyboard(post_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="❌ Отменить блокировку", callback_data=f"rev:cancel_ban:{post_id}")
            ]
        ]
    )


def get_cancel_revision_keyboard(post_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="❌ Отменить отправку на доработку", callback_data=f"rev:cancel_rev:{post_id}")
            ]
        ]
    )


def get_edit_post_keyboard(post: dict[str, Any], origin: str) -> InlineKeyboardMarkup:
    post_id = post["id"]
    post_type = post.get("post_type")
    text = post.get("text")
    rows: list[list[InlineKeyboardButton]] = []

    text_row = [InlineKeyboardButton(text="📝 Изменить текст", callback_data=f"edit:text:{post_id}:{origin}")]
    if text and text.strip() and post_type != "text":
        text_row.append(InlineKeyboardButton(text="🗑 Удалить текст", callback_data=f"edit:rm_text:{post_id}:{origin}"))
    rows.append(text_row)

    if post_type in ("photo", "video", "animation", "document", "audio", "voice"):
        rows.append([
            InlineKeyboardButton(text="🗑 Удалить медиафайл", callback_data=f"edit:rm_media:{post_id}:{origin}")
        ])
    elif post_type == "media_group":
        items = []
        try:
            items = json.loads(post.get("media_data") or "[]")
        except Exception:
            pass

        item_buttons = []
        for idx, it in enumerate(items):
            item_buttons.append(
                InlineKeyboardButton(
                    text=f"🗑 Фото #{idx + 1}",
                    callback_data=f"edit:rm_item:{post_id}:{idx}:{origin}",
                )
            )
            if len(item_buttons) == 2:
                rows.append(item_buttons)
                item_buttons = []
        if item_buttons:
            rows.append(item_buttons)

        if len(items) > 1:
            rows.append([
                InlineKeyboardButton(text="🗑 Удалить все медиа", callback_data=f"edit:rm_media:{post_id}:{origin}")
            ])

    back_text = "⬅️ Готово к решению" if origin == "rev" else "⬅️ Готово к очереди"
    rows.append([
        InlineKeyboardButton(text=back_text, callback_data=f"edit:done:{post_id}:{origin}")
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_cancel_edit_text_keyboard(post_id: int, origin: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="❌ Отменить ввод текста", callback_data=f"edit:cancel_text:{post_id}:{origin}")
            ]
        ]
    )


def get_subscription_keyboard(channel_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📢 Подписаться на канал", url=channel_url)
            ],
            [
                InlineKeyboardButton(text="🔄 Я подписался", callback_data="sub:check")
            ],
        ]
    )


def get_cancel_scheduled_keyboard(post_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="❌ Отменить публикацию", callback_data=f"cancel_sch:{post_id}")
            ]
        ]
    )


def get_unban_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔓 Разблокировать", callback_data=f"unban:{user_id}")
            ]
        ]
    )
