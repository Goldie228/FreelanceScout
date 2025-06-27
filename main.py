import logging
import sys
import asyncio
import os
from os import getenv
from dotenv import load_dotenv
import signal

from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.types import InlineKeyboardButton, ReplyKeyboardMarkup, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import CallbackQuery

from src import REDIS_CLIENT, REDIS_CLIENT_ASYNCIO
from src import ApplicationParser
from src import NotificationService
from src import Database

load_dotenv()
TOKEN = getenv("BOT_TOKEN")
ADMIN_USERNAME = getenv("ADMIN_USERNAME")

dp = Dispatcher()
db = Database()
redis_client = REDIS_CLIENT
redis_client_asyncio = REDIS_CLIENT_ASYNCIO

application_parser = ApplicationParser(redis_client)

@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    chat_id = str(message.from_user.id)
    user = db.get_user(chat_id)
    
    if user is None:
        default_keywords = ""
        db.add_user(
            chat_id,
            keywords=default_keywords,
            mailing_kwork=True,
            mailing_fl=True,
            mailing_freelancer=True
        )

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⚙️ Настройки")],
            [KeyboardButton(text="❓ Помощь")]
        ],
        resize_keyboard=True
    )
    await message.answer(
        f"👋 Добро пожаловать, {html.bold(message.from_user.full_name)}!\n\n"
        "Я - ваш персональный помощник для отслеживания новых проектов на фриланс-платформах.\n\n"
        "📌 Что я умею:\n"
        "• Автоматически отслеживать новые проекты на Kwork.ru, FL.ru и Freelancer.com\n"
        "• Присылать вам уведомления о проектах по вашим ключевым словам\n"
        "• Позволять гибко настраивать параметры уведомлений\n\n"
        "⚡ Чтобы начать работу:\n"
        "1. Перейдите в ⚙️ Настройки\n"
        "2. Укажите ключевые слова для фильтрации\n"
        "3. Выберите платформы, которые хотите отслеживать\n\n"
        "❓ Подробная инструкция доступна по команде /help",
        reply_markup=get_main_keyboard(),
        parse_mode=ParseMode.HTML
    )

@dp.message(Command("help"))
async def help_command(message: Message):
    is_admin = message.from_user.username and message.from_user.username.lower() == ADMIN_USERNAME.lower()
    
    help_text = (
        "📚 <b>Справка по командам бота</b>\n\n"
        "👋 <b>/start</b> - Начало работы с ботом\n"
        "⚙️ <b>/settings</b> - Настройки уведомлений и ключевых слов\n"
        "🔍 <b>Как это работает?</b>\n"
        "1. Я постоянно отслеживаю новые проекты на:\n"
        "   • Kwork.ru\n"
        "   • FL.ru\n"
        "   • Freelancer.com\n"
        "2. Фильтрую проекты по вашим ключевым словам\n"
        "3. Присылаю вам уведомления о подходящих проектах\n\n"
        "⚡ <b>Советы по использованию:</b>\n"
        "• Используйте несколько ключевых слов\n"
        "• Регулярно обновляйте ключевые слова в настройках\n"
        "• Отключайте платформы, которые вам неинтересны\n\n"
    )
    
    if is_admin:
        help_text += (
            "👑 <b>Команды администратора:</b>\n"
            "• <b>/force_update</b> - Экстренная проверка новых заказов\n"
            "• <b>/shutdown</b> - Остановка бота\n\n"
        )
    
    help_text += "❓ Если у вас остались вопросы, обратитесь к администратору: @Goldie228."
    
    await message.answer(
        help_text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_keyboard()
    )

@dp.message(lambda message: message.text == "⚙️ Настройки")
async def settings_text_command(message: Message):
    await cmd_settings(message)

@dp.message(lambda message: message.text == "❓ Помощь")
async def help_text_command(message: Message):
    await help_command(message)

async def shutdown(loop, bot):
    logging.info("Начало завершения работы...")

    try:
        await bot.close()
        logging.info("Бот остановлен")
    except Exception as e:
        logging.error(f"Ошибка при остановке бота: {e}")

    try:
        logging.info("Завершение процессов парсеров...")
        await asyncio.get_event_loop().run_in_executor(None, application_parser.kill_processes)
        logging.info("Процессы парсеров завершены")
    except Exception as e:
        logging.error(f"Ошибка при завершении парсеров: {e}")

    try:
        db.disconnect()
        logging.info("Соединение с БД закрыто")
    except Exception as e:
        logging.error(f"Ошибка при закрытии БД: {e}")

    loop.stop()
    logging.info("Event loop остановлен")

@dp.message(Command("shutdown"))
async def shutdown_command(message: Message):
    if message.from_user.username == ADMIN_USERNAME:
        await message.answer("🛑 Инициировано выключение бота...")
        logging.info(f"Инициировано выключение через команду от {message.from_user.username}")
        await shutdown(asyncio.get_event_loop(), bot)
    else:
        await message.answer("⛔ У вас нет прав на выполнение этой команды")
        logging.warning(f"Попытка выключения от неавторизованного пользователя: {message.from_user.username}")

class SettingsState(StatesGroup):
    SETTING_KEYWORDS = State()

def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⚙️ Настройки")],
            [KeyboardButton(text="❓ Помощь")]
        ],
        resize_keyboard=True
    )

async def cmd_settings(message: Message, update: bool = False):
    chat_id = str(message.chat.id)
    user = db.get_user(chat_id)
    
    if not user:
        return

    # Создаем клавиатуру настроек
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=f"🔔 Kwork: {'Вкл' if user[3] else 'Выкл'}",
            callback_data=f"toggle_kwork:{'off' if user[3] else 'on'}"
        ),
        InlineKeyboardButton(
            text=f"🔔 FL: {'Вкл' if user[4] else 'Выкл'}",
            callback_data=f"toggle_fl:{'off' if user[4] else 'on'}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=f"🔔 Freelancer: {'Вкл' if user[5] else 'Выкл'}",
            callback_data=f"toggle_freelancer:{'off' if user[5] else 'on'}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="✏️ Ключевые слова",
            callback_data="set_keywords"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="❌ Закрыть настройки",
            callback_data="close_settings"
        )
    )
    
    settings_text = (
        "⚙️ <b>Настройки уведомлений</b>\n\n"
        "Здесь Вы можете настроить параметры получения уведомлений:\n"
        "1. Включить/выключить уведомления для каждой платформы\n"
        "2. Установить ключевые слова для фильтрации проектов"
    )
    
    markup = builder.as_markup()
    
    if update:
        try:
            await message.edit_text(settings_text, reply_markup=markup, parse_mode="HTML")
        except Exception as e:
            logging.error(f"Ошибка редактирования сообщения: {e}")
            await message.answer(settings_text, reply_markup=markup, parse_mode="HTML")
    else:
        await message.answer(settings_text, reply_markup=markup, parse_mode="HTML")


@dp.message(Command("settings"))
async def settings_command_handler(message: Message):
    await cmd_settings(message, update=False)


@dp.callback_query(lambda c: c.data.startswith("toggle_"))
async def toggle_service(callback: CallbackQuery):
    service, action = callback.data.split(":")
    service = service.replace("toggle_", "")
    chat_id = str(callback.from_user.id)

    if service == "kwork":
        db.update_user(chat_id, mailing_kwork=(action == "on"))
    elif service == "fl":
        db.update_user(chat_id, mailing_fl=(action == "on"))
    elif service == "freelancer":
        db.update_user(chat_id, mailing_freelancer=(action == "on"))

    await cmd_settings(callback.message, update=True)
    await callback.answer(f"Настройки для {service} обновлены")


@dp.callback_query(lambda c: c.data == "set_keywords")
async def set_keywords_start(callback: CallbackQuery, state: FSMContext):
    chat_id = str(callback.message.chat.id)
    user = db.get_user(chat_id)
    current_keywords = user[2] if user and user[2] else "Нет установленных ключевых слов"
    
    await state.set_state(SettingsState.SETTING_KEYWORDS)
    try:
        await callback.message.edit_text(
            f"✏️ <b>Настройка ключевых слов</b>\n\n"
            f"Текущие ключевые слова: <code>{current_keywords}</code>\n\n"
            "Введите ключевые слова через запятую, по которым Вы хотите получать уведомления.\n"
            "Пример: <i>python, django, парсинг</i>\n\n"
            "❕ Для отмены введите /cancel",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logging.error(f"Ошибка редактирования сообщения для настройки ключевых слов: {e}")
        await callback.message.answer(
            f"✏️ <b>Настройка ключевых слов</b>\n\n"
            f"Текущие ключевые слова: <code>{current_keywords}</code>\n\n"
            "Введите ключевые слова через запятую, по которым Вы хотите получать уведомления.\n"
            "Пример: <i>python, django, парсинг</i>\n\n"
            "❕ Для отмены введите /cancel",
            parse_mode=ParseMode.HTML
        )
    await callback.answer()

@dp.message(Command("cancel"), SettingsState.SETTING_KEYWORDS)
async def cancel_keywords(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "❌ Настройка ключевых слов отменена",
        reply_markup=get_main_keyboard()
    )

@dp.message(Command("force_update"))
async def force_update_command(message: Message):
    if message.from_user.username and message.from_user.username.lower() == ADMIN_USERNAME.lower():
        redis_client.publish('data_updates', 'true')
        await message.answer("🔄 Запуск экстренной проверки новых заказов...")
    else:
        await message.answer("⛔ Эта команда доступна только администратору")

@dp.message(SettingsState.SETTING_KEYWORDS)
async def save_keywords(message: Message, state: FSMContext):
    chat_id = str(message.chat.id)
    raw_keywords = message.text.strip()

    keywords_list = [kw.strip() for kw in raw_keywords.split(",") if kw.strip()]
    if not keywords_list:
        await message.answer("❌ Вы не ввели корректных ключевых слов. Попробуйте еще раз или отправьте /cancel для отмены.")
        return

    validated_keywords = ", ".join(keywords_list)
    
    try:
        db.update_user(chat_id, keywords=validated_keywords)
        await state.clear()
    except Exception as e:
        logging.error(f"Ошибка обновления ключевых слов в БД: {e}")
        await message.answer("❌ Ошибка обновления ключевых слов в базе данных. Попробуйте позже.")
        return

    await cmd_settings(message, update=False)

    await message.answer(
        f"✅ Ключевые слова сохранены:\n<code>{validated_keywords}</code>", 
        parse_mode=ParseMode.HTML
    )
    await message.answer(
        "Вы в главном меню",
        reply_markup=get_main_keyboard()
    )

@dp.callback_query(lambda c: c.data == "close_settings")
async def close_settings(callback: CallbackQuery):
    try:
        await callback.message.delete()
    except Exception as e:
        logging.error(f"Ошибка удаления сообщения настроек: {e}")
    await callback.message.answer(
        "⚙️ Настройки закрыты.",
        reply_markup=get_main_keyboard()
    )
    await callback.answer()

def handle_signal(signame):
    logging.info(f"Получен сигнал {signame}")
    asyncio.create_task(shutdown(asyncio.get_event_loop(), bot))

async def main() -> None:
    global bot
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    db.connect()

    notification_service = NotificationService(redis_client_asyncio, db, dp, bot)
    asyncio.create_task(notification_service.listen())

    loop = asyncio.get_running_loop()
    for signame in ('SIGINT', 'SIGTERM'):
        loop.add_signal_handler(
            getattr(signal, signame),
            lambda: handle_signal(signame)
        )

    try:
        parser_task = asyncio.create_task(
            asyncio.to_thread(application_parser.run_parsers)
        )

        async with bot:
            await dp.start_polling(bot)
            
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logging.error(f"Ошибка: {e}")
    finally:
        db.disconnect()
        listen_task.cancel()

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        stream=sys.stdout
    )
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Завершение по Ctrl+C")
    except Exception as e:
        logging.error(f"Критическая ошибка: {e}")
    finally:
        logging.info("Программа завершена")
