import asyncio
import logging
from database import Database
from yandex_park_api import YandexParkAPI
from config import YANDEX_PARK_ID, YANDEX_API_KEY, YANDEX_CLIENT_ID, NOTIFICATION_CHANNEL_ID, BOT_TOKEN
from aiogram import Bot
import time

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='order_checker.log',
    filemode='a'
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console.setFormatter(formatter)
logging.getLogger('').addHandler(console)

# Инициализация бота для отправки уведомлений
bot = Bot(token=BOT_TOKEN)

# Пороговые значения заказов для разных позиций
ORDERS_THRESHOLD = {
    "cargo": 30,  # Грузовой - 30 заказов
    "express": 45  # Экспресс - 45 заказов
}


async def send_referrer_notification(referrer_id: int, referred: dict, park_position: str, orders_count: int):
    """Отправляет уведомление рефереру о том, что его реферал выполнил нужное количество заказов"""
    try:
        position_name = "грузовой" if park_position == "cargo" else "экспресс"
        threshold = ORDERS_THRESHOLD.get(park_position, 45)
        
        referrer_text = (
            f"🎉 <b>Отличные новости!</b>\n\n"
            f"👤 Пользователь <b>{referred.get('full_name')}</b>, которого вы пригласили, "
            f"выполнил нужное количество заказов!\n\n"
            f"📊 <b>Позиция:</b> {position_name}\n"
            f"📈 <b>Выполнено заказов:</b> {orders_count}\n"
            f"✅ <b>Требовалось:</b> {threshold}\n\n"
            f"💰 <b>Ваш бонус:</b> 1000 руб.\n\n"
            f"Спасибо за приглашение!"
        )
        
        await bot.send_message(
            chat_id=referrer_id,
            text=referrer_text,
            parse_mode="HTML"
        )
        
        logging.info(f"Отправлено уведомление рефереру {referrer_id} о достижении цели рефералом")
        
    except Exception as e:
        logging.error(f"Ошибка при отправке уведомления рефереру {referrer_id}: {e}", exc_info=True)


async def send_referred_notification(referred_id: int, referrer: dict, park_position: str, orders_count: int):
    """Отправляет уведомление рефералу о том, что он выполнил нужное количество заказов"""
    try:
        position_name = "грузовой" if park_position == "cargo" else "экспресс"
        threshold = ORDERS_THRESHOLD.get(park_position, 45)
        
        referred_text = (
            f"🎉 <b>Поздравляем!</b>\n\n"
            f"Вы выполнили нужное количество заказов!\n\n"
            f"📊 <b>Позиция:</b> {position_name}\n"
            f"📈 <b>Выполнено заказов:</b> {orders_count}\n"
            f"✅ <b>Требовалось:</b> {threshold}\n\n"
            f"💰 <b>Ваш бонус:</b> 500 руб.\n"
            f"👥 <b>Бонус вашему рефереру:</b> 1000 руб.\n\n"
            f"Спасибо за активную работу!"
        )
        
        await bot.send_message(
            chat_id=referred_id,
            text=referred_text,
            parse_mode="HTML"
        )
        
        logging.info(f"Отправлено уведомление рефералу {referred_id} о достижении цели")
        
    except Exception as e:
        logging.error(f"Ошибка при отправке уведомления рефералу {referred_id}: {e}", exc_info=True)


async def send_goal_notification(referrer_id: int, referred_id: int, park_position: str, orders_count: int):
    """Отправляет уведомление в канал и пользователям о достижении цели рефералом"""
    try:
        db = Database()
        
        # Получаем информацию о реферере и реферале
        referrer = db.get_user(referrer_id)
        referred = db.get_user(referred_id)
        
        if not referrer or not referred:
            logging.warning(f"Не найдены пользователи для уведомления: referrer_id={referrer_id}, referred_id={referred_id}")
            return
        
        # Определяем позицию в читаемом виде
        position_name = "грузовой" if park_position == "cargo" else "экспресс"
        threshold = ORDERS_THRESHOLD.get(park_position, 45)
        
        # Отправляем уведомление в канал
        notification_text = (
            f"🎉 <b>Достижение цели!</b>\n\n"
            f"👤 <b>Реферал:</b> {referred.get('full_name')}\n"
            f"📱 <b>Username:</b> @{referred.get('username') if referred.get('username') else 'не указан'}\n"
            f"📱 <b>Телефон:</b> {referred.get('phone_number') or 'не указан'}\n\n"
            f"👥 <b>Приглашен пользователем:</b> {referrer.get('full_name')}\n"
            f"📱 <b>Username реферера:</b> @{referrer.get('username') if referrer.get('username') else 'не указан'}\n\n"
            f"📊 <b>Позиция:</b> {position_name}\n"
            f"📈 <b>Выполнено заказов:</b> {orders_count}\n"
            f"✅ <b>Требовалось:</b> {threshold}\n\n"
            f"💰 <b>Бонус рефереру:</b> 1000 руб."
        )
        
        await bot.send_message(
            chat_id=NOTIFICATION_CHANNEL_ID,
            text=notification_text,
            parse_mode="HTML"
        )
        
        # Отправляем личные уведомления пользователям
        await send_referrer_notification(referrer_id, referred, park_position, orders_count)
        await send_referred_notification(referred_id, referrer, park_position, orders_count)
        
        logging.info(f"Отправлены уведомления о достижении цели: referrer_id={referrer_id}, referred_id={referred_id}")
        
    except Exception as e:
        logging.error(f"Ошибка при отправке уведомления о достижении цели: {e}", exc_info=True)


async def check_orders():
    """Основная функция для проверки заказов"""
    logging.info("=" * 80)
    logging.info("[CHECK_CYCLE] Starting order check cycle...")
    
    db = Database()
    yandex_api = YandexParkAPI(YANDEX_PARK_ID, YANDEX_API_KEY, YANDEX_CLIENT_ID)
    
    # Получаем всех рефералов, которых нужно проверить
    referrals_to_check = db.get_referrals_for_order_check()
    
    logging.info(f"[CHECK_CYCLE] Метод get_referrals_for_order_check() вернул: {len(referrals_to_check)} записей")
    
    # Также логируем ВСЕХ пользователей в парке для отладки
    all_park_users = db.get_all_park_users_for_order_check()
    logging.info(f"[CHECK_CYCLE] Всего пользователей в парке (метод get_all_park_users_for_order_check): {len(all_park_users)}")
    
    if not referrals_to_check:
        logging.warning("[CHECK_CYCLE] No referrals found in get_referrals_for_order_check()!")
        logging.info("[CHECK_CYCLE] Проверяем альтернативный метод...")
        
        # Используем альтернативный метод, если основной не нашел записей
        if all_park_users:
            logging.info(f"[CHECK_CYCLE] Используем альтернативный список: {len(all_park_users)} пользователей")
            referrals_to_check = all_park_users
        else:
            logging.info("[CHECK_CYCLE] Нет пользователей для проверки.")
            return
    
    logging.info(f"[CHECK_CYCLE] Будет проверено {len(referrals_to_check)} пользователей")
    
    for idx, referral in enumerate(referrals_to_check, 1):
        referred_id = referral["referred_id"]
        referrer_id = referral.get("referrer_id")
        yandex_driver_id = referral["yandex_driver_id"]
        park_position = referral.get("park_position")
        current_orders_count = referral.get("orders_count", 0)
        notification_sent = referral.get("notification_sent", 0)
        
        logging.info(f"[CHECK_{idx}/{len(referrals_to_check)}] Проверяем user_id={referred_id}, driver_id={yandex_driver_id}, referrer_id={referrer_id}")
        
        try:
            # Если позиция не определена, пытаемся её определить
            if not park_position and yandex_driver_id:
                logging.info(f"[CHECK_{idx}] Позиция не определена, определяем...")
                park_position = await yandex_api.get_driver_position(yandex_driver_id)
                if park_position:
                    db.update_user_park_position(referred_id, park_position)
                    logging.info(f"[CHECK_{idx}] Определена позиция для водителя {yandex_driver_id}: {park_position}")
                    # Обновляем позицию в referrals
                    conn = db.get_connection()
                    cursor = conn.cursor()
                    try:
                        cursor.execute("""
                        UPDATE referrals
                        SET park_position = ?
                        WHERE referred_id = ?
                        """, (park_position, referred_id))
                        conn.commit()
                    finally:
                        conn.close()
                else:
                    logging.warning(f"[CHECK_{idx}] Не удалось определить позицию для {yandex_driver_id}")
            
            # Получаем количество заказов из API
            logging.info(f"[CHECK_{idx}] Запрашиваем заказы из API для driver_id={yandex_driver_id}...")
            orders_count = await yandex_api.get_driver_orders_count(yandex_driver_id)
            
            if orders_count is not None:
                logging.info(f"[CHECK_{idx}] ✓ Driver {yandex_driver_id} (user {referred_id}): получено {orders_count} заказов (было в БД: {current_orders_count})")
                
                # Обновляем количество заказов в БД
                update_success = db.update_orders_count(referred_id, orders_count)
                if update_success:
                    logging.info(f"[CHECK_{idx}] ✓ Обновлено в БД: user_id={referred_id}, orders_count={orders_count}")
                else:
                    logging.error(f"[CHECK_{idx}] ✗ Не удалось обновить БД для user_id={referred_id}")
                
                # Проверяем, достиг ли реферал нужного числа заказов
                if park_position and park_position in ORDERS_THRESHOLD:
                    threshold = ORDERS_THRESHOLD[park_position]
                    logging.info(f"[CHECK_{idx}] Проверка порога: {orders_count} >= {threshold}? notification_sent={notification_sent}")
                    
                    # Если достигнута цель и уведомление еще не отправлялось
                    if orders_count >= threshold and not notification_sent and referrer_id:
                        logging.info(f"[CHECK_{idx}] 🎉 Реферал {referred_id} достиг цели: {orders_count} заказов (требуется {threshold} для {park_position})")
                        
                        # Отправляем уведомление в канал
                        await send_goal_notification(referrer_id, referred_id, park_position, orders_count)
                        
                        # Отмечаем, что уведомление отправлено
                        db.mark_notification_sent(referrer_id, referred_id)
                    elif not referrer_id:
                        logging.warning(f"[CHECK_{idx}] Пользователь {referred_id} достиг порога, но нет referrer_id")
                else:
                    logging.warning(f"[CHECK_{idx}] Позиция не определена или не в пороговых значениях: park_position={park_position}")
            else:
                logging.warning(f"[CHECK_{idx}] ✗ Could not get orders count for driver {yandex_driver_id} (user {referred_id}). API вернул None.")
        
        except Exception as e:
            logging.error(f"[CHECK_{idx}] ✗ Error checking orders for driver {yandex_driver_id}: {e}", exc_info=True)
        
        # Небольшая задержка, чтобы не перегружать API
        await asyncio.sleep(1.5)
    
    logging.info("=" * 80)
    logging.info("[CHECK_CYCLE] Order check cycle finished.")
    logging.info("=" * 80)

async def main():
    """Запускает цикл проверки заказов каждые N секунд"""
    while True:
        await check_orders()
        sleep_duration = 3600 # 1 час
        logging.info(f"Sleeping for {sleep_duration / 60} minutes...")
        await asyncio.sleep(sleep_duration)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Order checker stopped by user.")
