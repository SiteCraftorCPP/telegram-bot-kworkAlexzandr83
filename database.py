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
            category TEXT,
            referrer_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_admin INTEGER DEFAULT 0
        )
        """)
        
        # Таблица рефералов
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER,
            referred_id INTEGER,
            orders_count INTEGER DEFAULT 0,
            bonus_paid INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(referrer_id, referred_id),
            FOREIGN KEY (referrer_id) REFERENCES users(user_id),
            FOREIGN KEY (referred_id) REFERENCES users(user_id)
        )
        """)
        
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
                 first_name: str, category: str, referrer_id: Optional[int] = None):
        """Добавление нового пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
            INSERT OR IGNORE INTO users (user_id, username, full_name, first_name, category, referrer_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, username, full_name, first_name, category, referrer_id))
            
            # Если есть реферер, добавляем запись в таблицу рефералов (без дубликатов)
            if referrer_id:
                cursor.execute("""
                INSERT OR IGNORE INTO referrals (referrer_id, referred_id)
                VALUES (?, ?)
                """, (referrer_id, user_id))
            
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
        SELECT user_id, username, full_name, category, referrer_id, created_at, is_admin
        FROM users WHERE user_id = ?
        """, (user_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "user_id": row[0],
                "username": row[1],
                "full_name": row[2],
                "category": row[3],
                "referrer_id": row[4],
                "created_at": row[5],
                "is_admin": row[6]
            }
        return None
    
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
            # Обновляем в referrals
            cursor.execute("""
            UPDATE referrals
            SET orders_count = ?
            WHERE referred_id = ?
            """, (orders_count, user_id))
            
            conn.commit()
            return True
        except Exception as e:
            logging.error(f"Ошибка при обновлении заказов: {e}")
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
        user = self.get_user(user_id)
        return user and user.get("is_admin") == 1
    
    def get_all_users(self) -> List[Dict]:
        """Получение списка всех пользователей"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
        SELECT user_id, username, full_name, category, referrer_id, created_at
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
                "created_at": row[5]
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

