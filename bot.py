import asyncio
import logging
import re
from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from config import BOT_TOKEN, NOTIFICATION_CHANNEL_ID, YANDEX_PARK_ID, YANDEX_API_KEY, YANDEX_CLIENT_ID, ADMIN_USER_IDS
from database import Database
from yandex_park_api import YandexParkAPI

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
yandex_api = YandexParkAPI(YANDEX_PARK_ID, YANDEX_API_KEY, YANDEX_CLIENT_ID)

# Состояния для FSM
class RegistrationStates(StatesGroup):
    waiting_for_phone = State()
    waiting_for_category = State()
    waiting_for_documents = State()

class AdminStates(StatesGroup):
    viewing_users = State()
    viewing_user_details = State()
    waiting_for_search_phone = State()


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
        KeyboardButton("🔍 Поиск по номеру"),
        KeyboardButton("📊 Статистика рефералов")
    )
    keyboard.add(KeyboardButton("🔄 Обновить заказы"))
    keyboard.add(KeyboardButton("◀️ Назад"))
    return keyboard


def validate_phone(phone: str) -> bool:
    """Проверка формата номера телефона"""
    # Убираем все символы кроме цифр и +
    cleaned = re.sub(r'[^\d+]', '', phone)
    
    # Проверяем, что номер соответствует формату российского номера
    # +79XXXXXXXXX или 89XXXXXXXXX или 79XXXXXXXXX
    pattern = r'^(\+7|8|7)?\d{10}$'
    return bool(re.match(pattern, cleaned))


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
    
    # Пользователь считается зарегистрированным только если у него есть номер телефона
    if existing_user and existing_user.get('phone_number'):
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
        "phone_number": None,
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
    
    welcome_text += (
        "📱 <b>Для начала работы введите ваш номер телефона</b>\n\n"
        "Формат: +79XXXXXXXXX или 89XXXXXXXXX\n\n"
        "Номер телефона нужен для проверки регистрации."
    )
    
    await message.answer(
        text=welcome_text,
        parse_mode="HTML"
    )
    await RegistrationStates.waiting_for_phone.set()


@dp.message_handler(state=RegistrationStates.waiting_for_phone)
async def process_phone(message: types.Message, state: FSMContext):
    """Обработчик ввода номера телефона"""
    user_id = message.from_user.id
    phone = message.text.strip()
    
    # Проверяем формат номера
    if not validate_phone(phone):
        await message.answer(
            "❌ Неверный формат номера телефона.\n\n"
            "Пожалуйста, введите номер в формате:\n"
            "+79XXXXXXXXX или 89XXXXXXXXX"
        )
        return
    
    # Нормализуем номер
    cleaned_phone = re.sub(r'[^\d+]', '', phone)
    if cleaned_phone.startswith('8'):
        cleaned_phone = '+7' + cleaned_phone[1:]
    elif cleaned_phone.startswith('7'):
        cleaned_phone = '+' + cleaned_phone
    elif not cleaned_phone.startswith('+'):
        cleaned_phone = '+7' + cleaned_phone
    
    user_data[user_id]["phone_number"] = cleaned_phone
    
    # Отправляем сообщение о проверке
    checking_msg = await message.answer("🔍 Проверяю регистрацию в Яндекс Парке...")
    
    # Проверяем в Яндекс Парке
    driver_info = await yandex_api.check_driver_by_phone(cleaned_phone)
    
    if driver_info and driver_info.get("found"):
        # Водитель найден в парке
        # Формируем ФИО водителя (убираем None и пустые значения)
        name_parts = []
        if driver_info.get('last_name'):
            name_parts.append(driver_info.get('last_name'))
        if driver_info.get('first_name'):
            name_parts.append(driver_info.get('first_name'))
        if driver_info.get('middle_name'):
            name_parts.append(driver_info.get('middle_name'))
        driver_name = ' '.join(name_parts) if name_parts else 'Не указано'
        
        # Сохраняем пользователя с отметкой о регистрации в парке
        # Если пользователь уже в парке, не учитываем его как реферала (referrer_id=None)
        user_info = user_data[user_id]["user_info"]
        referrer_id = user_data[user_id].get("referrer_id")  # Сохраняем referrer_id из реферальной ссылки
        
        # Определяем позицию водителя в парке
        park_position = None
        driver_id = driver_info.get("driver_id")
        if driver_id:
            park_position = await yandex_api.get_driver_position(driver_id)
            logging.info(f"Определена позиция водителя {driver_id}: {park_position}")
        
        # Если пользователь уже в парке, не учитываем его как реферала (referrer_id=None)
        # Но если пользователь регистрируется по реферальной ссылке и уже в парке, нужно учитывать его позицию
        db.add_user(
            user_id=user_info["id"],
            username=user_info["username"],
            full_name=user_info["full_name"],
            first_name=user_info["first_name"],
            phone_number=cleaned_phone,
            category=None,
            referrer_id=None,  # Не учитываем реферала для пользователей, уже зарегистрированных в парке
            is_registered_in_park=True,
            yandex_driver_id=driver_id,
            yandex_driver_name=driver_name,
            park_position=park_position
        )
        
        # Если есть реферер И пользователь уже в парке, создаем запись реферала с позицией
        if referrer_id and park_position:
            # Создаем запись в referrals для отслеживания позиции и заказов
            conn = db.get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("""
                INSERT OR IGNORE INTO referrals (referrer_id, referred_id, park_position)
                VALUES (?, ?, ?)
                """, (referrer_id, user_info["id"], park_position))
                conn.commit()
                logging.info(f"Добавлен реферал (уже в парке): referrer_id={referrer_id}, referred_id={user_info['id']}, park_position={park_position}")
            except Exception as e:
                logging.error(f"Ошибка при добавлении реферала: {e}")
            finally:
                conn.close()
        
        # Формируем сообщение с информацией о водителе
        info_text = (
            f"✅ <b>Вы уже зарегистрированы!</b>\n\n"
            f"👤 <b>Имя:</b> {driver_name}\n"
            f"📱 <b>Телефон:</b> {cleaned_phone}\n"
        )
        
        # Если есть информация о балансе
        if driver_info.get("balance") is not None:
            balance = driver_info.get("balance", 0)
            info_text += f"💰 <b>Баланс:</b> {balance} руб.\n"
        
        info_text += (
            f"\n🎉 Регистрация завершена!\n"
            f"Используйте меню ниже для доступа к функциям бота."
        )
        
        await checking_msg.edit_text(info_text, parse_mode="HTML")
        
        # Показываем главное меню
        is_admin = db.is_admin(user_id)
        await message.answer(
            "Главное меню:",
            reply_markup=get_main_menu_keyboard(is_admin)
        )
        
        # Очищаем данные
        user_data.pop(user_id, None)
        await state.finish()
        
    else:
        # Водитель не найден, продолжаем регистрацию
        await checking_msg.edit_text(
            "📋 <b>Вы ещё не зарегистрированы в Яндекс Парке</b>\n\n"
            "Выберите категорию для регистрации:",
            parse_mode="HTML"
        )
        
        await message.answer(
            "Выберите вашу категорию:",
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
        # Проверяем, не был ли уже сохранён пользователь (защита от дублирования)
        if user_data[user_id].get("registered", False):
            return  # Пользователь уже зарегистрирован, игнорируем повторную отправку
        
        # Все документы собраны
        await message.answer(
            "✅ Все документы получены!\n"
            "Отправляем информацию на проверку..."
        )
        
        # Сохраняем пользователя в БД
        referrer_id = user_data[user_id].get("referrer_id")
        user_info = user_data[user_id]["user_info"]
        phone_number = user_data[user_id].get("phone_number")
        
        db.add_user(
            user_id=user_info["id"],
            username=user_info["username"],
            full_name=user_info["full_name"],
            first_name=user_info["first_name"],
            phone_number=phone_number,
            category=category,
            referrer_id=referrer_id,
            is_registered_in_park=False
        )
        
        # Отмечаем, что пользователь зарегистрирован
        user_data[user_id]["registered"] = True
        
        # Отправляем уведомление в канал
        await send_notification_to_channel(user_id, message.bot)
        
        # Отправляем информацию о реферальной программе
        referral_text = (
            f"💰 <b>Зарабатывайте с нами!</b>\n\n"
            f"Приглашайте друзей и получайте бонусы:\n"
            f"• <b>1000 руб</b> — вам за каждого приглашённого\n"
            f"• <b>500 руб</b> — вашему другу\n\n"
            f"📋 <b>Условие выплаты:</b>\n"
            f"При выполнении 45 заказов в тарифе «Экспресс» и 30 заказов в тарифе «Грузовой», Вы и Ваш друг получаете бонус.\n\n"
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
        phone_number = user_data[user_id].get("phone_number", "не указан")
        
        category_info = DOCUMENT_REQUIREMENTS[category]
        
        # Формируем текст уведомления
        notification_text = (
            f"🆕 <b>Новая регистрация!</b>\n\n"
            f"{category_info['emoji']} <b>Категория:</b> {category_info['name']}\n\n"
            f"👤 <b>Пользователь:</b> {user_info['full_name']}\n"
            f"🆔 <b>Username:</b> @{user_info['username'] if user_info['username'] else 'не указан'}\n"
            f"📱 <b>Телефон:</b> {phone_number}\n"
        )
        
        # Добавляем информацию о реферере
        if referrer_id:
            referrer = db.get_user(referrer_id)
            if referrer:
                notification_text += f"\n👥 <b>Приглашён пользователем:</b> {referrer['full_name']}\n"
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
    
    referral_text = (
        f"🔗 <b>Ваша реферальная ссылка:</b>\n"
        f"<code>{referral_link}</code>\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"👥 Приглашено: {stats['invited_count']}\n\n"
        f"💰 <b>Бонусы:</b>\n"
        f"• 1000 руб — вам\n"
        f"• 500 руб — другу\n\n"
        f"📋 <b>Условие выплаты:</b>\n"
        f"При выполнении 45 заказов в тарифе «Экспресс» и 30 заказов в тарифе «Грузовой», Вы и Ваш друг получаете бонус.\n\n"
        f"Отправьте ссылку своим друзьям!"
    )
    
    await message.answer(referral_text, parse_mode="HTML")


async def update_referrals_orders(user_id: int):
    """Обновляет данные о заказах для рефералов пользователя"""
    referrals = db.get_referrals(user_id)
    updated_count = 0
    
    for ref in referrals:
        user_ref = db.get_user(ref['user_id'])
        if user_ref and user_ref.get('is_registered_in_park') and user_ref.get('yandex_driver_id'):
            try:
                yandex_driver_id = user_ref['yandex_driver_id']
                orders_count = await yandex_api.get_driver_orders_count(yandex_driver_id)
                if orders_count is not None:
                    db.update_orders_count(ref['user_id'], orders_count)
                    updated_count += 1
                    logging.info(f"Обновлены заказы для user_id={ref['user_id']}, driver_id={yandex_driver_id}, заказов={orders_count}")
                else:
                    logging.warning(f"Не удалось получить заказы для user_id={ref['user_id']}, driver_id={yandex_driver_id}")
                # Увеличиваем задержку, чтобы избежать 429 ошибок (лимит API)
                await asyncio.sleep(2.0)  # Увеличенная задержка, чтобы избежать 429 ошибок
            except Exception as e:
                logging.error(f"Ошибка при обновлении заказов для {ref['user_id']}: {e}", exc_info=True)
    
    return updated_count


@dp.message_handler(lambda message: message.text == "👤 Профиль", state="*")
async def show_profile(message: types.Message, state: FSMContext):
    """Показать профиль пользователя"""
    user_id = message.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        await message.answer("Сначала пройдите регистрацию, отправив /start")
        return
    
    # Обновляем данные о заказах перед показом профиля
    msg = await message.answer("🔄 Обновляю данные о заказах...")
    updated = await update_referrals_orders(user_id)
    if updated > 0:
        await msg.edit_text(f"✅ Обновлено данных: {updated}")
        await asyncio.sleep(1)
        await msg.delete()
    
    referrals = db.get_referrals(user_id)
    stats = db.get_user_stats(user_id)
    
    profile_text = (
        f"👤 <b>Ваш профиль</b>\n\n"
        f"📛 Имя: {user['full_name']}\n"
        f"📱 Телефон: {user['phone_number']}\n"
    )
    
    # Если пользователь зарегистрирован в парке
    if user.get('is_registered_in_park'):
        profile_text += f"✅ <b>Статус:</b> Зарегистрирован в Яндекс Парке\n"
        if user.get('yandex_driver_name'):
            profile_text += f"👤 ФИО в парке: {user['yandex_driver_name']}\n"
    else:
        # Показываем категорию только если не зарегистрирован в парке
        if user.get('category'):
            category_info = DOCUMENT_REQUIREMENTS.get(user['category'], {})
            profile_text += f"{category_info.get('emoji', '❓')} Категория: {category_info.get('name', 'Не указана')}\n"
    
    profile_text += f"📅 Регистрация: {user['created_at'][:10]}\n\n"
    profile_text += f"👥 <b>Приглашённые:</b> {stats['invited_count']}\n\n"
    
    if referrals:
        profile_text += "<b>📋 Список приглашённых:</b>\n\n"
        for ref in referrals[:10]:  # Показываем первые 10
            
            orders_info = ""
            user_ref = db.get_user(ref['user_id'])
            # Показываем заказы если реферал зарегистрирован в парке ИЛИ если есть данные о заказах
            orders_count = ref.get('orders_count', 0)
            if user_ref and user_ref.get('is_registered_in_park') and orders_count > 0:
                # Показываем количество заказов
                orders_info = f"   📈 <b>Заказов: {orders_count}</b>\n"
            elif orders_count > 0:
                # Если есть данные о заказах, но пользователь не зарегистрирован в парке (старые данные)
                orders_info = f"   📈 <b>Заказов: {orders_count}</b>\n"

            profile_text += (
                f"{ref['full_name']}\n"
                f"@{ref['username'] if ref['username'] else 'нет username'}\n"
                f"{orders_info}"
                f"📅 {ref['created_at'][:10]}\n\n"
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


@dp.message_handler(lambda message: message.text == "🔍 Поиск по номеру", state="*")
async def admin_search_start(message: types.Message, state: FSMContext):
    """Начало поиска пользователя по номеру телефона"""
    if not db.is_admin(message.from_user.id):
        return
    
    await message.answer(
        "📱 Введите номер телефона для поиска:",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await AdminStates.waiting_for_search_phone.set()


@dp.message_handler(state=AdminStates.waiting_for_search_phone)
async def admin_process_search_phone(message: types.Message, state: FSMContext):
    """Обработка введенного номера телефона и поиск"""
    if not db.is_admin(message.from_user.id):
        await state.finish()
        return

    is_admin = db.is_admin(message.from_user.id)
    phone = message.text.strip()
    
    # Сбрасываем состояние FSM
    await state.finish()

    if not validate_phone(phone):
        await message.answer(
            "❌ Неверный формат номера. Попробуйте еще раз.",
            reply_markup=get_admin_keyboard()
        )
        return
        
    normalized_phone = yandex_api._normalize_phone(phone)
    
    await message.answer(f"🔍 Идет поиск по номеру: `{normalized_phone}`", parse_mode="Markdown")

    # Ищем в БД бота (быстро)
    try:
        user_in_db = db.get_user_by_phone(normalized_phone)
    except Exception as e:
        logging.error(f"Ошибка при поиске в БД: {e}")
        user_in_db = None
    
    # Ищем в парке (может быть медленно, поэтому сначала показываем результат из БД)
    driver_in_park = {"found": False}
    try:
        driver_in_park = await asyncio.wait_for(
            yandex_api.check_driver_by_phone(normalized_phone),
            timeout=10.0
        )
    except asyncio.TimeoutError:
        driver_in_park = {"found": False, "error": "timeout"}
        logging.warning("Таймаут при поиске в Яндекс Парке")
    except Exception as e:
        logging.error(f"Ошибка при поиске в парке: {e}")
        driver_in_park = {"found": False, "error": str(e)}
    
    # Проверяем результаты
    if not user_in_db and (not driver_in_park or not driver_in_park.get("found")):
        error_msg = ""
        if driver_in_park and driver_in_park.get("error"):
            if driver_in_park.get("error") == "timeout":
                error_msg = "\n\n⚠️ Поиск в Яндекс Парке занял слишком много времени."
            else:
                error_msg = f"\n\n⚠️ Ошибка при поиске в парке: {driver_in_park.get('error')}"
        
        await message.answer(
            f"🤷‍♂️ Пользователь с номером `{normalized_phone}` не найден ни в базе бота, ни в Яндекс Парке.{error_msg}",
            parse_mode="Markdown",
            reply_markup=get_admin_keyboard()
        )
        return
        
    # Формируем отчет
    report_text = f"📝 <b>Отчет по номеру:</b> <code>{normalized_phone}</code>\n\n"
    
    # --- Данные из Яндекс Парка ---
    if driver_in_park and driver_in_park.get("found"):
        report_text += "<b><u>Данные из Яндекс Парка</u></b>\n"
        
        name_parts = [
            driver_in_park.get('last_name'),
            driver_in_park.get('first_name'),
            driver_in_park.get('middle_name')
        ]
        driver_name = ' '.join(p for p in name_parts if p) or "Не указано"
        
        status_map = {
            "working": "✅ Работает", "not_working": "⏸ Не работает",
            "fired": "❌ Уволен", "blocked": "🚫 Заблокирован"
        }
        status = status_map.get(driver_in_park.get('work_status'), "-")
        
        report_text += f"👤 <b>ФИО:</b> {driver_name}\n"
        # Убрали ID водителя
        report_text += f"📊 <b>Статус:</b> {status}\n"
        
        if driver_in_park.get("balance") is not None:
            report_text += f"💰 <b>Баланс:</b> {driver_in_park.get('balance')} руб.\n"
        
        # Убрали информацию об автомобиле
        
        report_text += "\n"

    # --- Данные из Бота ---
    if user_in_db:
        report_text += "<b><u>Данные из бота</u></b>\n"
        report_text += f"👤 <b>Имя в Telegram:</b> {user_in_db.get('full_name')}\n"
        # Убрали Telegram ID
        if user_in_db.get('username'):
            report_text += f"📱 <b>Username:</b> @{user_in_db.get('username')}\n"
        
        if user_in_db.get('referrer_id'):
            referrer = db.get_user(user_in_db.get('referrer_id'))
            if referrer:
                # Убрали ID реферера
                report_text += f"👥 <b>Приглашен:</b> {referrer.get('full_name')}\n"
        
        report_text += "\n"
        
        # --- Приглашенные им пользователи ---
        try:
            user_id_for_search = user_in_db.get('user_id')
            logging.info(f"Searching for invited users by referrer_id: {user_id_for_search}")
            
            invited_users = db.get_invited_users_with_order_count(user_id_for_search)
            logging.info(f"Function returned: {invited_users}, type: {type(invited_users)}, length: {len(invited_users) if invited_users else 0}")
            
            # Всегда показываем раздел "Приглашенные им"
            report_text += f"<b><u>Приглашенные им:</u></b>\n"
            
            if invited_users and len(invited_users) > 0:
                report_text += f"<i>(найдено: {len(invited_users)})</i>\n"
                for i, ref in enumerate(invited_users, 1):
                    phone_display = ref.get('phone_number') if ref.get('phone_number') else 'не указан'
                    orders_count = ref.get('orders_count')
                    if orders_count is None:
                        orders_count = 0
                    else:
                        orders_count = int(orders_count)
                    
                    report_text += (
                        f"{i}. {ref.get('full_name')} (@{ref.get('username', '-')})\n"
                        f"   - 📱 {phone_display}\n"
                        f"   - 📈 Заказов: {orders_count}\n"
                    )
                report_text += "\n"
            else:
                report_text += "ℹ️ <i>Пользователь никого не пригласил</i>\n\n"
        except Exception as e:
            logging.error(f"Ошибка при получении приглашенных пользователей: {e}", exc_info=True)
            report_text += f"❌ <i>Ошибка при получении данных: {str(e)}</i>\n\n"
    elif driver_in_park and driver_in_park.get("found"):
        # Водитель найден в парке, но не в боте
        report_text += "<b><u>Данные из бота</u></b>\n"
        report_text += "ℹ️ <i>Пользователь не зарегистрирован в боте</i>\n"
        report_text += "<i>(Зарегистрирован напрямую в Яндекс Парке)</i>\n\n"

    try:
        await message.answer(report_text, parse_mode="HTML", reply_markup=get_admin_keyboard())
    except Exception as e:
        logging.error(f"Ошибка при отправке отчета: {e}")
        await message.answer(
            f"❌ Ошибка при формировании отчета. Попробуйте еще раз.\n\nОшибка: {str(e)}",
            reply_markup=get_admin_keyboard()
        )


@dp.message_handler(lambda message: message.text == "🔄 Обновить заказы", state="*")
async def update_all_orders(message: types.Message, state: FSMContext):
    """Обновить данные о заказах для всех рефералов"""
    user_id = message.from_user.id
    
    if not db.is_admin(user_id):
        await message.answer("У вас нет прав администратора")
        return
    
    msg = await message.answer("🔄 Обновляю данные о заказах для всех рефералов...\nЭто может занять некоторое время...")
    
    # Получаем всех пользователей, зарегистрированных в парке (не только тех, кто в referrals)
    referrals_to_check = db.get_all_park_users_for_order_check()
    
    if not referrals_to_check:
        await msg.edit_text("⚠️ Не найдено пользователей для проверки (зарегистрированных в парке)")
        return
    
    updated_count = 0
    failed_count = 0
    
    for i, referral in enumerate(referrals_to_check, 1):
        referred_id = referral["referred_id"]
        yandex_driver_id = referral["yandex_driver_id"]
        
        try:
            # Обновляем сообщение о прогрессе каждые 5 записей
            if i % 5 == 0 or i == 1:
                await msg.edit_text(f"🔄 Обновляю данные о заказах...\nОбработано: {i-1}/{len(referrals_to_check)}")
            
            orders_count = await yandex_api.get_driver_orders_count(yandex_driver_id)
            if orders_count is not None:
                # Обновляем заказы в referrals
                db.update_orders_count(referred_id, orders_count)
                
                # Если referrer_id есть, гарантируем что запись в referrals существует
                if referral.get("referrer_id"):
                    conn = db.get_connection()
                    cursor = conn.cursor()
                    try:
                        cursor.execute("""
                        INSERT OR IGNORE INTO referrals (referrer_id, referred_id, park_position)
                        VALUES (?, ?, ?)
                        """, (referral["referrer_id"], referred_id, referral.get("park_position")))
                        # Обновляем orders_count в случае, если запись уже существовала
                        cursor.execute("""
                        UPDATE referrals SET orders_count = ? WHERE referred_id = ?
                        """, (orders_count, referred_id))
                        conn.commit()
                    finally:
                        conn.close()
                
                updated_count += 1
                logging.info(f"Обновлены заказы для user_id={referred_id}, driver_id={yandex_driver_id}, заказов={orders_count}")
            else:
                failed_count += 1
                logging.warning(f"Не удалось получить заказы для user_id={referred_id}, driver_id={yandex_driver_id}")
            
            await asyncio.sleep(2.0)  # Увеличенная задержка, чтобы избежать 429 ошибок
        except Exception as e:
            failed_count += 1
            logging.error(f"Ошибка при обновлении заказов для {referred_id}: {e}", exc_info=True)
    
    result_text = f"✅ Обновление завершено!\n\n📊 Обновлено записей: {updated_count} из {len(referrals_to_check)}"
    if failed_count > 0:
        result_text += f"\n⚠️ Ошибок: {failed_count}"
    await msg.edit_text(result_text)


@dp.message_handler(lambda message: message.text == "📊 Статистика рефералов", state="*")
async def show_referral_statistics(message: types.Message, state: FSMContext):
    """Показать статистику по рефералам"""
    user_id = message.from_user.id
    
    if not db.is_admin(user_id):
        await message.answer("У вас нет прав администратора")
        return
    
    # Обновляем данные перед показом статистики
    msg = await message.answer("🔄 Обновляю данные о заказах...")
    referrals_to_check = db.get_all_park_users_for_order_check()
    
    if not referrals_to_check:
        await msg.edit_text("⚠️ Не найдено пользователей для проверки (зарегистрированных в парке)")
        await asyncio.sleep(2)
        await msg.delete()
    else:
        updated_count = 0
        failed_count = 0
        
        for i, referral in enumerate(referrals_to_check, 1):
            referred_id = referral["referred_id"]
            yandex_driver_id = referral["yandex_driver_id"]
            
            try:
                # Обновляем сообщение о прогрессе
                if i % 5 == 0 or i == 1:
                    await msg.edit_text(f"🔄 Обновляю данные о заказах...\nОбработано: {i-1}/{len(referrals_to_check)}")
                
                if not yandex_driver_id:
                    failed_count += 1
                    logging.warning(f"Пустой driver_id для user_id={referred_id}")
                    continue
                
                logging.info(f"Попытка получить заказы для user_id={referred_id}, driver_id={yandex_driver_id}")
                orders_count = await yandex_api.get_driver_orders_count(yandex_driver_id)
                logging.info(f"Результат для user_id={referred_id}: orders_count={orders_count}")
                
                if orders_count is not None:
                    # Обновляем заказы в referrals
                    db.update_orders_count(referred_id, orders_count)
                    
                    # Если referrer_id есть, гарантируем что запись в referrals существует
                    if referral.get("referrer_id"):
                        conn = db.get_connection()
                        cursor = conn.cursor()
                        try:
                            cursor.execute("""
                            INSERT OR IGNORE INTO referrals (referrer_id, referred_id, park_position)
                            VALUES (?, ?, ?)
                            """, (referral["referrer_id"], referred_id, referral.get("park_position")))
                            # Обновляем orders_count в случае, если запись уже существовала
                            cursor.execute("""
                            UPDATE referrals SET orders_count = ? WHERE referred_id = ?
                            """, (orders_count, referred_id))
                            conn.commit()
                        finally:
                            conn.close()
                    
                    updated_count += 1
                    logging.info(f"Обновлены заказы для user_id={referred_id}, driver_id={yandex_driver_id}, заказов={orders_count}")
                else:
                    failed_count += 1
                    logging.warning(f"Не удалось получить заказы для user_id={referred_id}, driver_id={yandex_driver_id} - API вернул None")
                
                # Увеличиваем задержку, чтобы избежать 429 ошибок (лимит API)
                await asyncio.sleep(2.0)
            except Exception as e:
                failed_count += 1
                logging.error(f"Ошибка при обновлении заказов для {referred_id}: {e}", exc_info=True)
        
        result_text = f"✅ Обновлено: {updated_count} из {len(referrals_to_check)}"
        if failed_count > 0:
            result_text += f"\n⚠️ Ошибок: {failed_count}"
        await msg.edit_text(result_text)
        await asyncio.sleep(1)  # Небольшая задержка, чтобы данные записались в БД
        await msg.delete()
    
    # Получаем обновленные данные из БД
    referrals_data = db.get_referral_stats()
    
    if not referrals_data:
        await message.answer("📊 Пока нет данных по рефералам.")
        return

    # Логируем данные для отладки
    logging.info(f"Получено {len(referrals_data)} записей статистики рефералов")
    for ref in referrals_data[:3]:  # Логируем первые 3 для отладки
        logging.info(f"Статистика: referrer={ref.get('referrer_full_name')}, referred={ref.get('referred_full_name')}, orders={ref.get('orders_count')}")

    stats_text = f"📊 <b>Статистика по рефералам (всего: {len(referrals_data)})</b>\n\n"
    
    current_referrer_id = None
    # Показываем не более 30 записей, чтобы не превысить лимит сообщения
    for ref in referrals_data[:30]:
        if ref['referrer_user_id'] != current_referrer_id:
            current_referrer_id = ref['referrer_user_id']
            stats_text += (
                f"----------------------------------\n"
                f"<b>Кто пригласил:</b> {ref['referrer_full_name']} "
                f"(@{ref['referrer_username'] if ref['referrer_username'] else 'нет username'})\n\n"
            )
        
        orders_count = ref.get('orders_count', 0)
        if orders_count is None:
            orders_count = 0
        else:
            orders_count = int(orders_count)
        
        stats_text += (
            f"  ➡️ <b>Кого пригласил:</b> {ref['referred_full_name']} "
            f"(@{ref['referred_username'] if ref['referred_username'] else 'нет username'})\n"
            f"  📈 <b>Выполнено заказов:</b> {orders_count}\n\n"
        )
    
    if len(referrals_data) > 30:
        stats_text += f"\n... и ещё {len(referrals_data) - 30} записей."
    
    # Разбиваем на несколько сообщений, если текст слишком длинный
    if len(stats_text) > 4096:
        for i in range(0, len(stats_text), 4096):
            await message.answer(stats_text[i:i + 4096], parse_mode="HTML")
    else:
        await message.answer(stats_text, parse_mode="HTML")


@dp.message_handler(lambda message: message.text == "📈 Статистика", state="*")
async def show_statistics(message: types.Message, state: FSMContext):
    """Показать статистику"""
    user_id = message.from_user.id
    
    if not db.is_admin(user_id):
        await message.answer("У вас нет прав администратора")
        return
    
    users = db.get_all_users()
    
    # Подсчитываем статистику
    total_users = len(users)
    registered_in_park = sum(1 for u in users if u.get('is_registered_in_park'))
    not_registered = total_users - registered_in_park
    
    # Статистика по категориям (только для не зарегистрированных в парке)
    categories = {}
    referrals_count = 0
    
    for user in users:
        if not user.get('is_registered_in_park'):
            category = user.get('category', 'unknown')
            categories[category] = categories.get(category, 0) + 1
        
        if user.get('referrer_id'):
            referrals_count += 1
    
    stats_text = (
        f"📈 <b>Общая статистика</b>\n\n"
        f"👥 <b>Всего пользователей:</b> {total_users}\n"
        f"✅ <b>Зарегистрированы в парке:</b> {registered_in_park}\n"
        f"📝 <b>В процессе регистрации:</b> {not_registered}\n"
        f"🔗 <b>По реферальным ссылкам:</b> {referrals_count}\n\n"
    )
    
    if categories:
        stats_text += f"📊 <b>По категориям (в процессе):</b>\n"
        for category, count in categories.items():
            category_info = DOCUMENT_REQUIREMENTS.get(category, {})
            emoji = category_info.get('emoji', '❓')
            name = category_info.get('name', category)
            stats_text += f"{emoji} {name}: {count}\n"
    
    # Статистика рефералов
    total_referrals = 0
    for user in users:
        refs = db.get_referrals(user['user_id'])
        total_referrals += len(refs)
    
    stats_text += f"\n👥 <b>Всего приглашено:</b> {total_referrals}"
    
    await message.answer(stats_text, parse_mode="HTML")


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
