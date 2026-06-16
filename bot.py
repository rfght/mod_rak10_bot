import asyncio
import os
import json
import logging
from flask import Flask, request

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    Update,
)
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.environ.get("TELEGRAM_ADMIN_ID", 0))
GROUP_ID = -1002832219010

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Flask приложение для webhook
app = Flask(__name__)
WEBHOOK_PATH = "/webhook"

# Путь для сохранения file_ids (абсолютный путь на PythonAnywhere)
USERNAME = os.environ.get("USER", "")
FILE_IDS_PATH = f"/home/{USERNAME}/file_ids.json"
FILE_IDS: dict[str, str] = {}

def load_file_ids() -> None:
    global FILE_IDS
    try:
        with open(FILE_IDS_PATH) as f:
            FILE_IDS = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        FILE_IDS = {}

def save_file_ids() -> None:
    with open(FILE_IDS_PATH, "w") as f:
        json.dump(FILE_IDS, f, ensure_ascii=False, indent=2)

load_file_ids()

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Моды"), KeyboardButton(text="Приколы")],
        [KeyboardButton(text="Помощь"), KeyboardButton(text="Предложить мод")],
        [KeyboardButton(text="В разработке"), KeyboardButton(text="Донат")],
        [KeyboardButton(text="Сообщить об ошибке")],
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
)

MENU_BUTTONS = {
    "Моды",
    "Приколы",
    "Помощь",
    "Предложить мод",
    "В разработке",
    "Донат",
    "Сообщить об ошибке",
}

mods_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Старый шрифт", callback_data="mod_old_font")],
        [InlineKeyboardButton(text="Старые медали", callback_data="mod_old_medals")],
        [InlineKeyboardButton(text="Старый UI ангара", callback_data="mod_old_ui")],
    ]
)

help_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Как установить мод", callback_data="help_install")],
        [InlineKeyboardButton(text="Как удалить мод", callback_data="help_remove")],
        [InlineKeyboardButton(text="Зачем нужны данные модификации", callback_data="help_why")],
        [InlineKeyboardButton(text="Сколько разрабатываются моды", callback_data="help_time")],
        [InlineKeyboardButton(text="Почему моды только на возвращение старого в игру", callback_data="help_why_old")],
    ]
)

class UserState(StatesGroup):
    awaiting_mod_suggestion = State()
    awaiting_file_register = State()
    awaiting_fun = State()
    awaiting_bug_report = State()

def find_file_id(base_name: str):
    base_lower = base_name.lower()
    if base_name in FILE_IDS:
        return base_name, FILE_IDS[base_name]
    for stored_name, file_id in FILE_IDS.items():
        stored_base = stored_name.rsplit(".", 1)[0].lower()
        if stored_base == base_lower:
            return stored_name, file_id
    return None

async def send_mod_file(chat_id: int, base_name: str) -> None:
    result = find_file_id(base_name)
    if not result:
        await bot.send_message(chat_id, "⚠️ Файл пока недоступен. Попробуй позже.")
        return
    found_name, file_id = result
    await bot.send_document(chat_id, file_id)

@dp.message(F.chat.id == GROUP_ID, F.document)
async def group_document_handler(message: Message) -> None:
    doc = message.document
    if doc.file_name:
        FILE_IDS[doc.file_name] = doc.file_id
        save_file_ids()
        logger.info(f"Captured file from group: {doc.file_name}")

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\n\nДобро пожаловать! Выбери нужный раздел:",
        reply_markup=main_keyboard,
    )

@dp.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    if current:
        await state.clear()
        await message.answer("❌ Отменено. Возвращаюсь в главное меню.", reply_markup=main_keyboard)
    else:
        await message.answer("Нечего отменять.", reply_markup=main_keyboard)

@dp.message(Command("add_file"))
async def cmd_add_file(message: Message, state: FSMContext) -> None:
    if message.from_user.id != ADMIN_ID:
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Использование: /add_file <имя_файла.zip>\nЗатем отправь документ.")
        return
    file_name = args[1].strip()
    await state.update_data(pending_file_name=file_name)
    await state.set_state(UserState.awaiting_file_register)
    await message.answer(f"Теперь отправь файл для «{file_name}»")

@dp.message(UserState.awaiting_file_register, F.document)
async def receive_file_for_register(message: Message, state: FSMContext) -> None:
    if message.from_user.id != ADMIN_ID:
        await state.clear()
        return
    data = await state.get_data()
    file_name = data.get("pending_file_name", "")
    if not file_name:
        await state.clear()
        return
    FILE_IDS[file_name] = message.document.file_id
    save_file_ids()
    await state.clear()
    await message.answer(f"✅ Файл «{file_name}» сохранён!")

@dp.message(F.text == "Моды")
async def btn_mods(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("<b>Моды</b>\n\nВыбери мод:", parse_mode="HTML", reply_markup=mods_keyboard)

@dp.callback_query(F.data == "mod_old_font")
async def cb_old_font(callback: CallbackQuery) -> None:
    await callback.answer()
    await send_mod_file(callback.from_user.id, "old_font")

@dp.callback_query(F.data == "mod_old_medals")
async def cb_old_medals(callback: CallbackQuery) -> None:
    await callback.answer()
    await send_mod_file(callback.from_user.id, "old_medals")

@dp.callback_query(F.data == "mod_old_ui")
async def cb_old_ui(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer(
        "Данный мод возвращает:\n"
        "• боковую панель, кнопку «В Бой» и выбор режима\n"
        "• UI хранилища\n"
        "• кнопку магазина\n"
        "• иконки ресурсов\n"
        "• иконки победы/поражения/ничьи во вкладке уведомлений"
    )
    await send_mod_file(callback.from_user.id, "old_ui")

@dp.message(F.text == "Приколы")
async def btn_fun(message: Message, state: FSMContext) -> None:
    await state.set_state(UserState.awaiting_fun)
    await message.answer(
        "Кидай свой игровой прикол сюда!\n\n"
        "Это может быть:\n"
        "• Забавный момент из боя\n"
        "• Необычная ситуация с физикой игры\n"
        "• Смешной баг или совпадение\n"
        "• Любой другой забавный случай из игры\n\n"
        "Отправляй хоть видео, хоть фото, хоть текст",
        reply_markup=main_keyboard,
    )

@dp.message(UserState.awaiting_fun, ~F.text.in_(MENU_BUTTONS))
async def receive_fun(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = message.from_user
    username = f"@{user.username}" if user.username else "нет username"
    header = f"😂 <b>Прикол от пользователя!</b>\n👤 {user.full_name} ({username})\n🆔 <code>{user.id}</code>\n\n"
    try:
        await bot.send_message(ADMIN_ID, header, parse_mode="HTML")
        await message.forward(ADMIN_ID)
    except Exception as e:
        logger.error("Failed to forward fun to admin: %s", e)
    await message.answer(
        "Спасибо! Твой прикол принят. Когда его проверят моддераторы, он попадёт в наш канал.",
        reply_markup=main_keyboard,
    )

@dp.message(F.text == "Помощь")
async def btn_help(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("<b>Помощь</b>\n\nВыбери вопрос:", parse_mode="HTML", reply_markup=help_keyboard)

@dp.callback_query(F.data == "help_install")
async def cb_help_install(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer(
        "Как установить мод:\n\n"
        "Шаг 1. Скачать мод с официального сайта For Blitz или в нашем боте\n"
        "‼️Обрати внимание, мод только на ПК‼️\n"
        "Шаг 2. Распаковать архив или просто зайти в него\n"
        "Шаг 3. Скопировать папку Data\n"
        "Шаг 4. Зайти в папку игры: C:\\Games\\Tanks Blitz\n"
        "Шаг 5. Нажать вставить скопированную папку Data с заменой"
    )

@dp.callback_query(F.data == "help_remove")
async def cb_help_remove(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer(
        "Как удалить мод:\n\nСамый простой способ — нажать в приложении LGC восстановление игры"
    )

@dp.callback_query(F.data == "help_why")
async def cb_help_why(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer(
        "Зачем нужны данные модификации:\n\n"
        "Моды возвращают удалённые функции и интерфейс, к которым привыкли игроки. "
        "Это делает игру комфортнее и привычнее для тех, кто играл раньше. "
        "Иногда старое — это просто лучше."
    )

@dp.callback_query(F.data == "help_time")
async def cb_help_time(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer(
        "Сколько разрабатываются моды:\n\n"
        "Время разработки зависит от размера мода, сложности, свободного времени у мододела, "
        "а также от того, насколько часто бывают бухие сервера у картошки"
    )

@dp.callback_query(F.data == "help_why_old")
async def cb_help_why_old(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer(
        "Почему модификации только на возвращение старого в игру:\n\n"
        "Чтобы делать что-то новое, нужно настроение. У нашей команды пока настроение только "
        "делать старое, к тому же новое делать намного сложнее"
    )

@dp.message(F.text == "Предложить мод")
async def btn_suggest_mod(message: Message, state: FSMContext) -> None:
    await state.set_state(UserState.awaiting_mod_suggestion)
    await message.answer(
        "<b>Предложить мод</b>\n\n"
        "Напиши описание мода или отправь файл/ссылку.\n"
        "Твоё сообщение будет переслано администратору. ✅\n\n"
        "Для отмены напиши /cancel",
        parse_mode="HTML",
    )

@dp.message(UserState.awaiting_mod_suggestion, ~F.text.in_(MENU_BUTTONS))
async def receive_mod_suggestion(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = message.from_user
    username = f"@{user.username}" if user.username else "нет username"
    header = f"📩 <b>Новый мод от пользователя!</b>\n👤 {user.full_name} ({username})\n🆔 <code>{user.id}</code>\n\n"
    try:
        await bot.send_message(ADMIN_ID, header, parse_mode="HTML")
        await message.forward(ADMIN_ID)
        await message.answer("✅ Твой мод отправлен на рассмотрение! Спасибо!", reply_markup=main_keyboard)
    except Exception as e:
        logger.error("Failed to forward mod to admin: %s", e)
        await message.answer("⚠️ Не удалось отправить мод. Попробуй позже.", reply_markup=main_keyboard)

@dp.message(F.text == "В разработке")
async def btn_in_dev(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Сейчас в разработке:\n\n"
        "• Мод на старое окно шансов\n"
        "• Мод на отсутствие подтверждения при открытии контейнера из хранилища\n"
        "• Старое окно выбора режима\n"
        "• Старая анимация открытия контейнера\n\n"
        "‼️ И всё из этого может и не выйти\n"
        "Данный список — это набросок планируемых модов. Что-то выйдет, что-то нет",
        reply_markup=main_keyboard,
    )

@dp.message(F.text == "Донат")
async def btn_donate(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Поддержать разработку модов\n\n"
        "Пока мы не принимаем донаты, но если хочешь сказать спасибо — вот что можно сделать:\n\n"
        "• Расскажи о нашем канале и боте друзьям\n"
        "• Предложи идею для нового мода\n"
        "• Присоединись к команде тестировщиков (скоро можно будет)\n\n"
        "Донаты откроются позже. Следи за новостями в нашем канале!",
        reply_markup=main_keyboard,
    )

@dp.message(F.text == "Сообщить об ошибке")
async def btn_bug_report(message: Message, state: FSMContext) -> None:
    await state.set_state(UserState.awaiting_bug_report)
    await message.answer(
        "Опиши ошибку в моде. Напиши название мода и что именно не так, всё будет передано разработчикам.",
        reply_markup=main_keyboard,
    )

@dp.message(UserState.awaiting_bug_report, ~F.text.in_(MENU_BUTTONS))
async def receive_bug_report(message: Message, state: FSMContext) -> None:
    if message.voice or (not message.text and not message.photo and not message.video and not message.document):
        await message.answer("Напиши подробности текстом и по возможности фото или видео. Голосовые и пустые сообщения не принимаются.")
        return
    await state.clear()
    user = message.from_user
    username = f"@{user.username}" if user.username else "нет username"
    header = f"🐛 <b>[ОШИБКА] Сообщение об ошибке</b>\n👤 {user.full_name} ({username})\n🆔 <code>{user.id}</code>\n\n"
    try:
        await bot.send_message(ADMIN_ID, header, parse_mode="HTML")
        await message.forward(ADMIN_ID)
    except Exception as e:
        logger.error("Failed to forward bug report to admin: %s", e)
    await message.answer(
        "✅ Спасибо, сообщение об ошибке передано разработчикам. Постараемся исправить в ближайшее время.",
        reply_markup=main_keyboard,
    )

# Flask webhook endpoint
@app.route(WEBHOOK_PATH, methods=["POST"])
async def webhook():
    update = Update.model_validate(await request.get_json(), context={"bot": bot})
    await dp.feed_update(bot, update)
    return "OK"

@app.route("/", methods=["GET"])
def index():
    return "Mod_rak bot is running"

def set_webhook():
    webhook_url = f"https://{USERNAME}.pythonanywhere.com{WEBHOOK_PATH}"
    # Используем asyncio для установки webhook
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(bot.set_webhook(webhook_url))
    logger.info(f"Webhook set to {webhook_url}")

# Устанавливаем webhook при запуске
set_webhook()