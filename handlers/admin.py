import html
import logging
from datetime import datetime, timedelta
from typing import Any

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import Config
from database import Database
from filters import AdminChatFilter
from keyboards import (
    get_cancel_ban_keyboard,
    get_cancel_custom_keyboard,
    get_cancel_revision_keyboard,
    get_reschedule_keyboard,
    get_review_keyboard,
    get_schedule_keyboard,
)
from scheduler import cancel_post_job, publish_post, schedule_post_job
from utils import (
    format_author_tag,
    format_msk_datetime,
    parse_msk_time,
    update_user_status,
)

logger = logging.getLogger(__name__)
admin_router = Router(name="admin_router")
admin_router.message.filter(AdminChatFilter())
admin_router.callback_query.filter(AdminChatFilter())


class AdminStates(StatesGroup):
    waiting_for_custom_time = State()
    waiting_for_ban_reason = State()
    waiting_for_revision_comment = State()


def get_moderator_mention(user) -> str:
    if user.username:
        return f"@{user.username}"
    return user.full_name


async def apply_post_schedule(
    bot: Bot,
    db: Database,
    config: Config,
    scheduler: AsyncIOScheduler,
    post: dict[str, Any],
    target_time: datetime,
    moderator_user,
) -> str:
    post_id = post["id"]
    mod_name = get_moderator_mention(moderator_user)
    target_str = format_msk_datetime(target_time, config.timezone)
    is_resched = post.get("status") == "scheduled"

    await db.set_status(
        post_id=post_id,
        status="scheduled",
        moderator_id=moderator_user.id,
        moderator_name=mod_name,
        scheduled_at=target_time.isoformat(),
    )

    if scheduler:
        schedule_post_job(scheduler, bot, post_id, db, config, target_time)

    status_text = (
        f"⏳ <b>Время публикации вашего поста изменено на {target_str} МСК!</b>"
        if is_resched
        else f"⏳ <b>Ваш пост принят администрацией и будет опубликован в {target_str} МСК!</b>"
    )
    await update_user_status(
        bot=bot,
        user_id=post["user_id"],
        status_message_id=post.get("user_status_message_id"),
        reply_to_message_id=post["user_message_id"],
        text=status_text,
    )
    await db.mark_author_notified(post_id)
    return target_str


async def build_scheduled_list_view(db: Database, config: Config) -> tuple[str, InlineKeyboardMarkup | None]:
    scheduled_posts = await db.get_scheduled_posts()
    if not scheduled_posts:
        return "📭 <b>На данный момент нет запланированных публикаций.</b>", None

    lines = ["📅 <b>Очередь запланированных публикаций:</b>\n"]
    buttons = []

    for p in scheduled_posts:
        sched_time_str = format_msk_datetime(p["scheduled_at"], config.timezone)
        author = format_author_tag(p["user_name"], p["user_username"], p["user_id"])
        preview = (p["text"] or "").strip().replace("\n", " ")
        if len(preview) > 40:
            preview = preview[:40] + "..."
        snippet = f' — <i>«{html.escape(preview)}»</i>' if preview else ""
        lines.append(f"• <b>Пост #{p['id']}</b> на <b>{sched_time_str} МСК</b>\n  Автор: {author}{snippet}")
        buttons.append([
            InlineKeyboardButton(text=f"✏️ Время #{p['id']}", callback_data=f"resched:{p['id']}"),
            InlineKeyboardButton(text=f"❌ Отменить #{p['id']}", callback_data=f"cancel_sch:{p['id']}"),
        ])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    return "\n\n".join(lines), kb


@admin_router.callback_query(F.data.startswith("rev:rej:"))
async def reject_post_handler(
    callback: CallbackQuery,
    bot: Bot,
    db: Database,
    config: Config,
) -> None:
    post_id = int(callback.data.split(":")[2])
    post = await db.get_post(post_id)

    if not post:
        await callback.answer("❌ Заявка не найдена в базе данных.", show_alert=True)
        return

    if post["status"] == "published":
        await callback.answer("⚠️ Нельзя отклонить уже опубликованный пост!", show_alert=True)
        return

    mod_name = get_moderator_mention(callback.from_user)
    now_msk = datetime.now(config.timezone)
    now_str = format_msk_datetime(now_msk, config.timezone)

    await db.set_status(
        post_id=post_id,
        status="rejected",
        moderator_id=callback.from_user.id,
        moderator_name=mod_name,
    )

    await update_user_status(
        bot=bot,
        user_id=post["user_id"],
        status_message_id=post.get("user_status_message_id"),
        reply_to_message_id=post["user_message_id"],
        text="❌ <b>К сожалению, ваш пост был отклонён администраторами.</b>",
    )

    author_tag = format_author_tag(post["user_name"], post["user_username"], post["user_id"])
    new_card_text = (
        f"❌ <b>Пост #{post_id} отклонён</b>\n\n"
        f"👤 <b>Автор:</b> {author_tag}\n"
        f"👮‍♂️ <b>Модератор:</b> {mod_name}\n"
        f"🕒 <b>Время решения:</b> {now_str} МСК"
    )
    await callback.message.edit_text(new_card_text, reply_markup=None, parse_mode="HTML")
    await callback.answer("Пост отклонён. Автор уведомлен.")


@admin_router.callback_query(F.data.startswith("rev:rev:"))
async def revision_prompt_handler(
    callback: CallbackQuery,
    db: Database,
    state: FSMContext,
) -> None:
    post_id = int(callback.data.split(":")[2])
    post = await db.get_post(post_id)

    if not post:
        await callback.answer("❌ Заявка не найдена.", show_alert=True)
        return

    if post["status"] == "published":
        await callback.answer("⚠️ Нельзя отправить на доработку опубликованный пост!", show_alert=True)
        return

    await state.set_state(AdminStates.waiting_for_revision_comment)
    await state.update_data(
        post_id=post_id,
        author_id=post["user_id"],
        admin_message_id=callback.message.message_id,
    )

    prompt_text = (
        f"🔄 <b>Укажите замечания / что нужно доработать по посту #{post_id}:</b>\n\n"
        f"<i>Отправьте сообщение с комментарием или нажмите кнопку отмены ниже:</i>"
    )
    prompt_msg = await callback.message.reply(
        prompt_text,
        reply_markup=get_cancel_revision_keyboard(post_id),
        parse_mode="HTML",
    )
    await state.update_data(prompt_message_id=prompt_msg.message_id)
    await callback.answer()


@admin_router.callback_query(F.data.startswith("rev:cancel_rev:"))
async def cancel_revision_handler(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await state.clear()
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer("Отправка на доработку отменена.")


@admin_router.message(AdminStates.waiting_for_revision_comment, F.text)
async def process_revision_comment_input(
    message: Message,
    bot: Bot,
    db: Database,
    config: Config,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    post_id = data.get("post_id")
    admin_msg_id = data.get("admin_message_id")
    prompt_msg_id = data.get("prompt_message_id")

    if not post_id:
        await state.clear()
        return

    comment = message.text.strip()
    await state.clear()

    if prompt_msg_id:
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=prompt_msg_id)
        except Exception:
            pass

    post = await db.get_post(post_id)
    if not post:
        await message.reply(f"❌ Пост #{post_id} не найден.")
        return

    mod_name = get_moderator_mention(message.from_user)
    now_msk = datetime.now(config.timezone)
    now_str = format_msk_datetime(now_msk, config.timezone)

    await db.set_status(
        post_id=post_id,
        status="needs_revision",
        moderator_id=message.from_user.id,
        moderator_name=mod_name,
        revision_comment=comment,
    )

    user_text = (
        f"🔄 <b>Ваш предложенный пост отправлен на доработку.</b>\n\n"
        f"<b>Комментарий администрации:</b>\n"
        f"{html.escape(comment)}\n\n"
        f"<i>Вы можете исправить замечания и прислать пост заново в этот диалог.</i>"
    )
    await update_user_status(
        bot=bot,
        user_id=post["user_id"],
        status_message_id=post.get("user_status_message_id"),
        reply_to_message_id=post["user_message_id"],
        text=user_text,
    )

    author_tag = format_author_tag(post["user_name"], post["user_username"], post["user_id"])
    new_card_text = (
        f"🔄 <b>Пост #{post_id} отправлен на доработку</b>\n\n"
        f"👤 <b>Автор:</b> {author_tag}\n"
        f"👮‍♂️ <b>Модератор:</b> {mod_name}\n"
        f"📝 <b>Замечания:</b> {html.escape(comment)}\n"
        f"🕒 <b>Время:</b> {now_str} МСК"
    )
    if admin_msg_id:
        try:
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=admin_msg_id,
                text=new_card_text,
                reply_markup=None,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning(f"Failed to edit admin card: {e}")

    await message.reply(
        f"🔄 <b>Пост #{post_id} успешно отправлен автору на доработку!</b>",
        parse_mode="HTML",
    )


@admin_router.callback_query(F.data.startswith("rev:ban:"))
async def ban_author_prompt_handler(
    callback: CallbackQuery,
    db: Database,
    state: FSMContext,
) -> None:
    post_id = int(callback.data.split(":")[2])
    post = await db.get_post(post_id)

    if not post:
        await callback.answer("❌ Заявка не найдена.", show_alert=True)
        return

    await state.set_state(AdminStates.waiting_for_ban_reason)
    await state.update_data(
        post_id=post_id,
        author_id=post["user_id"],
        author_name=post["user_name"],
        author_username=post["user_username"],
        admin_message_id=callback.message.message_id,
    )

    prompt_text = (
        f"🚫 <b>Укажите причину блокировки для автора поста #{post_id}:</b>\n\n"
        f"<i>Отправьте сообщение с причиной или нажмите кнопку отмены ниже:</i>"
    )
    prompt_msg = await callback.message.reply(
        prompt_text,
        reply_markup=get_cancel_ban_keyboard(post_id),
        parse_mode="HTML",
    )
    await state.update_data(prompt_message_id=prompt_msg.message_id)
    await callback.answer()


@admin_router.callback_query(F.data.startswith("rev:cancel_ban:"))
async def cancel_ban_handler(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await state.clear()
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer("Блокировка отменена.")


@admin_router.message(AdminStates.waiting_for_ban_reason, F.text)
async def process_ban_reason_input(
    message: Message,
    bot: Bot,
    db: Database,
    config: Config,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    post_id = data.get("post_id")
    author_id = data.get("author_id")
    author_name = data.get("author_name")
    author_username = data.get("author_username")
    admin_msg_id = data.get("admin_message_id")
    prompt_msg_id = data.get("prompt_message_id")

    if not post_id or not author_id:
        await state.clear()
        return

    reason = message.text.strip()
    await state.clear()

    if prompt_msg_id:
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=prompt_msg_id)
        except Exception:
            pass

    now = datetime.now(config.timezone)
    now_iso = now.isoformat()
    now_str = format_msk_datetime(now, config.timezone)
    mod_name = get_moderator_mention(message.from_user)

    await db.ban_user(
        user_id=author_id,
        user_name=author_name,
        user_username=author_username,
        reason=reason,
        banned_by_id=message.from_user.id,
        banned_by_name=mod_name,
        banned_at=now_iso,
    )

    await db.set_status(
        post_id=post_id,
        status="rejected",
        moderator_id=message.from_user.id,
        moderator_name=mod_name,
    )

    post = await db.get_post(post_id)
    if post:
        await update_user_status(
            bot=bot,
            user_id=author_id,
            status_message_id=post.get("user_status_message_id"),
            reply_to_message_id=post["user_message_id"],
            text=(
                f"❌ <b>Ваш пост был отклонён, а вы заблокированы в предложке.</b>\n\n"
                f"<b>Причина блокировки:</b> {html.escape(reason)}"
            ),
        )

    author_tag = format_author_tag(author_name, author_username, author_id)
    new_card_text = (
        f"❌ <b>Пост #{post_id} отклонён, автор заблокирован</b>\n\n"
        f"👤 <b>Автор:</b> {author_tag}\n"
        f"👮‍♂️ <b>Модератор:</b> {mod_name}\n"
        f"📝 <b>Причина:</b> {html.escape(reason)}\n"
        f"🕒 <b>Время:</b> {now_str} МСК"
    )

    if admin_msg_id:
        try:
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=admin_msg_id,
                text=new_card_text,
                reply_markup=None,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning(f"Failed to edit admin card: {e}")

    await message.reply(
        f"🚫 <b>Пользователь {author_tag} успешно заблокирован!</b>",
        parse_mode="HTML",
    )


@admin_router.callback_query(F.data.startswith("rev:acc:"))
async def accept_post_handler(
    callback: CallbackQuery,
    db: Database,
) -> None:
    post_id = int(callback.data.split(":")[2])
    post = await db.get_post(post_id)

    if not post:
        await callback.answer("❌ Заявка не найдена в базе данных.", show_alert=True)
        return

    mod_name = get_moderator_mention(callback.from_user)

    await db.set_status(
        post_id=post_id,
        status="approved",
        moderator_id=callback.from_user.id,
        moderator_name=mod_name,
    )

    author_tag = format_author_tag(post["user_name"], post["user_username"], post["user_id"])
    card_text = (
        f"✅ <b>Пост #{post_id} одобрен к публикации</b>\n\n"
        f"👤 <b>Автор:</b> {author_tag}\n"
        f"👮‍♂️ <b>Модератор:</b> {mod_name}\n\n"
        f"⏳ <b>Выберите время отправки поста:</b>"
    )
    await callback.message.edit_text(
        card_text,
        reply_markup=get_schedule_keyboard(post_id),
        parse_mode="HTML",
    )
    await callback.answer("Пост принят. Выберите время публикации.")


@admin_router.callback_query(F.data.startswith("sch:back:"))
async def back_to_review_handler(
    callback: CallbackQuery,
    db: Database,
    config: Config,
) -> None:
    post_id = int(callback.data.split(":")[2])
    post = await db.get_post(post_id)

    if not post:
        await callback.answer("❌ Заявка не найдена в базе данных.", show_alert=True)
        return

    await db.set_status(post_id=post_id, status="pending")

    author_tag = format_author_tag(post["user_name"], post["user_username"], post["user_id"])
    created_str = format_msk_datetime(post["created_at"], config.timezone)
    card_text = (
        f"📋 <b>Заявка на публикацию #{post_id} (на повторном рассмотрении)</b>\n\n"
        f"👤 <b>Автор:</b> {author_tag} (ID: <code>{post['user_id']}</code>)\n"
        f"🕒 <b>Получено:</b> {created_str} МСК\n\n"
        f"<i>Выберите действие ниже:</i>"
    )
    await callback.message.edit_text(
        card_text,
        reply_markup=get_review_keyboard(post_id),
        parse_mode="HTML",
    )
    await callback.answer("Возврат к рассмотрению.")


@admin_router.callback_query(F.data.startswith("sch:now:"))
async def publish_now_handler(
    callback: CallbackQuery,
    bot: Bot,
    db: Database,
    config: Config,
) -> None:
    post_id = int(callback.data.split(":")[2])
    await callback.answer("Публикуем пост в канал...")
    success = await publish_post(bot, post_id, db, config)
    if not success:
        await callback.message.reply(f"⚠️ Ошибка при немедленной публикации поста #{post_id}.")


@admin_router.callback_query(F.data.startswith("sch:30m:"))
async def publish_in_30m_handler(
    callback: CallbackQuery,
    bot: Bot,
    db: Database,
    config: Config,
    scheduler: AsyncIOScheduler,
) -> None:
    post_id = int(callback.data.split(":")[2])
    post = await db.get_post(post_id)
    if not post:
        await callback.answer("❌ Заявка не найдена.", show_alert=True)
        return

    target_time = datetime.now(config.timezone) + timedelta(minutes=30)
    target_str = await apply_post_schedule(bot, db, config, scheduler, post, target_time, callback.from_user)

    author_tag = format_author_tag(post["user_name"], post["user_username"], post["user_id"])
    mod_name = get_moderator_mention(callback.from_user)
    card_text = (
        f"⏳ <b>Пост #{post_id} запланирован</b>\n\n"
        f"👤 <b>Автор:</b> {author_tag}\n"
        f"📅 <b>Время публикации:</b> {target_str} МСК (через 30 мин)\n"
        f"👮‍♂️ <b>Модератор:</b> {mod_name}"
    )
    await callback.message.edit_text(card_text, reply_markup=None, parse_mode="HTML")
    await callback.answer("Публикация запланирована через 30 минут.")


@admin_router.callback_query(F.data.startswith("sch:60m:"))
async def publish_in_1h_handler(
    callback: CallbackQuery,
    bot: Bot,
    db: Database,
    config: Config,
    scheduler: AsyncIOScheduler,
) -> None:
    post_id = int(callback.data.split(":")[2])
    post = await db.get_post(post_id)
    if not post:
        await callback.answer("❌ Заявка не найдена.", show_alert=True)
        return

    target_time = datetime.now(config.timezone) + timedelta(hours=1)
    target_str = await apply_post_schedule(bot, db, config, scheduler, post, target_time, callback.from_user)

    author_tag = format_author_tag(post["user_name"], post["user_username"], post["user_id"])
    mod_name = get_moderator_mention(callback.from_user)
    card_text = (
        f"⏳ <b>Пост #{post_id} запланирован</b>\n\n"
        f"👤 <b>Автор:</b> {author_tag}\n"
        f"📅 <b>Время публикации:</b> {target_str} МСК (через 1 час)\n"
        f"👮‍♂️ <b>Модератор:</b> {mod_name}"
    )
    await callback.message.edit_text(card_text, reply_markup=None, parse_mode="HTML")
    await callback.answer("Публикация запланирована через 1 час.")


@admin_router.callback_query(F.data.startswith("sch:custom:"))
async def publish_custom_prompt_handler(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    post_id = int(callback.data.split(":")[2])
    await state.set_state(AdminStates.waiting_for_custom_time)
    await state.update_data(
        post_id=post_id,
        admin_message_id=callback.message.message_id,
        admin_chat_id=callback.message.chat.id,
    )

    prompt_text = (
        f"📅 <b>Укажите время публикации для поста #{post_id} по МСК:</b>\n\n"
        f"<b>Примеры форматов:</b>\n"
        f"• <code>18:30</code> — публикация сегодня (или завтра, если время прошло)\n"
        f"• <code>28.10 14:00</code> — дата и время в текущем году\n"
        f"• <code>28.10.2026 14:00</code> — точная дата и время\n\n"
        f"<i>Отправьте сообщение с временем или нажмите кнопку отмены:</i>"
    )
    prompt_msg = await callback.message.reply(
        prompt_text,
        reply_markup=get_cancel_custom_keyboard(post_id),
        parse_mode="HTML",
    )
    await state.update_data(prompt_message_id=prompt_msg.message_id)
    await callback.answer()


@admin_router.callback_query(F.data.startswith("sch:cancel_custom:"))
async def cancel_custom_time_handler(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await state.clear()
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer("Ввод времени отменён.")


@admin_router.message(AdminStates.waiting_for_custom_time, F.text)
async def process_custom_time_input(
    message: Message,
    bot: Bot,
    db: Database,
    config: Config,
    state: FSMContext,
    scheduler: AsyncIOScheduler,
) -> None:
    data = await state.get_data()
    post_id = data.get("post_id")
    admin_msg_id = data.get("admin_message_id")
    prompt_msg_id = data.get("prompt_message_id")

    if not post_id:
        await state.clear()
        return

    target_time = parse_msk_time(message.text, config.timezone)
    if not target_time or target_time <= datetime.now(config.timezone):
        await message.reply(
            "⚠️ <b>Не удалось распознать время или указанное время уже прошло.</b>\n\n"
            "Пожалуйста, введите будущее время по МСК (например, <code>19:30</code> или <code>28.10 14:00</code>) "
            "или отмените ввод кнопкой выше.",
            parse_mode="HTML",
        )
        return

    await state.clear()

    if prompt_msg_id:
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=prompt_msg_id)
        except Exception:
            pass

    post = await db.get_post(post_id)
    if not post:
        await message.reply(f"❌ Пост #{post_id} не найден в базе.")
        return

    target_str = await apply_post_schedule(bot, db, config, scheduler, post, target_time, message.from_user)

    author_tag = format_author_tag(post["user_name"], post["user_username"], post["user_id"])
    mod_name = get_moderator_mention(message.from_user)
    new_card_text = (
        f"⏳ <b>Пост #{post_id} запланирован</b>\n\n"
        f"👤 <b>Автор:</b> {author_tag}\n"
        f"📅 <b>Время публикации:</b> {target_str} МСК\n"
        f"👮‍♂️ <b>Модератор:</b> {mod_name}"
    )

    if admin_msg_id:
        try:
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=admin_msg_id,
                text=new_card_text,
                reply_markup=None,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning(f"Failed to edit admin card: {e}")

    await message.reply(
        f"✅ <b>Публикация поста #{post_id} успешно запланирована на {target_str} МСК!</b>",
        parse_mode="HTML",
    )


@admin_router.message(Command("scheduled", "queue"))
async def admin_scheduled_list_handler(
    message: Message,
    db: Database,
    config: Config,
) -> None:
    text, kb = await build_scheduled_list_view(db, config)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@admin_router.callback_query(F.data == "back_to_queue")
async def back_to_queue_callback(
    callback: CallbackQuery,
    db: Database,
    config: Config,
) -> None:
    text, kb = await build_scheduled_list_view(db, config)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@admin_router.callback_query(F.data.startswith("resched:"))
async def reschedule_post_prompt(
    callback: CallbackQuery,
    db: Database,
    config: Config,
) -> None:
    post_id = int(callback.data.split(":")[1])
    post = await db.get_post(post_id)
    if not post or post["status"] != "scheduled":
        await callback.answer("Этот пост уже не находится в очереди.", show_alert=True)
        return

    author_tag = format_author_tag(post["user_name"], post["user_username"], post["user_id"])
    curr_time = format_msk_datetime(post["scheduled_at"], config.timezone)
    card_text = (
        f"✏️ <b>Изменение времени для поста #{post_id}</b>\n\n"
        f"👤 <b>Автор:</b> {author_tag}\n"
        f"🕒 <b>Текущее время:</b> {curr_time} МСК\n\n"
        f"⏳ <b>Выберите новое время публикации:</b>"
    )
    await callback.message.edit_text(
        card_text,
        reply_markup=get_reschedule_keyboard(post_id),
        parse_mode="HTML",
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("cancel_sch:"))
async def cancel_scheduled_callback(
    callback: CallbackQuery,
    bot: Bot,
    db: Database,
    scheduler: AsyncIOScheduler,
) -> None:
    post_id = int(callback.data.split(":")[1])
    post = await db.get_post(post_id)

    if not post or post["status"] != "scheduled":
        await callback.answer("Этот пост уже не находится в очереди.", show_alert=True)
        return

    cancel_post_job(scheduler, post_id)
    await db.cancel_scheduled_post(post_id)

    await update_user_status(
        bot=bot,
        user_id=post["user_id"],
        status_message_id=post.get("user_status_message_id"),
        reply_to_message_id=post["user_message_id"],
        text="⚠️ <b>Запланированная публикация вашего поста была отменена администрацией.</b>",
    )

    admin_chat_id = post.get("admin_chat_id")
    admin_msg_id = post.get("admin_message_id")
    if admin_chat_id and admin_msg_id:
        try:
            author_tag = format_author_tag(post["user_name"], post["user_username"], post["user_id"])
            card_text = (
                f"⚠️ <b>Публикация поста #{post_id} была отменена</b>\n\n"
                f"👤 <b>Автор:</b> {author_tag}\n\n"
                f"⏳ <b>Выберите новое время отправки поста:</b>"
            )
            await bot.edit_message_text(
                chat_id=admin_chat_id,
                message_id=admin_msg_id,
                text=card_text,
                reply_markup=get_schedule_keyboard(post_id),
                parse_mode="HTML",
            )
        except Exception:
            pass

    await callback.answer(f"Публикация поста #{post_id} отменена.")
    await callback.message.edit_text(
        f"✅ <b>Публикация поста #{post_id} успешно отменена модератором {get_moderator_mention(callback.from_user)}.</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад к очереди", callback_data="back_to_queue")]]),
        parse_mode="HTML",
    )


@admin_router.message(Command("banned", "banlist"))
async def admin_banned_list_handler(
    message: Message,
    db: Database,
    config: Config,
) -> None:
    banned_users = await db.get_banned_users()
    if not banned_users:
        await message.answer("🟢 <b>Список заблокированных пользователей пуст.</b>", parse_mode="HTML")
        return

    lines = ["🚫 <b>Список заблокированных пользователей:</b>\n"]
    buttons = []

    for u in banned_users:
        banned_at_str = format_msk_datetime(u["banned_at"], config.timezone)
        username_str = f" (@{u['user_username']})" if u["user_username"] else ""
        lines.append(
            f"• <b>{html.escape(u['user_name'])}</b>{username_str}\n"
            f"  ID: <code>{u['user_id']}</code>\n"
            f"  Причина: <i>{html.escape(u['reason'])}</i>\n"
            f"  Модератор: {u['banned_by_name']}\n"
            f"  Дата: {banned_at_str} МСК"
        )
        display_name = f"@{u['user_username']}" if u["user_username"] else str(u["user_id"])
        buttons.append([InlineKeyboardButton(text=f"🔓 Разблокировать {display_name}", callback_data=f"unban:{u['user_id']}")])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("\n\n".join(lines), reply_markup=kb, parse_mode="HTML")


@admin_router.callback_query(F.data.startswith("unban:"))
async def unban_user_callback(
    callback: CallbackQuery,
    db: Database,
) -> None:
    user_id = int(callback.data.split(":")[1])
    unbanned = await db.unban_user(user_id)

    if unbanned:
        await callback.answer(f"Пользователь {user_id} разблокирован!")
        await callback.message.reply(
            f"✅ <b>Пользователь с ID <code>{user_id}</code> успешно разблокирован модератором {get_moderator_mention(callback.from_user)}.</b>",
            parse_mode="HTML",
        )
    else:
        await callback.answer("Пользователь не найден в списке заблокированных.", show_alert=True)


@admin_router.message(Command("unban"))
async def admin_unban_command_handler(
    message: Message,
    db: Database,
) -> None:
    args = message.text.split()
    if len(args) < 2:
        await message.reply("⚠️ Использование: <code>/unban &lt;user_id&gt;</code>", parse_mode="HTML")
        return

    try:
        user_id = int(args[1])
    except ValueError:
        await message.reply("⚠️ Неверный формат ID. Должно быть число.", parse_mode="HTML")
        return

    unbanned = await db.unban_user(user_id)
    if unbanned:
        await message.reply(f"✅ <b>Пользователь с ID <code>{user_id}</code> успешно разблокирован.</b>", parse_mode="HTML")
    else:
        await message.reply(f"⚠️ Пользователь с ID <code>{user_id}</code> не найден в списке заблокированных.", parse_mode="HTML")


@admin_router.message(Command("stats"))
async def admin_stats_handler(
    message: Message,
    db: Database,
) -> None:
    stats = await db.get_stats()
    banned_count = len(await db.get_banned_users())
    text = (
        "📊 <b>Статистика предложенных постов:</b>\n\n"
        f"⏳ На рассмотрении: <b>{stats.get('pending', 0)}</b>\n"
        f"👍 Одобрено (ожидают времени): <b>{stats.get('approved', 0)}</b>\n"
        f"📅 Запланировано к выходу: <b>{stats.get('scheduled', 0)}</b>\n"
        f"🚀 Опубликовано в канале: <b>{stats.get('published', 0)}</b>\n"
        f"❌ Отклонено: <b>{stats.get('rejected', 0)}</b>\n"
        f"🚫 Заблокировано пользователей: <b>{banned_count}</b>"
    )
    await message.answer(text, parse_mode="HTML")


@admin_router.message(Command("help"))
async def admin_help_handler(
    message: Message,
) -> None:
    text = (
        "📖 <b>Команды управления предложкой:</b>\n\n"
        "• <code>/scheduled</code> (или <code>/queue</code>) — список всех запланированных постов с возможностью отмены\n"
        "• <code>/banned</code> (или <code>/banlist</code>) — список заблокированных пользователей с кнопками разблокировки\n"
        "• <code>/unban &lt;user_id&gt;</code> — разблокировать пользователя по его числовому ID\n"
        "• <code>/stats</code> — статистика предложенных постов и блокировок\n"
        "• <code>/help</code> — справка по командам бота"
    )
    await message.answer(text, parse_mode="HTML")
