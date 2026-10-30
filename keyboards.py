from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_review_keyboard(post_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Принять", callback_data=f"rev:acc:{post_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"rev:rej:{post_id}"),
            ],
            [
                InlineKeyboardButton(text="🔄 На доработку", callback_data=f"rev:rev:{post_id}"),
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
