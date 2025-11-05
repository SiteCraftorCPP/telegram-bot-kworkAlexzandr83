import asyncio
import logging
from database import Database
from yandex_park_api import YandexParkAPI
from config import YANDEX_PARK_ID, YANDEX_API_KEY, YANDEX_CLIENT_ID
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


async def check_orders():
    """Основная функция для проверки заказов"""
    logging.info("Starting order check cycle...")
    
    db = Database()
    yandex_api = YandexParkAPI(YANDEX_PARK_ID, YANDEX_API_KEY, YANDEX_CLIENT_ID)
    
    # Получаем всех рефералов, которых нужно проверить
    referrals_to_check = db.get_referrals_for_order_check()
    
    if not referrals_to_check:
        logging.info("No new referrals in park to check.")
        return
        
    logging.info(f"Found {len(referrals_to_check)} referrals to check.")
    
    for referral in referrals_to_check:
        referred_id = referral["referred_id"]
        yandex_driver_id = referral["yandex_driver_id"]
        
        try:
            # Получаем количество заказов из API
            orders_count = await yandex_api.get_driver_orders_count(yandex_driver_id)
            
            if orders_count is not None:
                logging.info(f"Driver {yandex_driver_id} (user {referred_id}) has {orders_count} orders.")
                
                # Обновляем количество заказов в БД
                db.update_orders_count(referred_id, orders_count)
            else:
                logging.warning(f"Could not get orders count for driver {yandex_driver_id} (user {referred_id}).")
        
        except Exception as e:
            logging.error(f"Error checking orders for driver {yandex_driver_id}: {e}")
        
        # Небольшая задержка, чтобы не перегружать API
        await asyncio.sleep(1)
        
    logging.info("Order check cycle finished.")

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
