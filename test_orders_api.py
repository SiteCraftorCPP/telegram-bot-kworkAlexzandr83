#!/usr/bin/env python3
"""
Скрипт для тестирования получения заказов через API
Использование: python3 test_orders_api.py
"""
import asyncio
import logging
from yandex_park_api import YandexParkAPI
from database import Database
from config import YANDEX_PARK_ID, YANDEX_API_KEY, YANDEX_CLIENT_ID

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

async def test_orders():
    """Тестируем получение заказов для всех водителей в БД"""
    db = Database()
    yandex_api = YandexParkAPI(YANDEX_PARK_ID, YANDEX_API_KEY, YANDEX_CLIENT_ID)
    
    print("=" * 80)
    print("ТЕСТ ПОЛУЧЕНИЯ ЗАКАЗОВ ИЗ API")
    print("=" * 80)
    
    # Получаем всех пользователей в парке
    conn = db.get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
    SELECT user_id, phone_number, yandex_driver_id, yandex_driver_name
    FROM users 
    WHERE is_registered_in_park = 1 AND yandex_driver_id IS NOT NULL
    """)
    
    users = cursor.fetchall()
    conn.close()
    
    if not users:
        print("❌ В БД нет пользователей, зарегистрированных в парке")
        return
    
    print(f"\n✓ Найдено {len(users)} пользователей в парке\n")
    
    for idx, (user_id, phone, driver_id, driver_name) in enumerate(users, 1):
        print(f"\n{'='*80}")
        print(f"ТЕСТ {idx}/{len(users)}")
        print(f"{'='*80}")
        print(f"User ID: {user_id}")
        print(f"Телефон: {phone}")
        print(f"Driver ID: {driver_id}")
        print(f"ФИО: {driver_name}")
        print("-" * 80)
        
        try:
            # Получаем заказы
            print(f"📡 Запрашиваем заказы для driver_id={driver_id}...")
            orders_count = await yandex_api.get_driver_orders_count(driver_id)
            
            if orders_count is not None:
                print(f"✅ УСПЕХ! Получено заказов: {orders_count}")
                
                # Обновляем в БД
                db.update_orders_count(user_id, orders_count)
                print(f"✓ Обновлено в БД")
            else:
                print(f"❌ ОШИБКА! API вернул None")
                print(f"   Проверь логи выше для деталей")
        
        except Exception as e:
            print(f"❌ ИСКЛЮЧЕНИЕ: {e}")
            logging.exception(e)
        
        # Задержка между запросами
        if idx < len(users):
            await asyncio.sleep(2)
    
    print(f"\n{'='*80}")
    print("ТЕСТ ЗАВЕРШЕН")
    print("=" * 80)
    
    # Показываем итоговую таблицу
    print("\nИТОГОВАЯ ТАБЛИЦА:")
    print("-" * 80)
    
    conn = db.get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
    SELECT u.user_id, u.phone_number, u.yandex_driver_name, 
           COALESCE(r.orders_count, 0) as orders_count
    FROM users u
    LEFT JOIN referrals r ON u.user_id = r.referred_id
    WHERE u.is_registered_in_park = 1 AND u.yandex_driver_id IS NOT NULL
    """)
    
    results = cursor.fetchall()
    conn.close()
    
    if results:
        for user_id, phone, name, orders in results:
            print(f"  {name or 'Без имени':30} | {phone:15} | Заказов: {orders}")
    
    print("-" * 80)

if __name__ == "__main__":
    asyncio.run(test_orders())

