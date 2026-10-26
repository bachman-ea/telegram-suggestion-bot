import asyncio
import html
import json
import logging
import re
from datetime import datetime
from aiogram import Bot
from aiogram.types import (
    InputMediaAudio,
    InputMediaDocument,
    InputMediaPhoto,
    InputMediaVideo,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import Config
from database import Database
from utils import append_author_tag, format_author_tag, update_user_status

logger = logging.getLogger(__name__)


def fit_media_caption(text: str | None, author_tag: str, max_length: int = 1024) -> str:
    needed = len(author_tag) + 2
    if not text or not text.strip():
        return author_tag
    clean = text.strip()
    if len(clean) + needed <= max_length:
        return f"{clean}\n\n{author_tag}"

    available = max_length - needed - 3
    if available <= 0:
        return author_tag[:max_length]

    if "<" not in clean and ">" not in clean:
        return f"{clean[:available].rstrip()}...\n\n{author_tag}"

    plain = re.sub(r"<[^>]+>", "", clean)
    if len(plain) + needed <= max_length:
        return f"{clean}\n\n{author_tag}"

    truncated = html.escape(plain[:available].rstrip()) + "..."
    return f"{truncated}\n\n{author_tag}"


async def publish_post(bot: Bot, post_id: int, db: Database, config: Config) -> bool:
    post = await db.get_post(post_id)
    if not post:
        logger.error(f"Post #{post_id} not found in DB")
        return False

    if post["status"] == "published":
        return True

    author_tag = format_author_tag(
        user_name=post["user_name"],
        user_username=post["user_username"],
        user_id=post["user_id"],
    )

    post_type = post["post_type"]
    raw_text = post["text"]
    now_msk = datetime.now(config.timezone)

    try:
        if post_type == "text":
            final_text = append_author_tag(raw_text, author_tag)
            await bot.send_message(
                chat_id=config.channel_id,
                text=final_text,
                parse_mode="HTML",
            )

        elif post_type == "photo":
            media = json.loads(post["media_data"])
            caption = fit_media_caption(raw_text, author_tag)
            await bot.send_photo(
                chat_id=config.channel_id,
                photo=media["file_id"],
                caption=caption,
                parse_mode="HTML",
            )

        elif post_type == "video":
            media = json.loads(post["media_data"])
            caption = fit_media_caption(raw_text, author_tag)
            await bot.send_video(
                chat_id=config.channel_id,
                video=media["file_id"],
                caption=caption,
                parse_mode="HTML",
            )

        elif post_type == "animation":
            media = json.loads(post["media_data"])
            caption = fit_media_caption(raw_text, author_tag)
            await bot.send_animation(
                chat_id=config.channel_id,
                animation=media["file_id"],
                caption=caption,
                parse_mode="HTML",
            )

        elif post_type == "document":
            media = json.loads(post["media_data"])
            caption = fit_media_caption(raw_text, author_tag)
            await bot.send_document(
                chat_id=config.channel_id,
                document=media["file_id"],
                caption=caption,
                parse_mode="HTML",
            )

        elif post_type == "audio":
            media = json.loads(post["media_data"])
            caption = fit_media_caption(raw_text, author_tag)
            await bot.send_audio(
                chat_id=config.channel_id,
                audio=media["file_id"],
                caption=caption,
                parse_mode="HTML",
            )

        elif post_type == "voice":
            media = json.loads(post["media_data"])
            caption = fit_media_caption(raw_text, author_tag)
            await bot.send_voice(
                chat_id=config.channel_id,
                voice=media["file_id"],
                caption=caption,
                parse_mode="HTML",
            )

        elif post_type == "media_group":
            items = json.loads(post["media_data"])
            caption = fit_media_caption(raw_text, author_tag)
            media_group = []

            for idx, item in enumerate(items):
                item_caption = caption if idx == 0 else None
                item_pm = "HTML" if item_caption else None

                if item["type"] == "photo":
                    media_group.append(
                        InputMediaPhoto(
                            media=item["file_id"],
                            caption=item_caption,
                            parse_mode=item_pm,
                        )
                    )
                elif item["type"] == "video":
                    media_group.append(
                        InputMediaVideo(
                            media=item["file_id"],
                            caption=item_caption,
                            parse_mode=item_pm,
                        )
                    )
                elif item["type"] == "audio":
                    media_group.append(
                        InputMediaAudio(
                            media=item["file_id"],
                            caption=item_caption,
                            parse_mode=item_pm,
                        )
                    )
                elif item["type"] == "document":
                    media_group.append(
                        InputMediaDocument(
                            media=item["file_id"],
                            caption=item_caption,
                            parse_mode=item_pm,
                        )
                    )

            await bot.send_media_group(
                chat_id=config.channel_id,
                media=media_group,
            )

        logger.info(f"Post #{post_id} published to {config.channel_id}")

    except Exception as e:
        logger.error(f"Failed to publish post #{post_id}: {e}", exc_info=True)
        return False

    await db.set_status(
        post_id=post_id,
        status="published",
        published_at=now_msk.isoformat(),
    )

    await update_user_status(
        bot=bot,
        user_id=post["user_id"],
        status_message_id=post.get("user_status_message_id"),
        reply_to_message_id=post["user_message_id"],
        text="🎉 <b>Ваш пост был опубликован в канале!</b>",
    )

    admin_chat_id = post.get("admin_chat_id")
    admin_msg_id = post.get("admin_message_id")
    if admin_chat_id and admin_msg_id:
        try:
            pub_time_str = now_msk.strftime("%d.%m.%Y %H:%M")
            mod_name = post.get("moderator_name") or "Администратор"
            new_text = (
                f"🚀 <b>Пост #{post_id} опубликован в канале!</b>\n\n"
                f"👤 <b>Автор:</b> {author_tag}\n"
                f"👮‍♂️ <b>Модератор:</b> {mod_name}\n"
                f"🕒 <b>Опубликован:</b> {pub_time_str} МСК"
            )
            await bot.edit_message_text(
                chat_id=admin_chat_id,
                message_id=admin_msg_id,
                text=new_text,
                reply_markup=None,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning(f"Could not update admin message for post #{post_id}: {e}")

    return True


def schedule_post_job(
    scheduler: AsyncIOScheduler,
    bot: Bot,
    post_id: int,
    db: Database,
    config: Config,
    run_date: datetime,
) -> None:
    scheduler.add_job(
        publish_post,
        trigger="date",
        run_date=run_date,
        args=[bot, post_id, db, config],
        id=f"post_{post_id}",
        replace_existing=True,
    )
    logger.info(f"Scheduled post #{post_id} for {run_date}")


def cancel_post_job(scheduler: AsyncIOScheduler, post_id: int) -> None:
    job_id = f"post_{post_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        logger.info(f"Canceled schedule for post #{post_id}")


async def restore_scheduled_jobs(
    scheduler: AsyncIOScheduler,
    bot: Bot,
    db: Database,
    config: Config,
) -> None:
    scheduled_posts = await db.get_scheduled_posts()
    now = datetime.now(config.timezone)

    for post in scheduled_posts:
        sched_raw = post.get("scheduled_at")
        if not sched_raw:
            continue

        try:
            sched_dt = datetime.fromisoformat(sched_raw)
            if sched_dt.tzinfo is None:
                sched_dt = sched_dt.replace(tzinfo=config.timezone)

            if sched_dt <= now:
                asyncio.create_task(publish_post(bot, post["id"], db, config))
            else:
                schedule_post_job(scheduler, bot, post["id"], db, config, sched_dt)
        except Exception as e:
            logger.error(f"Error restoring schedule for post #{post['id']}: {e}")
