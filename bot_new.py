import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from config import BOT_TOKEN, NOTIFICATION_CHANNEL_ID
from database import Database

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Инициализация бота, диспетчера и БД
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot, storage=storage)
db = Database()

# Состояния для FSM
class RegistrationStates(StatesGroup):
    waiting_for_category = State()
    waiting_for_documents = State()

class AdminStates(StatesGroup):
    viewing_users = State()
    viewing_user_details = State()

# Словарь для хранения данных пользователей (временно)
user_data = {}

# Требования к документам
DOCUMENT_REQUIREMENTS = {
    "truck_driver": {
        "name": "Водитель грузового авто",
        "emoji": "🚛",
        "text": "📋 Для регистрации в качестве <b>водителя грузового авто</b> отправьте следующие документы:\n\n"
               "1️⃣ Паспорт (разворот с фото - 2 страницы)\n"
               "2️⃣ Свидетельство о регистрации транспортного средства\n"
               "3️⃣ Водительское удостоверение (обе стороны)\n\n"
               "📸 Отправьте все фото одним сообщением",
        "required_count": 4,
        "orders_required": 30  # Для грузового
    },
    "car_courier": {
        "name": "Курьер на авто",
        "emoji": "🚗",
        "text": "📋 Для регистрации в качестве <b>курьера на авто</b> отправьте следующие документы:\n\n"
               "1️⃣ Паспорт (разворот с фото - 2 страницы)\n"
               "2️⃣ Свидетельство о регистрации транспортного средства\n"
               "3️⃣ Водительское удостоверение (обе стороны)\n\n"
               "📸 Отправьте все фото одним сообщением",
        "required_count": 4,
        "orders_required": 45  # Для легкового
    },
    "foot_courier": {
        "name": "Пеший курьер",
        "emoji": "🚶",
        "text": "📋 Для регистрации в качестве <b>пешего курьера</b> отправьте следующие документы:\n\n"
               "1️⃣ Паспорт (разворот с фото - 2 страницы)\n\n"
               "📸 Отправьте обе страницы паспорта.",
        "required_count": 2,
        "orders_required": 45
    }
}


def get_main_menu_keyboard(is_admin=False):
    """Главное меню с кнопками"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        KeyboardButton("👤 Профиль"),
        KeyboardButton("👥 Пригласить друзей")
    )
    if is_admin:
        keyboard.add(KeyboardButton("⚙️ Админ-панель"))
    return keyboard


def get_category_keyboard():
    """Создает клавиатуру для выбора категории"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton(text="🚛 Водитель грузового авто", callback_data="category:truck_driver"),
        InlineKeyboardButton(text="🚗 Курьер на авто", callback_data="category:car_courier"),
        InlineKeyboardButton(text="🚶 Пеший курьер", callback_data="category:foot_courier")
    )
    return keyboard


def get_form_links_keyboard():
    """Создает клавиатуру со ссылками на формы"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton(
            text="🚛 Водитель грузового авто",
            url="https://forms.fleet.yandex.ru/forms?specification=delivery&ref_id=8419ea99ae524a0abc7a2bd5d6c9c70e"
        ),
        InlineKeyboardButton(
            text="🚗 Курьер на авто",
            url="https://forms.fleet.yandex.ru/forms?specification=delivery&ref_id=d078e9b00c424882989307cc022adc16"
        ),
        InlineKeyboardButton(
            text="🚶 Пеший курьер",
            url="https://forms.fleet.yandex.ru/forms?specification=delivery&skip_license=1&skip_vehicle=1&ref_id=c3456951bc4b49eca09c93cb7fd28787"
        )
    )
    return keyboard


def get_admin_keyboard():
    """Клавиатура админ-панели"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        KeyboardButton("📊 Все пользователи"),
        KeyboardButton("📈 Статистика")
    )
    keyboard.add(KeyboardButton("◀️ Назад"))
    return keyboard


@dp.message_handler(CommandStart(), state="*")
async def cmd_start(message: types.Message, state: FSMContext):
    """Обработчик команды /start"""
    await state.finish()
    
    user = message.from_user
    args = message.get_args()  # Получаем аргументы из /start ref_12345
    
    # Проверяем реферальную ссылку
    referrer_id = None
    if args and args.startswith("ref_"):
        try:
            referrer_id = int(args.split("_")[1])
            # Проверяем, что реферер существует и это не сам пользователь
            if referrer_id == user.id:
                referrer_id = None
        except:
            referrer_id = None
    
    # Проверяем, зарегистрирован ли пользователь
    existing_user = db.get_user(user.id)
    
    if existing_user:
        # Пользователь уже зарегистрирован, показываем главное меню
        is_admin = db.is_admin(user.id)
        await message.answer(
            f"👋 С возвращением, {user.first_name}!",
            reply_markup=get_main_menu_keyboard(is_admin)
        )
        return
    
    # Инициализируем данные нового пользователя
    user_data[user.id] = {
        "category": None,
        "photos": [],
        "referrer_id": referrer_id,
        "user_info": {
            "id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "first_name": user.first_name
        }
    }
    
    # Приветствие с упоминанием реферала
    welcome_text = f"👋 Здравствуйте, {user.first_name}!\n\n"
    if referrer_id:
        referrer = db.get_user(referrer_id)
        if referrer:
            welcome_text += f"Вы приглашены пользователем {referrer['full_name']}!\n\n"
    
    welcome_text += "Выберите категорию для регистрации:"
    
    await message.answer(
        text=welcome_text,
        reply_markup=get_category_keyboard()
    )
    await RegistrationStates.waiting_for_category.set()


@dp.callback_query_handler(lambda c: c.data.startswith("category:"), state=RegistrationStates.waiting_for_category)
async def process_category_selection(callback_query: types.CallbackQuery, state: FSMContext):
    """Обработчик выбора категории"""
    await callback_query.answer()
    
    user_id = callback_query.from_user.id
    category = callback_query.data.split(":")[1]
    
    if user_id not in user_data:
        user_data[user_id] = {"photos": [], "user_info": {}}
    
    user_data[user_id]["category"] = category
    doc_info = DOCUMENT_REQUIREMENTS[category]
    
    await callback_query.message.edit_text(
        text=doc_info["text"],
        parse_mode="HTML"
    )
    
    await RegistrationStates.waiting_for_documents.set()


@dp.message_handler(content_types=types.ContentType.PHOTO, state=RegistrationStates.waiting_for_documents)
async def process_photo(message: types.Message, state: FSMContext):
    """Обработчик получения фото документов"""
    user_id = message.from_user.id
    
    if user_id not in user_data:
        await message.answer("Произошла ошибка. Пожалуйста, начните сначала с команды /start")
        await state.finish()
        return
    
    # Сохраняем фото
    photo = message.photo[-1]
    user_data[user_id]["photos"].append(photo.file_id)
    
    category = user_data[user_id]["category"]
    required_count = DOCUMENT_REQUIREMENTS[category]["required_count"]
    current_count = len(user_data[user_id]["photos"])
    
    # Проверяем, собрали ли мы все документы
    if current_count < required_count:
        # НЕ отправляем промежуточное сообщение
        pass
    else:
        # Все документы собраны
        await message.answer(
            "✅ Все документы получены!\n"
            "Отправляем информацию на проверку..."
        )
        
        # Сохраняем пользователя в БД
        referrer_id = user_data[user_id].get("referrer_id")
        user_info = user_data[user_id]["user_info"]
        
        db.add_user(
            user_id=user_info["id"],
            username=user_info["username"],
            full_name=user_info["full_name"],
            first_name=user_info["first_name"],
            category=category,
            referrer_id=referrer_id
        )
        
        # Отправляем уведомление в канал
        await send_notification_to_channel(user_id, message.bot)
        
        # Отправляем информацию о реферальной программе
        orders_required = DOCUMENT_REQUIREMENTS[category]["orders_required"]
        referral_text = (
            f"🎉 <b>Регистрация успешно завершена!</b>\n\n"
            f"💰 <b>Зарабатывайте с нами!</b>\n\n"
            f"Приглашайте друзей и получайте бонусы:\n"
            f"• <b>1000 руб</b> — вам за каждого приглашённого\n"
            f"• <b>500 руб</b> — вашему другу\n\n"
            f"📋 Условия:\n"
            f"Ваш друг должен выполнить <b>{orders_required} заказов</b> в категории {DOCUMENT_REQUIREMENTS[category]['emoji']} {DOCUMENT_REQUIREMENTS[category]['name']}\n\n"
            f"Используйте кнопку <b>\"👥 Пригласить друзей\"</b> для получения вашей реферальной ссылки!"
        )
        
        # Отправляем пользователю ссылки на формы
        await message.answer(
            "📝 <b>Откройте нужную форму заявки на подключение:</b>",
            parse_mode="HTML",
            reply_markup=get_form_links_keyboard()
        )
        
        # Показываем главное меню
        is_admin = db.is_admin(user_id)
        await message.answer(
            referral_text,
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard(is_admin)
        )
        
        # Очищаем данные пользователя
        user_data.pop(user_id, None)
        await state.finish()


async def send_notification_to_channel(user_id: int, bot: Bot):
    """Отправляет уведомление в канал с фото и информацией о пользователе"""
    try:
        user_info = user_data[user_id]["user_info"]
        category = user_data[user_id]["category"]
        photos = user_data[user_id]["photos"]
        referrer_id = user_data[user_id].get("referrer_id")
        
        category_info = DOCUMENT_REQUIREMENTS[category]
        
        # Формируем текст уведомления
        user_link = f"<a href='tg://user?id={user_info['id']}'>{user_info['full_name']}</a>"
        notification_text = (
            f"🆕 <b>Новая регистрация!</b>\n\n"
            f"{category_info['emoji']} <b>Категория:</b> {category_info['name']}\n\n"
            f"👤 <b>Пользователь:</b> {user_link}\n"
            f"🆔 <b>Username:</b> @{user_info['username'] if user_info['username'] else 'не указан'}\n"
            f"🔢 <b>ID:</b> <code>{user_info['id']}</code>\n"
        )
        
        # Добавляем информацию о реферере
        if referrer_id:
            referrer = db.get_user(referrer_id)
            if referrer:
                referrer_link = f"<a href='tg://user?id={referrer['user_id']}'>{referrer['full_name']}</a>"
                notification_text += f"\n👥 <b>Приглашён пользователем:</b> {referrer_link}\n"
                notification_text += f"📱 <b>Username реферера:</b> @{referrer['username'] if referrer['username'] else 'не указан'}"
        
        notification_text += f"\n\n📄 <b>Документы:</b> {len(photos)} фото"
        
        # Формируем медиа группу
        media = []
        for i, photo_id in enumerate(photos):
            if i == 0:
                media.append(types.InputMediaPhoto(
                    media=photo_id,
                    caption=notification_text,
                    parse_mode="HTML"
                ))
            else:
                media.append(types.InputMediaPhoto(media=photo_id))
        
        # Отправляем медиа группу
        await bot.send_media_group(
            chat_id=NOTIFICATION_CHANNEL_ID,
            media=media
        )
        
        logging.info(f"Уведомление для пользователя {user_id} успешно отправлено в канал")
        
    except Exception as e:
        logging.error(f"Ошибка при отправке уведомления в канал: {e}")


@dp.message_handler(lambda message: message.text == "👥 Пригласить друзей", state="*")
async def show_referral_link(message: types.Message, state: FSMContext):
    """Показать реферальную ссылку"""
    user_id = message.from_user.id
    bot_info = await bot.get_me()
    referral_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
    
    user = db.get_user(user_id)
    if not user:
        await message.answer("Сначала пройдите регистрацию, отправив /start")
        return
    
    stats = db.get_user_stats(user_id)
    category = user['category']
    orders_required = DOCUMENT_REQUIREMENTS[category]['orders_required']
    
    referral_text = (
        f"🔗 <b>Ваша реферальная ссылка:</b>\n"
        f"<code>{referral_link}</code>\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"👥 Приглашено: {stats['invited_count']}\n"
        f"✅ Выполнили условия: {stats['completed_count']}\n\n"
        f"💰 <b>Условия:</b>\n"
        f"• 1000 руб — вам\n"
        f"• 500 руб — другу\n"
        f"• Нужно выполнить {orders_required} заказов\n\n"
        f"Отправьте ссылку своим друзьям!"
    )
    
    await message.answer(referral_text, parse_mode="HTML")


@dp.message_handler(lambda message: message.text == "👤 Профиль", state="*")
async def show_profile(message: types.Message, state: FSMContext):
    """Показать профиль пользователя"""
    user_id = message.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        await message.answer("Сначала пройдите регистрацию, отправив /start")
        return
    
    referrals = db.get_referrals(user_id)
    stats = db.get_user_stats(user_id)
    category_info = DOCUMENT_REQUIREMENTS[user['category']]
    orders_required = category_info['orders_required']
    
    profile_text = (
        f"👤 <b>Ваш профиль</b>\n\n"
        f"📛 Имя: {user['full_name']}\n"
        f"{category_info['emoji']} Категория: {category_info['name']}\n"
        f"📅 Регистрация: {user['created_at'][:10]}\n\n"
        f"👥 <b>Приглашённые:</b> {stats['invited_count']}\n"
        f"✅ <b>Выполнили условия:</b> {stats['completed_count']}\n\n"
    )
    
    if referrals:
        profile_text += "<b>📋 Список приглашённых:</b>\n\n"
        for ref in referrals[:10]:  # Показываем первые 10
            status_emoji = "✅" if ref['orders_count'] >= orders_required else "⏳"
            profile_text += (
                f"{status_emoji} {ref['full_name']}\n"
                f"   Заказов: {ref['orders_count']}/{orders_required}\n"
                f"   Бонус: {'Выплачен' if ref['bonus_paid'] else 'Ожидается'}\n\n"
            )
    
    await message.answer(profile_text, parse_mode="HTML")


@dp.message_handler(lambda message: message.text == "⚙️ Админ-панель", state="*")
async def show_admin_panel(message: types.Message, state: FSMContext):
    """Админ-панель"""
    user_id = message.from_user.id
    
    if not db.is_admin(user_id):
        await message.answer("У вас нет прав администратора")
        return
    
    await message.answer(
        "⚙️ <b>Админ-панель</b>\n\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard()
    )


@dp.message_handler(lambda message: message.text == "📊 Все пользователи", state="*")
async def show_all_users(message: types.Message, state: FSMContext):
    """Показать всех пользователей"""
    user_id = message.from_user.id
    
    if not db.is_admin(user_id):
        await message.answer("У вас нет прав администратора")
        return
    
    users = db.get_all_users()
    
    users_text = f"📊 <b>Всего пользователей:</b> {len(users)}\n\n"
    
    for user in users[:20]:  # Показываем первых 20
        category_info = DOCUMENT_REQUIREMENTS.get(user['category'], {})
        emoji = category_info.get('emoji', '❓')
        
        referrer_text = ""
        if user['referrer_id']:
            referrer = db.get_user(user['referrer_id'])
            if referrer:
                referrer_text = f"   👥 Пригласил: {referrer['full_name']}\n"
        
        users_text += (
            f"{emoji} <b>{user['full_name']}</b>\n"
            f"   ID: <code>{user['user_id']}</code>\n"
            f"   @{user['username'] if user['username'] else 'нет username'}\n"
            f"{referrer_text}"
            f"   📅 {user['created_at'][:10]}\n\n"
        )
    
    if len(users) > 20:
        users_text += f"\n... и ещё {len(users) - 20} пользователей"
    
    await message.answer(users_text, parse_mode="HTML")


@dp.message_handler(lambda message: message.text == "◀️ Назад", state="*")
async def go_back(message: types.Message, state: FSMContext):
    """Вернуться в главное меню"""
    user_id = message.from_user.id
    is_admin = db.is_admin(user_id)
    
    await message.answer(
        "Главное меню",
        reply_markup=get_main_menu_keyboard(is_admin)
    )


async def main():
    """Запуск бота"""
    logging.info("Запуск бота...")
    
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling()
    except Exception as e:
        logging.error(f"Ошибка при запуске бота: {e}")


if __name__ == "__main__":
    asyncio.run(main())

