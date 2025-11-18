import os
import logging


from dotenv import load_dotenv
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    ContextTypes,
    ApplicationBuilder,
    MessageHandler,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    filters,
)
from utils import MusicEducation as education, Replies as replies
from database import Profile, async_session_maker


logging.basicConfig(
    filename="bot.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(module)s - %(message)s",
)


load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

MAIN, NAME, FACULTY, COURSE, EDUCATION, DESC, LINK, LIKE = range(8)


async def get_profile(id: int):
    async with async_session_maker() as session:
        return (
            await session.execute(select(Profile).where(Profile.id == id))
        ).scalar_one_or_none()


async def get_random_profile(exclude_id: int = None):
    async with async_session_maker() as session:
        if (
            await session.execute(select(func.count()).select_from(Profile))
        ).scalar() <= 1:
            return None
        stmt = select(Profile).order_by(func.random()).limit(1)
        if exclude_id:
            stmt = stmt.where(Profile.id != exclude_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


async def check_enity_exists(id: int):
    async with async_session_maker() as session:
        return await session.get(Profile, id) is not None


async def view_profile(update: Update):
    user_profile = await get_profile(update.effective_chat.id)
    await update.message.reply_text(
        str(user_profile), reply_markup=replies.MAIN_MARKUP.value
    )
    return MAIN


async def view_musician(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session_maker() as session:
        user_profile: Profile = await session.get(
            Profile,
            update.effective_chat.id,
            options=[
                selectinload(Profile.likes),
            ],
        )
        count: Profile = await session.scalar(func.count(Profile.id))
    musician = await get_random_profile(exclude_id=update.effective_chat.id)
    if musician is None or len(user_profile.likes) == count - 1:
        await update.message.reply_text(
            "Профилей пока нет", reply_markup=replies.MAIN_MARKUP.value
        )
        return MAIN
    if musician in user_profile.likes:
        return await view_musician(exclude_id=update.effective_chat.id)

    context.user_data["profile_id"] = musician.id
    await update.message.reply_text(
        str(musician), reply_markup=replies.LIKE_MARKUP.value
    )

    return LIKE


async def main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message

    match message.text:
        case replies.PROFILE.value:
            return await view_profile(update=update)
        case replies.EDIT.value:
            await update.message.reply_text("Введи имя:")
            return NAME
        case replies.VIEW.value:
            return await view_musician(update=update, context=context)
        case replies.INFO.value:
            await update.message.reply_text(replies.MAN.value, parse_mode="HTML")
            return MAIN

    return await default(update=update, context=context)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_enity_exists(id=update.effective_chat.id):
        await update.message.reply_text(
            "Выбери действие:", reply_markup=replies.MAIN_MARKUP.value
        )
        return MAIN

    await update.message.reply_text(replies.START.value)
    return NAME


async def name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data[NAME] = update.message.text
    await update.message.reply_text(replies.FACULTY.value)
    return FACULTY


async def faculty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data[FACULTY] = update.message.text
    await update.message.reply_text(replies.COURSE.value)
    return COURSE


async def course(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data[COURSE] = int(update.message.text)
    except ValueError:
        await update.message.reply_text(replies.COURSE.value)
        return COURSE

    keyboard = [
        [InlineKeyboardButton(member.value, callback_data=member.name)]
        for member in education.__members__.values()
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(replies.EDUCATION.value, reply_markup=reply_markup)
    return EDUCATION


async def edu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data[EDUCATION] = education[query.data]
    await query.edit_message_text(replies.DESC.value)
    return DESC


async def desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data[DESC] = update.message.text
    await update.message.reply_text(replies.LINK.value)
    return LINK


async def link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data[LINK] = update.message.text

    async with async_session_maker() as session:
        profile: Profile | None = await session.get(Profile, update.effective_chat.id)

        if profile is None:
            profile = Profile(
                id=update.effective_chat.id,
                username=f"@{update.effective_user.username}",
                name=context.user_data[NAME],
                faculty=context.user_data[FACULTY],
                course=context.user_data[COURSE],
                education=context.user_data[EDUCATION],
                desc=context.user_data[DESC],
                link=context.user_data[LINK],
            )
            session.add(profile)
        else:
            profile.name = context.user_data[NAME]
            profile.faculty = context.user_data[FACULTY]
            profile.course = context.user_data[COURSE]
            profile.education = context.user_data[EDUCATION]
            profile.desc = context.user_data[DESC]
            profile.link = context.user_data[LINK]

        await session.commit()
        await session.refresh(profile)

    context.user_data["user_profile"] = profile
    await update.message.reply_text("Профиль сохранен")
    await update.message.reply_text(
        str(profile), reply_markup=replies.MAIN_MARKUP.value
    )
    return MAIN


async def like(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session_maker() as session:
        match update.message.text:
            case replies.LIKE.value:
                user_profile: Profile = await session.get(
                    Profile,
                    update.effective_chat.id,
                    options=[
                        selectinload(Profile.likes),
                        selectinload(Profile.liked_by),
                    ],
                )
                liked_profile: Profile = await session.get(
                    Profile,
                    context.user_data["profile_id"],
                    options=[
                        selectinload(Profile.likes),
                        selectinload(Profile.liked_by),
                    ],
                )

                liked_by = f"Твой профиль понравился\n{str(user_profile)}"
                greeting = "Начинай общаться 👉"

                if liked_profile in user_profile.liked_by:
                    user_profile.likes.append(liked_profile)
                    await session.commit()
                    await context.bot.send_message(
                        chat_id=liked_profile.id,
                        text=f"{liked_by}\n{greeting}{user_profile.username}",
                        reply_markup=replies.CONTINUE_MARKUP.value,
                    )
                    await update.message.reply_text(
                        f"{greeting}{liked_profile.username}"
                    )
                elif liked_profile not in user_profile.likes:
                    user_profile.likes.append(liked_profile)
                    await session.commit()
                    await context.bot.send_message(
                        chat_id=liked_profile.id,
                        text=liked_by,
                        reply_markup=replies.CONTINUE_WATCHING_MARKUP.value,
                    )

                return await view_musician(update=update, context=context)

            case replies.DISLIKE.value:
                return await view_musician(update=update, context=context)

            case replies.PROFILE.value:
                return await view_profile(update=update)

    return await default(update=update, context=context)


async def default(update: Update, context: ContextTypes.DEFAULT_TYPE):
    match update.message.text:
        case replies.CONTINUE.value:
            return await view_musician(update=update, context=context)
        case replies.CONTINUE_WATCHING.value:
            async with async_session_maker() as session:
                user_profile: Profile = await session.get(
                    Profile,
                    update.effective_chat.id,
                    options=[selectinload(Profile.liked_by)],
                )
                profile = user_profile.liked_by[0]
                context.user_data["profile_id"] = profile.id
                await update.message.reply_text(
                    str(profile), reply_markup=replies.LIKE_MARKUP.value
                )

                return LIKE


def run_bot():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MAIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, main)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name)],
            FACULTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, faculty)],
            COURSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, course)],
            EDUCATION: [CallbackQueryHandler(edu)],
            DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, desc)],
            LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, link)],
            LIKE: [MessageHandler(filters.TEXT & ~filters.COMMAND, like)],
        },
        fallbacks=[],
    )

    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, default))

    app.run_polling()


if __name__ == "__main__":
    run_bot()
