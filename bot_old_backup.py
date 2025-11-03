import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from config import BOT_TOKEN, NOTIFICATION_CHANNEL_ID

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Состояния для FSM
class RegistrationStates(StatesGroup):
    waiting_for_category = State()
    waiting_for_documents = State()

# Инициализация бота и диспетчера
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot, storage=storage)

# Словарь для хранения данных пользователей
user_data = {}


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


# Требования к документам для каждой категории
DOCUMENT_REQUIREMENTS = {
    "truck_driver": {
        "name": "Водитель грузового авто",
        "emoji": "🚛",
        "text": "📋 Для регистрации в качестве <b>водителя грузового авто</b> отправьте следующие документы:\n\n"
               "1️⃣ Паспорт (разворот с фото - 2 страницы)\n"
               "2️⃣ Свидетельство о регистрации транспортного средства\n"
               "3️⃣ Водительское удостоверение (обе стороны)\n\n"
               "📸 Отправьте все фото одним сообщением",
        "required_count": 4  # паспорт 2 стр + СТС + права 2 стр
    },
    "car_courier": {
        "name": "Курьер на авто",
        "emoji": "🚗",
        "text": "📋 Для регистрации в качестве <b>курьера на авто</b> отправьте следующие документы:\n\n"
               "1️⃣ Паспорт (разворот с фото - 2 страницы)\n"
               "2️⃣ Свидетельство о регистрации транспортного средства\n"
               "3️⃣ Водительское удостоверение (обе стороны)\n\n"
               "📸 Отправьте все фото одним сообщением",
        "required_count": 4
    },
    "foot_courier": {
        "name": "Пеший курьер",
        "emoji": "🚶",
        "text": "📋 Для регистрации в качестве <b>пешего курьера</b> отправьте следующие документы:\n\n"
               "1️⃣ Паспорт (разворот с фото - 2 страницы)\n\n"
               "📸 Отправьте обе страницы паспорта.",
        "required_count": 2
    }
}


@dp.message_handler(CommandStart(), state="*")
async def cmd_start(message: types.Message, state: FSMContext):
    """Обработчик команды /start"""
    user = message.from_user
    
    # Сбрасываем состояние если было
    await state.finish()
    
    # Инициализируем данные пользователя
    user_data[user.id] = {
        "category": None,
        "photos": [],
        "user_info": {
            "id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "first_name": user.first_name
        }
    }
    
    # Отправляем приветствие с категориями
    welcome_text = (
        f"👋 Здравствуйте, {user.first_name}!\n\n"
        f"Выберите категорию для регистрации:"
    )
    
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
    
    # Сохраняем выбранную категорию
    if user_id not in user_data:
        user_data[user_id] = {"photos": [], "user_info": {}}
    
    user_data[user_id]["category"] = category
    
    # Получаем требования к документам
    doc_info = DOCUMENT_REQUIREMENTS[category]
    
    # Отправляем инструкцию
    await callback_query.message.edit_text(
        text=doc_info["text"],
        parse_mode="HTML"
    )
    
    # Переходим в состояние ожидания документов
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
    photo = message.photo[-1]  # Берём самое большое разрешение
    user_data[user_id]["photos"].append(photo.file_id)
    
    category = user_data[user_id]["category"]
    required_count = DOCUMENT_REQUIREMENTS[category]["required_count"]
    current_count = len(user_data[user_id]["photos"])
    
    # Проверяем, собрали ли мы все документы
    if current_count < required_count:
        await message.answer(
            f"✅ Фото {current_count} из {required_count} получено.\n"
            f"Отправьте ещё {required_count - current_count} фото."
        )
    else:
        # Все документы собраны
        await message.answer(
            "✅ Все документы получены!\n"
            "Отправляем информацию на проверку..."
        )
        
        # Отправляем уведомление в канал
        await send_notification_to_channel(user_id, message.bot)
        
        # Отправляем пользователю ссылки на формы
        await message.answer(
            "📝 <b>Откройте нужную форму заявки на подключение:</b>",
            parse_mode="HTML",
            reply_markup=get_form_links_keyboard()
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
        
        category_info = DOCUMENT_REQUIREMENTS[category]
        
        # Формируем текст уведомления
        user_link = f"<a href='tg://user?id={user_info['id']}'>{user_info['full_name']}</a>"
        notification_text = (
            f"🆕 <b>Новая регистрация!</b>\n\n"
            f"{category_info['emoji']} <b>Категория:</b> {category_info['name']}\n\n"
            f"👤 <b>Пользователь:</b> {user_link}\n"
            f"🆔 <b>Username:</b> @{user_info['username'] if user_info['username'] else 'не указан'}\n"
            f"🔢 <b>ID:</b> <code>{user_info['id']}</code>\n\n"
            f"📄 <b>Документы:</b> {len(photos)} фото"
        )
        
        # Формируем медиа группу для отправки всех фото одним сообщением
        media = []
        for i, photo_id in enumerate(photos):
            if i == 0:
                # Первое фото с подписью
                media.append(types.InputMediaPhoto(
                    media=photo_id,
                    caption=notification_text,
                    parse_mode="HTML"
                ))
            else:
                # Остальные фото без подписи
                media.append(types.InputMediaPhoto(media=photo_id))
        
        # Отправляем медиа группу
        await bot.send_media_group(
            chat_id=NOTIFICATION_CHANNEL_ID,
            media=media
        )
        
        logging.info(f"Уведомление для пользователя {user_id} успешно отправлено в канал")
        
    except Exception as e:
        logging.error(f"Ошибка при отправке уведомления в канал: {e}")


async def main():
    """Запуск бота"""
    logging.info("Запуск бота...")
    
    try:
        # Удаляем старые обновления
        await bot.delete_webhook(drop_pending_updates=True)
        
        # Запускаем polling
        await dp.start_polling()
    except Exception as e:
        logging.error(f"Ошибка при запуске бота: {e}")


if __name__ == "__main__":
    asyncio.run(main())

