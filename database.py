import sqlite3
from datetime import datetime
from typing import Optional, List, Dict
import logging

class Database:
    def __init__(self, db_file: str = "bot.db"):
        self.db_file = db_file
        self.init_db()
    
    def get_connection(self):
        return sqlite3.connect(self.db_file)
    
    def init_db(self):
        """Инициализация базы данных"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Таблица пользователей
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            first_name TEXT,
            phone_number TEXT,
            category TEXT,
            referrer_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_admin INTEGER DEFAULT 0,
            is_registered_in_park INTEGER DEFAULT 0,
            yandex_driver_id TEXT,
            yandex_driver_name TEXT,
            park_position TEXT
        )
        """)
        
        # Добавляем колонку park_position, если её нет
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN park_position TEXT")
        except sqlite3.OperationalError:
            pass  # Колонка уже существует
        
        # Таблица рефералов
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER,
            referred_id INTEGER,
            orders_count INTEGER DEFAULT 0,
            bonus_paid INTEGER DEFAULT 0,
            park_position TEXT,
            notification_sent INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(referrer_id, referred_id),
            FOREIGN KEY (referrer_id) REFERENCES users(user_id),
            FOREIGN KEY (referred_id) REFERENCES users(user_id)
        )
        """)
        
        # Добавляем колонки park_position и notification_sent, если их нет
        try:
            cursor.execute("ALTER TABLE referrals ADD COLUMN park_position TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE referrals ADD COLUMN notification_sent INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        
        # Таблица для отслеживания заказов
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            order_count INTEGER,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
        """)
        
        conn.commit()
        conn.close()
    
    def add_user(self, user_id: int, username: str, full_name: str, 
                 first_name: str, phone_number: str, category: str = None, 
                 referrer_id: Optional[int] = None, is_registered_in_park: bool = False,
                 yandex_driver_id: str = None, yandex_driver_name: str = None,
                 park_position: str = None):
        """Добавление нового пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
            INSERT OR IGNORE INTO users (user_id, username, full_name, first_name, phone_number, 
                                        category, referrer_id, is_registered_in_park, 
                                        yandex_driver_id, yandex_driver_name, park_position)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, username, full_name, first_name, phone_number, category, 
                  referrer_id, 1 if is_registered_in_park else 0, yandex_driver_id, yandex_driver_name, park_position))
            
            # Если есть реферер И пользователь НЕ зарегистрирован в парке, добавляем запись в таблицу рефералов
            # (пользователи, уже зарегистрированные в парке, не учитываются как рефералы)
            if referrer_id and not is_registered_in_park:
                cursor.execute("""
                INSERT OR IGNORE INTO referrals (referrer_id, referred_id, park_position)
                VALUES (?, ?, ?)
                """, (referrer_id, user_id, park_position))
                logging.info(f"Добавлен реферал: referrer_id={referrer_id}, referred_id={user_id}, park_position={park_position}")
            elif referrer_id and is_registered_in_park:
                logging.info(f"Реферал не добавлен (пользователь уже в парке): referrer_id={referrer_id}, referred_id={user_id}")
            
            conn.commit()
            return True
        except Exception as e:
            logging.error(f"Ошибка при добавлении пользователя: {e}")
            return False
        finally:
            conn.close()
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        """Получение информации о пользователе"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
        SELECT user_id, username, full_name, phone_number, category, referrer_id, 
               created_at, is_admin, is_registered_in_park, yandex_driver_id, yandex_driver_name, park_position
        FROM users WHERE user_id = ?
        """, (user_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "user_id": row[0],
                "username": row[1],
                "full_name": row[2],
                "phone_number": row[3],
                "category": row[4],
                "referrer_id": row[5],
                "created_at": row[6],
                "is_admin": row[7],
                "is_registered_in_park": row[8],
                "yandex_driver_id": row[9],
                "yandex_driver_name": row[10],
                "park_position": row[11]
            }
        return None
    
    def get_user_by_phone(self, phone_number: str) -> Optional[Dict]:
        """Получение информации о пользователе по номеру телефона"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
        SELECT user_id, username, full_name, phone_number, category, referrer_id, 
               created_at, is_admin, is_registered_in_park, yandex_driver_id, yandex_driver_name, park_position
        FROM users WHERE phone_number = ?
        """, (phone_number,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "user_id": row[0],
                "username": row[1],
                "full_name": row[2],
                "phone_number": row[3],
                "category": row[4],
                "referrer_id": row[5],
                "created_at": row[6],
                "is_admin": row[7],
                "is_registered_in_park": row[8],
                "yandex_driver_id": row[9],
                "yandex_driver_name": row[10],
                "park_position": row[11]
            }
        return None
    
    def get_user_by_driver_id(self, yandex_driver_id: str) -> Optional[Dict]:
        """Получение информации о пользователе по yandex_driver_id"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
        SELECT user_id FROM users WHERE yandex_driver_id = ?
        """, (yandex_driver_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {"user_id": row[0]}
        return None
    
    def get_referrals_for_order_check(self) -> List[Dict]:
        """Получение списка рефералов, зарегистрированных в парке, для проверки заказов"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Получаем всех пользователей, зарегистрированных в парке, которые есть в referrals
        cursor.execute("""
        SELECT r.referrer_id, r.referred_id, u.yandex_driver_id, 
               COALESCE(r.park_position, u.park_position) as park_position, 
               r.orders_count, r.notification_sent
        FROM referrals r
        JOIN users u ON r.referred_id = u.user_id
        WHERE u.is_registered_in_park = 1 AND u.yandex_driver_id IS NOT NULL AND u.yandex_driver_id != ''
        """)
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                "referrer_id": row[0],
                "referred_id": row[1],
                "yandex_driver_id": row[2],
                "park_position": row[3],
                "orders_count": row[4] or 0,
                "notification_sent": row[5] or 0
            }
            for row in rows
        ]
    
    def get_all_park_users_for_order_check(self) -> List[Dict]:
        """Получение всех пользователей, зарегистрированных в парке, для проверки заказов (не только рефералов)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Получаем всех пользователей, зарегистрированных в парке
        cursor.execute("""
        SELECT u.user_id, u.yandex_driver_id, u.park_position
        FROM users u
        WHERE u.is_registered_in_park = 1 AND u.yandex_driver_id IS NOT NULL AND u.yandex_driver_id != ''
        """)
        
        rows = cursor.fetchall()
        conn.close()
        
        result = []
        for row in rows:
            user_id = row[0]
            yandex_driver_id = row[1]
            park_position = row[2]
            
            # Получаем referrer_id из referrals, если есть
            referrer_id = None
            conn2 = self.get_connection()
            cursor2 = conn2.cursor()
            cursor2.execute("SELECT referrer_id FROM referrals WHERE referred_id = ? LIMIT 1", (user_id,))
            ref_row = cursor2.fetchone()
            if ref_row:
                referrer_id = ref_row[0]
            conn2.close()
            
            result.append({
                "referrer_id": referrer_id,
                "referred_id": user_id,
                "yandex_driver_id": yandex_driver_id,
                "park_position": park_position,
                "orders_count": 0,
                "notification_sent": 0
            })
        
        return result
    
    def get_referrals(self, referrer_id: int) -> List[Dict]:
        """Получение списка приглашённых пользователей"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
        SELECT u.user_id, u.full_name, u.username, u.category, r.orders_count, r.bonus_paid, r.created_at
        FROM referrals r
        JOIN users u ON r.referred_id = u.user_id
        WHERE r.referrer_id = ?
        ORDER BY r.created_at DESC
        """, (referrer_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                "user_id": row[0],
                "full_name": row[1],
                "username": row[2],
                "category": row[3],
                "orders_count": row[4],
                "bonus_paid": row[5],
                "created_at": row[6]
            }
            for row in rows
        ]
    
    def update_orders_count(self, user_id: int, orders_count: int) -> bool:
        """Обновление количества заказов для пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Сначала пытаемся обновить существующую запись
            cursor.execute("""
            UPDATE referrals
            SET orders_count = ?
            WHERE referred_id = ?
            """, (orders_count, user_id))
            
            rows_affected = cursor.rowcount
            
            # Если запись не найдена, пытаемся найти referrer_id и создать запись
            if rows_affected == 0:
                # Ищем referrer_id для этого пользователя
                cursor.execute("""
                SELECT referrer_id FROM users WHERE user_id = ?
                """, (user_id,))
                user_row = cursor.fetchone()
                
                if user_row and user_row[0]:
                    referrer_id = user_row[0]
                    # Получаем park_position если есть
                    cursor.execute("""
                    SELECT park_position FROM users WHERE user_id = ?
                    """, (user_id,))
                    park_pos_row = cursor.fetchone()
                    park_position = park_pos_row[0] if park_pos_row else None
                    
                    # Создаем запись в referrals
                    cursor.execute("""
                    INSERT OR REPLACE INTO referrals (referrer_id, referred_id, orders_count, park_position)
                    VALUES (?, ?, ?, ?)
                    """, (referrer_id, user_id, orders_count, park_position))
                    rows_affected = cursor.rowcount
                    logging.info(f"Created referral record for user {user_id} with orders_count {orders_count}")
                else:
                    logging.warning(f"No referrer_id found for user {user_id}, cannot create referral record")
            
            conn.commit()
            
            if rows_affected > 0:
                logging.info(f"Updated orders for user {user_id} to {orders_count} (rows affected: {rows_affected})")
            
            return True
        except Exception as e:
            logging.error(f"Ошибка при обновлении заказов для user_id {user_id}: {e}", exc_info=True)
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def get_user_orders_count(self, user_id: int) -> int:
        """Получение количества заказов пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
            SELECT orders_count FROM referrals WHERE referred_id = ?
            """, (user_id,))
            row = cursor.fetchone()
            return int(row[0]) if row and row[0] is not None else 0
        except Exception as e:
            logging.error(f"Ошибка при получении количества заказов для user_id {user_id}: {e}")
            return 0
        finally:
            conn.close()
    
    def update_user_park_position(self, user_id: int, park_position: str) -> bool:
        """Обновление позиции пользователя в парке"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
            UPDATE users
            SET park_position = ?
            WHERE user_id = ?
            """, (park_position, user_id))
            
            # Также обновляем в referrals, если есть запись
            cursor.execute("""
            UPDATE referrals
            SET park_position = ?
            WHERE referred_id = ?
            """, (park_position, user_id))
            
            conn.commit()
            logging.info(f"Updated park_position for user {user_id} to {park_position}")
            return True
        except Exception as e:
            logging.error(f"Ошибка при обновлении позиции: {e}")
            return False
        finally:
            conn.close()
    
    def mark_notification_sent(self, referrer_id: int, referred_id: int) -> bool:
        """Отметить, что уведомление о достижении цели отправлено"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
            UPDATE referrals
            SET notification_sent = 1
            WHERE referrer_id = ? AND referred_id = ?
            """, (referrer_id, referred_id))
            
            conn.commit()
            return True
        except Exception as e:
            logging.error(f"Ошибка при отметке уведомления: {e}")
            return False
        finally:
            conn.close()
    
    def mark_bonus_paid(self, referrer_id: int, referred_id: int) -> bool:
        """Отметить, что бонус выплачен"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
            UPDATE referrals
            SET bonus_paid = 1
            WHERE referrer_id = ? AND referred_id = ?
            """, (referrer_id, referred_id))
            
            conn.commit()
            return True
        except Exception as e:
            logging.error(f"Ошибка при отметке бонуса: {e}")
            return False
        finally:
            conn.close()
    
    def set_admin(self, user_id: int, is_admin: bool = True) -> bool:
        """Установить/снять статус администратора"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
            UPDATE users
            SET is_admin = ?
            WHERE user_id = ?
            """, (1 if is_admin else 0, user_id))
            
            conn.commit()
            return True
        except Exception as e:
            logging.error(f"Ошибка при установке статуса админа: {e}")
            return False
        finally:
            conn.close()
    
    def is_admin(self, user_id: int) -> bool:
        """Проверка, является ли пользователь администратором"""
        # Проверяем список постоянных админов из config
        from config import ADMIN_USER_IDS
        if user_id in ADMIN_USER_IDS:
            return True
        
        # Проверяем статус в БД
        user = self.get_user(user_id)
        return user and user.get("is_admin") == 1
    
    def get_all_users(self) -> List[Dict]:
        """Получение списка всех пользователей"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
        SELECT user_id, username, full_name, category, referrer_id, created_at, phone_number, is_registered_in_park
        FROM users
        ORDER BY created_at DESC
        """)
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                "user_id": row[0],
                "username": row[1],
                "full_name": row[2],
                "category": row[3],
                "referrer_id": row[4],
                "created_at": row[5],
                "phone_number": row[6],
                "is_registered_in_park": row[7]
            }
            for row in rows
        ]
    
    def get_user_stats(self, user_id: int) -> Dict:
        """Получение статистики пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Количество приглашённых
        cursor.execute("""
        SELECT COUNT(*) FROM referrals WHERE referrer_id = ?
        """, (user_id,))
        invited_count = cursor.fetchone()[0]
        
        # Количество выполненных условий (45+ заказов)
        cursor.execute("""
        SELECT COUNT(*) FROM referrals 
        WHERE referrer_id = ? AND orders_count >= 45
        """, (user_id,))
        completed_count = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "invited_count": invited_count,
            "completed_count": completed_count
        }

    def get_referral_stats(self) -> List[Dict]:
        """Получение статистики по всем рефералам"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
        SELECT 
            referrer.user_id as referrer_user_id,
            referrer.full_name as referrer_full_name,
            referrer.username as referrer_username,
            referred.user_id as referred_user_id,
            referred.full_name as referred_full_name,
            referred.username as referred_username,
            COALESCE(r.orders_count, 0) as orders_count
        FROM referrals r
        JOIN users referrer ON r.referrer_id = referrer.user_id
        JOIN users referred ON r.referred_id = referred.user_id
        ORDER BY referrer.created_at DESC, r.created_at DESC
        """)
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                "referrer_user_id": row[0],
                "referrer_full_name": row[1],
                "referrer_username": row[2],
                "referred_user_id": row[3],
                "referred_full_name": row[4],
                "referred_username": row[5],
                "orders_count": int(row[6]) if row[6] is not None else 0,
            }
            for row in rows
        ]

    def get_invited_users_with_order_count(self, referrer_id: int) -> List[Dict]:
        """Получение списка приглашенных пользователем с количеством их заказов"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            logging.info(f"Executing query for referrer_id: {referrer_id}")
            cursor.execute("""
            SELECT 
                u.full_name,
                u.username,
                u.phone_number,
                COALESCE(r.orders_count, 0) as orders_count
            FROM referrals r
            JOIN users u ON r.referred_id = u.user_id
            WHERE r.referrer_id = ?
            ORDER BY r.created_at DESC
            """, (referrer_id,))
            
            rows = cursor.fetchall()
            logging.info(f"Query returned {len(rows)} rows for referrer_id: {referrer_id}")
            
            result = [
                {
                    "full_name": row[0] if row[0] else "Не указано",
                    "username": row[1] if row[1] else None,
                    "phone_number": row[2] if row[2] else None,
                    "orders_count": int(row[3]) if row[3] is not None else 0,
                }
                for row in rows
            ]
            
            logging.info(f"Returning result: {result}")
            return result
        except Exception as e:
            logging.error(f"Error in get_invited_users_with_order_count: {e}", exc_info=True)
            return []
        finally:
            conn.close()

