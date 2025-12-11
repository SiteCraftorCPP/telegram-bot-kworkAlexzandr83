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
        "orders_required": 30  # Для грузового
    },
    "car_courier": {
        "name": "Курьер на авто",
        "emoji": "🚗",
        "orders_required": 45  # Для легкового
    },
    "foot_courier": {
        "name": "Пеший курьер",
        "emoji": "🚶",
        "orders_required": 45
    }
}


def get_main_menu_keyboard(is_admin=False):
    """Главное меню с кнопками"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        KeyboardButton("🚀 Начать работать"),
        KeyboardButton("👥 Пригласить друзей")
    )
    keyboard.add(KeyboardButton("👤 Профиль"))
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
    keyboard.add(KeyboardButton("🔍 Поиск по номеру"))
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
    # Ограничиваем ожидание ответа от API, чтобы бот не "висел" надолго
    try:
        driver_info = await asyncio.wait_for(
            yandex_api.check_driver_by_phone(cleaned_phone),
            timeout=10.0
        )
    except asyncio.TimeoutError:
        logging.warning("Timeout while checking driver in Yandex Park")
        driver_info = {"found": False, "error": "timeout"}
    except Exception as e:
        logging.error(f"Error while checking driver: {e}")
        driver_info = {"found": False, "error": str(e)}
    
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
        
        # Сохраняем пользователя с реферальной информацией
        # ВАЖНО: referrer_id НЕ обнуляем, даже если пользователь уже в парке
        db.add_user(
            user_id=user_info["id"],
            username=user_info["username"],
            full_name=user_info["full_name"],
            first_name=user_info["first_name"],
            phone_number=cleaned_phone,
            category=None,
            referrer_id=referrer_id,  # Сохраняем реферала, даже если пользователь уже в парке
            is_registered_in_park=True,
            yandex_driver_id=driver_id,
            yandex_driver_name=driver_name,
            park_position=park_position
        )
        
        # Если есть реферер И пользователь уже в парке, создаем запись реферала с позицией
        if referrer_id:
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
        # Водитель не найден, сохраняем пользователя и предлагаем выбрать категорию позже
        referrer_id = user_data[user_id].get("referrer_id")
        user_info = user_data[user_id]["user_info"]
        db.add_user(
            user_id=user_info["id"],
            username=user_info["username"],
            full_name=user_info["full_name"],
            first_name=user_info["first_name"],
            phone_number=cleaned_phone,
            category=None,
            referrer_id=referrer_id,
            is_registered_in_park=False
        )
        await checking_msg.edit_text(
            "📋 <b>Вы ещё не зарегистрированы в Яндекс Парке</b>\n\n"
            "Нажмите «🚀 Начать работать» и выберите категорию. Менеджер свяжется с вами в ближайшее время.",
            parse_mode="HTML"
        )
        # Показываем главное меню сразу, чтобы были видны кнопки
        is_admin = db.is_admin(user_id)
        await message.answer(
            "Главное меню:",
            reply_markup=get_main_menu_keyboard(is_admin)
        )
        # Очищаем временные данные и завершаем FSM
        user_data.pop(user_id, None)
        await state.finish()


@dp.message_handler(lambda message: message.text == "🚀 Начать работать", state="*")
async def start_work_flow(message: types.Message, state: FSMContext):
    """Запуск выбора категории для подключения"""
    user_id = message.from_user.id
    user = db.get_user(user_id)
    if not user or not user.get("phone_number"):
        await message.answer("Сначала отправьте номер телефона через /start.")
        return
    if user and user.get("is_registered_in_park"):
        await message.answer("Вы уже зарегистрированы в Яндекс Парке.")
        return
    # Готовим данные в user_data (для referrer/username)
    if user_id not in user_data:
        user_data[user_id] = {
            "category": None,
            "phone_number": user.get("phone_number") if user else None,
            "referrer_id": user.get("referrer_id") if user else None,
            "user_info": {
                "id": user_id,
                "username": user.get("username") if user else message.from_user.username,
                "full_name": user.get("full_name") if user else message.from_user.full_name,
                "first_name": user.get("first_name") if user else message.from_user.first_name,
            }
        }
    await message.answer(
        "Выберите вашу категорию:",
        reply_markup=get_category_keyboard()
    )
    await RegistrationStates.waiting_for_category.set()


@dp.callback_query_handler(lambda c: c.data.startswith("category:"), state=RegistrationStates.waiting_for_category)
async def process_category_selection(callback_query: types.CallbackQuery, state: FSMContext):
    """Обработчик выбора категории без загрузки документов"""
    await callback_query.answer()
    
    user_id = callback_query.from_user.id
    category = callback_query.data.split(":")[1]
    
    # Обновляем данные и БД
    if user_id not in user_data:
        user_data[user_id] = {"user_info": {"id": user_id, "username": callback_query.from_user.username,
                                            "full_name": callback_query.from_user.full_name,
                                            "first_name": callback_query.from_user.first_name}}
    user_data[user_id]["category"] = category
    
    # Обновляем категорию в БД (если запись уже есть после ввода телефона)
    conn = db.get_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE users SET category = ? WHERE user_id = ?", (category, user_id))
        conn.commit()
    finally:
        conn.close()
    
    # Отправляем уведомление в канал
    await send_notification_to_channel_simple(user_id, category, callback_query.bot)
    
    await callback_query.message.edit_text(
        "✅ Ваша заявка принята. Менеджер свяжется с вами в ближайшее время.",
        parse_mode="HTML"
    )
    
    # Чистим состояние
    user_data.pop(user_id, None)
    await state.finish()


async def send_notification_to_channel_simple(user_id: int, category: str, bot: Bot):
    """Отправляет текстовое уведомление в канал о новой заявке без фотографий"""
    try:
        user = db.get_user(user_id)
        cat = DOCUMENT_REQUIREMENTS.get(category, {})
        referrer_text = ""
        if user and user.get("referrer_id"):
            referrer = db.get_user(user.get("referrer_id"))
            if referrer:
                ref_username = referrer.get("username")
                ref_link = f"@{ref_username}" if ref_username else f'<a href="tg://user?id={referrer.get("user_id")}">профиль</a>'
                referrer_text = (
                    f"\n👥 Пригласил: {referrer.get('full_name')} "
                    f"({ref_link})"
                )
        
        if user and user.get("username"):
            username_link = f"@{user.get('username')}"
        else:
            # Кликабельная ссылка на профиль, если username отсутствует
            username_link = f'<a href="tg://user?id={user_id}">профиль</a>'
        
        phone = user.get("phone_number") if user else "не указан"
        full_name = user.get("full_name") if user else "Не указано"
        
        text = (
            "🆕 <b>Новая заявка</b>\n\n"
            f"{cat.get('emoji', '📌')} Категория: {cat.get('name', category)}\n"
            f"👤 Имя: {full_name}\n"
            f"🔗 Telegram: {username_link}\n"
            f"📱 Телефон: {phone}"
            f"{referrer_text}"
        )
        
        await bot.send_message(
            chat_id=NOTIFICATION_CHANNEL_ID,
            text=text,
            parse_mode="HTML"
        )
        logging.info(f"Уведомление для пользователя {user_id} отправлено в канал без фото")
    except Exception as e:
        logging.error(f"Ошибка при отправке уведомления в канал: {e}")


@dp.message_handler(lambda message: message.text == "👥 Пригласить друзей", state="*")
async def show_referral_link(message: types.Message, state: FSMContext):
    """Показать реферальную ссылку"""
    user_id = message.from_user.id
    bot_info = await bot.get_me()
    referral_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
    # Добавляем zero-width space, чтобы ссылка не автокликалась и её было удобно копировать
    copy_safe_link = referral_link.replace("https://", "https://\u2060")
    
    user = db.get_user(user_id)
    if not user:
        await message.answer("Сначала пройдите регистрацию, отправив /start")
        return
    
    stats = db.get_user_stats(user_id)
    
    referral_text = (
        "🔗 <b>Ваша реферальная ссылка:</b>\n"
        f"{copy_safe_link}\n\n"
        f"👥 Приглашено: {stats['invited_count']}\n\n"
        "💰 Бонусы: 1000 руб вам / 500 руб другу\n"
        "Условие: 45 заказов (экспресс) или 30 (грузовой)."
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
        
    # Формируем компактный отчет
    parts = [f"📝 <b>Отчет по номеру:</b> <code>{normalized_phone}</code>"]
    
    # --- Данные из Яндекс Парка ---
    if driver_in_park and driver_in_park.get("found"):
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
        
        driver_id = driver_in_park.get("driver_id")
        orders_count = 0
        if driver_id:
            try:
                logging.info(f"[ADMIN_SEARCH] Запрос заказов из парка для driver_id={driver_id}")
                orders_count = await yandex_api.get_driver_orders_count(driver_id) or 0
                if user_in_db and user_in_db.get('user_id'):
                    db.update_orders_count(user_in_db['user_id'], orders_count)
            except Exception as e:
                logging.error(f"[ADMIN_SEARCH] ❌ Ошибка получения заказов: {e}", exc_info=True)
        
        park_block = [
            f"👤 ФИО: {driver_name}",
            f"📊 Статус: {status}",
            f"📈 Выполнено заказов: {orders_count}"
        ]
        parts.append("\n".join(park_block))
    else:
        parts.append("❔ В Яндекс Парке не найден")

    # --- Данные из Бота ---
    if user_in_db:
        bot_lines = [f"👤 Имя в Telegram: {user_in_db.get('full_name')}"]
        if user_in_db.get('username'):
            bot_lines.append(f"📱 Username: @{user_in_db.get('username')}")
        if user_in_db.get('phone_number'):
            bot_lines.append(f"📞 Телефон: {user_in_db.get('phone_number')}")
        # Показываем, кто пригласил (ищем в users.referrer_id, а при отсутствии — в referrals)
        referrer_id = user_in_db.get('referrer_id')
        if not referrer_id:
            try:
                conn = db.get_connection()
                cur = conn.cursor()
                cur.execute("SELECT referrer_id FROM referrals WHERE referred_id = ? LIMIT 1", (user_in_db.get('user_id'),))
                row = cur.fetchone()
                if row and row[0]:
                    referrer_id = row[0]
            except Exception as e:
                logging.error(f"Ошибка при поиске referrer_id в referrals: {e}")
            finally:
                try:
                    conn.close()
                except:
                    pass
        if referrer_id:
            ref = db.get_user(referrer_id)
            if ref:
                ref_username = ref.get('username')
                ref_phone = ref.get('phone_number') or 'не указан'
                ref_link = f"@{ref_username}" if ref_username else f'<a href="tg://user?id={ref.get("user_id")}">профиль</a>'
                bot_lines.append("")  # пустая строка для визуального разделения
                bot_lines.append("👥 Пользователя пригласил:")
                bot_lines.append(f"👤 Имя в Telegram: {ref.get('full_name')}")
                bot_lines.append(f"📱 Username: {ref_link}")
                bot_lines.append(f"📞 Телефон: {ref_phone}")
        parts.append("\n".join(bot_lines))
        
        # --- Приглашенные им пользователи ---
        try:
            invited_users = db.get_invited_users_with_order_count(user_in_db['user_id'])
            if invited_users:
                invite_blocks = []
                for ref in invited_users:
                    uname = ref.get('username')
                    uname_txt = f"@{uname}" if uname else "нет username"
                    phone_display = ref.get('phone_number') or 'не указан'
                    invite_blocks.append(
                        "\n".join([
                            f"👤 Имя в Telegram: {ref.get('full_name')}",
                            f"📱 Username: {uname_txt}",
                            f"📞 Телефон: {phone_display}",
                            f"📈 Заказов: {ref.get('orders_count',0)}",
                        ])
                    )
                parts.append("Приглашенные им:\n\n" + "\n\n".join(invite_blocks))
            else:
                parts.append("Приглашенные им:\n— нет данных")
        except Exception as e:
            logging.error(f"Ошибка при получении приглашенных пользователей: {e}", exc_info=True)
            parts.append("Приглашенные им: ошибка получения данных")
    elif driver_in_park and driver_in_park.get("found"):
        parts.append("ℹ️ В боте не зарегистрирован (но есть в парке)")

    report_text = "\n\n".join(parts)

    try:
        await message.answer(report_text, parse_mode="HTML", reply_markup=get_admin_keyboard())
    except Exception as e:
        logging.error(f"Ошибка при отправке отчета: {e}")
        await message.answer(
            f"❌ Ошибка при формировании отчета. Попробуйте еще раз.\n\nОшибка: {str(e)}",
            reply_markup=get_admin_keyboard()
        )


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
