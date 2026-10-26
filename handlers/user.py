import html
import json
import logging
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.filters import CommandStart
from aiogram.types import (
    CallbackQuery,
    InputMediaAudio,
    InputMediaDocument,
    InputMediaPhoto,
    InputMediaVideo,
    Message,
)

from config import Config
from database import Database
from keyboards import get_review_keyboard, get_subscription_keyboard
from utils import (
    check_channel_subscription,
    format_author_tag,
    format_msk_datetime,
    get_channel_link,
)

logger = logging.getLogger(__name__)
user_router = Router(name="user_router")
user_router.message.filter(F.chat.type == ChatType.PRIVATE)
user_router.callback_query.filter(F.message.chat.type == ChatType.PRIVATE)


@user_router.callback_query(F.data == "sub:check")
async def sub_check_callback(
    callback: CallbackQuery,
    bot: Bot,
    config: Config,
    db: Database,
) -> None:
    user_id = callback.from_user.id
    ban_info = await db.is_user_banned(user_id)
    if ban_info:
        await callback.answer("Вы заблокированы в предложке.", show_alert=True)
        return

    is_sub = await check_channel_subscription(bot, config.channel_id, user_id)
    if is_sub:
        await callback.message.edit_text(
            "✅ <b>Спасибо за подписку!</b>\n\n"
            "Теперь вы можете отправить свой пост прямо в этот чат.",
            parse_mode="HTML",
        )
        await callback.answer()
    else:
        await callback.answer("❌ Вы ещё не подписались на канал!", show_alert=True)


@user_router.message(CommandStart())
async def command_start_handler(
    message: Message,
    bot: Bot,
    db: Database,
    config: Config,
) -> None:
    user_id = message.from_user.id
    ban_info = await db.is_user_banned(user_id)
    if ban_info:
        await message.answer(
            f"🚫 <b>Вы заблокированы в предложке.</b>\n\n"
            f"<b>Причина:</b> {html.escape(ban_info['reason'])}\n"
            f"<b>Дата блокировки:</b> {format_msk_datetime(ban_info['banned_at'], config.timezone)} МСК",
            parse_mode="HTML",
        )
        return

    is_sub = await check_channel_subscription(bot, config.channel_id, user_id)
    if not is_sub:
        link = await get_channel_link(bot, config.channel_id)
        await message.answer(
            "👋 <b>Добро пожаловать в предложку канала!</b>\n\n"
            "⚠️ <b>Для использования бота необходимо подписаться на наш канал:</b>",
            reply_markup=get_subscription_keyboard(link),
            parse_mode="HTML",
        )
        return

    text = (
        "👋 <b>Приветствуем вас в предложке канала!</b>\n\n"
        "Через этого бота вы можете предложить свой пост для публикации в нашем канале.\n\n"
        "📌 <b>Что можно отправить:</b>\n"
        "• Текстовые заметки и статьи\n"
        "• Фотографии и видеозаписи с описанием\n"
        "• <b>Коллажи (альбомы)</b> из нескольких фото и видео\n"
        "• Документы, анимации (GIF) и аудио\n\n"
        "🚀 <i>Просто отправьте ваш пост прямо в этот диалог. Он поступит на рассмотрение модераторам, "
        "а бот уведомит вас о решении и о выходе поста в канале!</i>"
    )
    await message.answer(text, parse_mode="HTML")


@user_router.message(F.text.startswith("/"))
async def unknown_command_handler(message: Message) -> None:
    await message.reply(
        "⚠️ Команды в личных сообщениях не поддерживаются. "
        "Чтобы предложить новость, просто отправьте текст, медиа или коллаж."
    )


@user_router.message()
async def handle_incoming_post(
    message: Message,
    bot: Bot,
    db: Database,
    config: Config,
    album: list[Message] | None = None,
) -> None:
    author = message.from_user
    user_id = author.id
    user_name = author.full_name
    user_username = author.username

    ban_info = await db.is_user_banned(user_id)
    if ban_info:
        await message.answer(
            f"🚫 <b>Вы заблокированы в предложке.</b>\n\n"
            f"<b>Причина:</b> {html.escape(ban_info['reason'])}\n"
            f"<b>Дата блокировки:</b> {format_msk_datetime(ban_info['banned_at'], config.timezone)} МСК",
            parse_mode="HTML",
        )
        return

    is_sub = await check_channel_subscription(bot, config.channel_id, user_id)
    if not is_sub:
        link = await get_channel_link(bot, config.channel_id)
        await message.answer(
            "⚠️ <b>Для отправки постов необходимо подписаться на наш канал!</b>",
            reply_markup=get_subscription_keyboard(link),
            parse_mode="HTML",
        )
        return

    now = datetime.now(config.timezone)
    now_iso = now.isoformat()
    now_formatted = format_msk_datetime(now, config.timezone)
    author_tag = format_author_tag(user_name, user_username, user_id)

    if album:
        caption_text = ""
        for m in album:
            if m.caption:
                caption_text = m.html_text
                break

        media_items = []
        for m in album:
            if m.photo:
                media_items.append({"type": "photo", "file_id": m.photo[-1].file_id})
            elif m.video:
                media_items.append({"type": "video", "file_id": m.video.file_id})
            elif m.audio:
                media_items.append({"type": "audio", "file_id": m.audio.file_id})
            elif m.document:
                media_items.append({"type": "document", "file_id": m.document.file_id})

        if not media_items:
            await message.reply("⚠️ Не удалось обработать медиафайлы из альбома.")
            return

        first_msg_id = album[0].message_id
        post_id = await db.add_post(
            user_id=user_id,
            user_name=user_name,
            user_username=user_username,
            user_message_id=first_msg_id,
            post_type="media_group",
            text=caption_text,
            media_data=json.dumps(media_items),
            created_at=now_iso,
        )

        try:
            status_msg = await message.answer(
                "⏳ <b>Ваш предложенный пост (коллаж) принят на рассмотрение!</b>\n"
                "Ожидайте решения администрации.",
                reply_to_message_id=first_msg_id,
                parse_mode="HTML",
            )
            await db.update_user_status_message(post_id, status_msg.message_id)
        except Exception as e:
            logger.warning(f"Could not answer user {user_id}: {e}")

        admin_media = []
        for idx, item in enumerate(media_items):
            item_cap = caption_text if idx == 0 else None
            item_pm = "HTML" if item_cap else None
            if item["type"] == "photo":
                admin_media.append(InputMediaPhoto(media=item["file_id"], caption=item_cap, parse_mode=item_pm))
            elif item["type"] == "video":
                admin_media.append(InputMediaVideo(media=item["file_id"], caption=item_cap, parse_mode=item_pm))
            elif item["type"] == "audio":
                admin_media.append(InputMediaAudio(media=item["file_id"], caption=item_cap, parse_mode=item_pm))
            elif item["type"] == "document":
                admin_media.append(InputMediaDocument(media=item["file_id"], caption=item_cap, parse_mode=item_pm))

        try:
            sent_album = await bot.send_media_group(
                chat_id=config.admin_chat_id,
                media=admin_media,
            )
            reply_to_msg_id = sent_album[0].message_id
        except Exception as e:
            logger.error(f"Failed to send album to admin chat: {e}", exc_info=True)
            return

        card_text = (
            f"📋 <b>Заявка на публикацию #{post_id}</b>\n\n"
            f"👤 <b>Автор:</b> {author_tag} (ID: <code>{user_id}</code>)\n"
            f"🕒 <b>Получено:</b> {now_formatted} МСК\n\n"
            f"<i>Выберите действие ниже:</i>"
        )
        card_msg = await bot.send_message(
            chat_id=config.admin_chat_id,
            text=card_text,
            reply_markup=get_review_keyboard(post_id),
            reply_to_message_id=reply_to_msg_id,
            parse_mode="HTML",
        )
        await db.update_admin_message(post_id, config.admin_chat_id, card_msg.message_id)
        return

    post_type = None
    media_data = None
    content_text = ""

    if message.text:
        post_type = "text"
        content_text = message.html_text
    elif message.photo:
        post_type = "photo"
        content_text = message.html_text if message.caption else ""
        media_data = json.dumps({"type": "photo", "file_id": message.photo[-1].file_id})
    elif message.video:
        post_type = "video"
        content_text = message.html_text if message.caption else ""
        media_data = json.dumps({"type": "video", "file_id": message.video.file_id})
    elif message.animation:
        post_type = "animation"
        content_text = message.html_text if message.caption else ""
        media_data = json.dumps({"type": "animation", "file_id": message.animation.file_id})
    elif message.document:
        post_type = "document"
        content_text = message.html_text if message.caption else ""
        media_data = json.dumps({"type": "document", "file_id": message.document.file_id})
    elif message.audio:
        post_type = "audio"
        content_text = message.html_text if message.caption else ""
        media_data = json.dumps({"type": "audio", "file_id": message.audio.file_id})
    elif message.voice:
        post_type = "voice"
        content_text = message.html_text if message.caption else ""
        media_data = json.dumps({"type": "voice", "file_id": message.voice.file_id})
    else:
        await message.reply(
            "⚠️ Данный формат сообщения не поддерживается для предложки. "
            "Пожалуйста, отправьте текст, фото, видео или коллаж."
        )
        return

    post_id = await db.add_post(
        user_id=user_id,
        user_name=user_name,
        user_username=user_username,
        user_message_id=message.message_id,
        post_type=post_type,
        text=content_text,
        media_data=media_data,
        created_at=now_iso,
    )

    try:
        status_msg = await message.answer(
            "⏳ <b>Ваш предложенный пост принят на рассмотрение!</b>\n"
            "Ожидайте решения администрации.",
            reply_to_message_id=message.message_id,
            parse_mode="HTML",
        )
        await db.update_user_status_message(post_id, status_msg.message_id)
    except Exception as e:
        logger.warning(f"Could not answer user {user_id}: {e}")

    try:
        copied_msg = await message.copy_to(chat_id=config.admin_chat_id)
    except Exception as e:
        logger.error(f"Failed to copy message to admin chat: {e}", exc_info=True)
        return

    card_text = (
        f"📋 <b>Заявка на публикацию #{post_id}</b>\n\n"
        f"👤 <b>Автор:</b> {author_tag} (ID: <code>{user_id}</code>)\n"
        f"🕒 <b>Получено:</b> {now_formatted} МСК\n\n"
        f"<i>Выберите действие ниже:</i>"
    )
    card_msg = await bot.send_message(
        chat_id=config.admin_chat_id,
        text=card_text,
        reply_markup=get_review_keyboard(post_id),
        reply_to_message_id=copied_msg.message_id,
        parse_mode="HTML",
    )
    await db.update_admin_message(post_id, config.admin_chat_id, card_msg.message_id)
