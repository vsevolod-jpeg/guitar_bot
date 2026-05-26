import asyncio
import sqlite3
import logging
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ChatMember
from aiogram.filters import CommandStart, Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# ─────────────────────────────────────────────
# НАСТРОЙКИ — замените перед запуском
# ─────────────────────────────────────────────
BOT_TOKEN = "8881070793:AAGyUlmz-sWV98JCpiRs0bzUfZZzDrU1NY0"

VIDEO_IDS = {
    0: "BAACAgIAAxkBAAMUahWLKIzFFMnrCYqgeZIbZ3ubd2EAAn-bAAKwAqlIWt6bZME7kKU7BA",
    1: "BAACAgIAAxkBAAMgahWdWyGoeyaiffTuv1ja0Tut3YAAAqmbAAKqgbFIKFKTMeo3dAABOwQ",
    2: "BAACAgIAAxkBAAMiahWeG1mzqg4xnuHDU6xhmFLzl4oAArebAAKqgbFIk2hofloI9Q47BA",
    3: "BAACAgIAAxkBAAMkahWf9VjSCHEZCVxHW0IMM3cIHQQAAuSbAAKqgbFIzC7S301GHqI7BA",
}

# Фото
PHOTO_WELCOME    = "AgACAgIAAxkBAANEahW1iaIxp_1jvfgTjJJ1ubs_j-AAAlQdaxuwAqlIxLCHxoLyYoABAAMCAAN3AAM7BA"
PHOTO_LESSON_1   = "AgACAgIAAxkBAANNahW2ZPREYnk1U2SUwey8FBVMOzUAAlgdaxuwAqlIYjb8KU8XvYsBAAMCAAN4AAM7BA"
PHOTO_LESSON_2   = "AgACAgIAAxkBAANNahW2ZPREYnk1U2SUwey8FBVMOzUAAlgdaxuwAqlIYjb8KU8XvYsBAAMCAAN4AAM7BA"

CONTACT_LINK = "https://t.me/tajiiiikkkk"
ADMIN_ID = 806817338
CHANNEL_USERNAME = "@vsevolod_gitara"

# ─────────────────────────────────────────────

logging.basicConfig(level=logging.INFO)

# ─── Данные уроков ────────────────────────────
LESSONS = [
    {
        "callback": "lesson_0",
        "button_label": "🎸 Настройка гитары",
        "text": (
            "Первый шаг — настроить инструмент. "
            "Без этого звук будет грязным, а учиться — некомфортно. "
            "Смотри видео и повторяй."
        ),
        "photo": None,
    },
    {
        "callback": "lesson_1",
        "button_label": "🪑 Посадка и постановка рук",
        "text": (
            "Теперь поставим руки, чтобы играть было удобно. "
            "Не пропускай этот шаг — от него зависит твой прогресс."
        ),
        "photo": PHOTO_LESSON_1,
    },
    {
        "callback": "lesson_2",
        "button_label": "🎸 Первые 4 аккорда + бой",
        "text": (
            "Самый важный урок. Эти 4 аккорда откроют тебе сотни песен. "
            "Смотри, повторяй и тренируй перестановки."
        ),
        "photo": PHOTO_LESSON_2,
    },
    {
        "callback": "lesson_3",
        "button_label": "🎵 Вторая песня + акценты в ритме",
        "text": (
            "Поздравляю, ты дошел до финала! "
            "Теперь ты сыграешь вторую песню и научишься делать ритм живым и интересным."
        ),
        "photo": None,
    },
]

FINAL_TEXT = (
    "🎉 Ты прошел курс! Как тебе твой прогресс?\n\n"
    "Хочешь играть любимые песни, а не просто повторять уроки? "
    "Давай прокачиваться дальше! "
    "Записывайся на пробное занятие. Я помогу тебе достичь твоей цели."
)

# ─── База данных ──────────────────────────────
def init_db():
    conn = sqlite3.connect("progress.db")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_progress (
            user_id INTEGER PRIMARY KEY,
            last_lesson INTEGER DEFAULT -1
        )
        """
    )
    conn.commit()
    conn.close()


def get_progress(user_id: int) -> int:
    conn = sqlite3.connect("progress.db")
    row = conn.execute(
        "SELECT last_lesson FROM user_progress WHERE user_id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return row[0] if row else -1


def set_progress(user_id: int, lesson_index: int):
    conn = sqlite3.connect("progress.db")
    conn.execute(
        """
        INSERT INTO user_progress (user_id, last_lesson)
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET last_lesson = excluded.last_lesson
        """,
        (user_id, lesson_index),
    )
    conn.commit()
    conn.close()


def reset_progress(user_id: int):
    conn = sqlite3.connect("progress.db")
    conn.execute("DELETE FROM user_progress WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


# ─── Клавиатуры ──────────────────────────────
def lesson_keyboard(lesson_index: int) -> InlineKeyboardMarkup:
    lesson = LESSONS[lesson_index]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=lesson["button_label"], callback_data=lesson["callback"])]
        ]
    )


def final_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Записаться на пробный урок", url=CONTACT_LINK)]
        ]
    )


def subscribe_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📢 Подписаться на канал", url=f"https://t.me/vsevolod_gitara")],
            [InlineKeyboardButton(text="✅ Я подписался", callback_data="check_subscription")],
        ]
    )


# ─── Проверка подписки (исправленная версия) ───
async def is_subscribed(bot: Bot, user_id: int) -> bool:
    """
    Проверяет, подписан ли пользователь на канал.
    Отправляет владельцу (тебе) диагностическое сообщение при ошибке.
    """
    try:
        # Пытаемся получить информацию о пользователе в канале
        member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        
        # Пишем в консоль (логи bothost.ru), что мы получили от Telegram
        print(f"DEBUG: Статус пользователя {user_id}: {member.status}")
        
        # Проверяем статус
        if member.status in ("member", "creator", "administrator"):
            return True
        else:
            # Отправляем диагностику ТЕБЕ (владельцу)
            await bot.send_message(
                chat_id=YOUR_USER_ID,  # ТВОЙ ID
                text=f"❌ Пользователь {user_id} не подписан. Его статус: {member.status}"
            )
            return False
    except Exception as e:
        # Если произошла ошибка, пишем в консоль и отправляем тебе
        error_text = f"🚨 ОШИБКА проверки для {user_id}: {e}"
        print(error_text)
        await bot.send_message(chat_id=YOUR_USER_ID, text=error_text)
        return False


# ─── Функция отправки стартового сообщения ───
async def send_start_message(target, user_id: int):
    progress = get_progress(user_id)
    
    if progress == -1:
        await target.answer_photo(
            photo=PHOTO_WELCOME,
            caption=(
                "Привет! Я Всеволод, преподаватель гитары. Я провел больше 1500 уроков и вложил свои навыки в мини курс.\n\n"
                "Этот курс поможет тебе легко начать играть на гитаре с нуля. "
                "Начнём с самого важного — с настройки инструмента."
            ),
            reply_markup=lesson_keyboard(0),
        )
    elif progress < len(LESSONS) - 1:
        next_lesson = progress + 1
        await target.answer(
            f"С возвращением! Продолжаем с урока {next_lesson + 1}.",
            reply_markup=lesson_keyboard(next_lesson),
        )
    else:
        await target.answer(
            "Ты уже прошёл весь курс! 🎉\n\nНапиши мне, чтобы продолжить обучение:",
            reply_markup=final_keyboard(),
        )


# ─── Роутер ──────────────────────────────────
router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    
    if await is_subscribed(message.bot, user_id):
        await send_start_message(message, user_id)
    else:
        await message.answer(
            "👋 Привет!\n\n"
            "Чтобы получить бесплатный курс, подпишись на мой канал — там я делюсь уроками и советами по гитаре.\n\n"
            "После подписки нажми кнопку «✅ Я подписался».",
            reply_markup=subscribe_keyboard(),
        )


@router.message(Command("restart"))
async def cmd_restart(message: Message):
    user_id = message.from_user.id
    
    if not await is_subscribed(message.bot, user_id):
        await message.answer(
            "👋 Чтобы получить курс, подпишись на мой канал.",
            reply_markup=subscribe_keyboard(),
        )
        return
    
    reset_progress(user_id)
    
    await message.answer_photo(
        photo=PHOTO_WELCOME,
        caption=(
            "🔄 Начинаем сначала! 🎸\n\n"
            "Я Всеволод, преподаватель гитары. Я провел больше 1500 уроков и вложил свои навыки в мини курс.\n\n"
            "Этот курс поможет тебе легко начать играть на гитаре с нуля. "
            "Начнём с самого важного — с настройки инструмента."
        ),
        reply_markup=lesson_keyboard(0),
    )


@router.callback_query(F.data == "check_subscription")
async def check_sub_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if not await is_subscribed(callback.bot, user_id):
        await callback.answer("❌ Ты ещё не подписан. Подпишись и нажми кнопку снова.", show_alert=True)
        return
    
    await callback.answer("✅ Подписка подтверждена! Загружаю курс...", show_alert=False)
    
    try:
        await callback.message.delete()
    except Exception:
        pass
    
    await send_start_message(callback.message, user_id)


@router.callback_query(F.data.startswith("lesson_"))
async def handle_lesson(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if not await is_subscribed(callback.bot, user_id):
        await callback.answer("❌ Сначала подпишись на канал!", show_alert=True)
        return
    
    lesson_index = int(callback.data.split("_")[1])
    progress = get_progress(user_id)
    
    if lesson_index > progress + 1:
        await callback.answer("Сначала посмотри предыдущие уроки.", show_alert=True)
        return
    
    lesson = LESSONS[lesson_index]
    video_id = VIDEO_IDS[lesson_index]
    
    if lesson["photo"]:
        await callback.message.answer_photo(
            photo=lesson["photo"],
            caption=lesson["text"],
        )
    else:
        await callback.message.answer(lesson["text"])
    
    await callback.message.answer_video(video=video_id)
    
    if lesson_index > progress:
        set_progress(user_id, lesson_index)
    
    if lesson_index < len(LESSONS) - 1:
        next_index = lesson_index + 1
        await callback.message.answer(
            "Готов к следующему уроку?",
            reply_markup=lesson_keyboard(next_index),
        )
    else:
        await callback.message.answer(FINAL_TEXT, reply_markup=final_keyboard())
    
    await callback.answer()


# ─── Получение file_id (только для админа) ────
@router.message(F.video)
async def get_video_id(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    file_id = message.video.file_id
    await message.answer(f"📋 <code>{file_id}</code>")


@router.message(F.photo)
async def get_photo_id(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    file_id = message.photo[-1].file_id
    await message.answer(f"📋 <code>{file_id}</code>")


# ─── Запуск ───────────────────────────────────
async def main():
    init_db()
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
