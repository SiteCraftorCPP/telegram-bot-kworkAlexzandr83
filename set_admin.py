#!/usr/bin/env python3
"""
Скрипт для установки/снятия статуса администратора
Использование:
  python set_admin.py add USER_ID     # Добавить администратора
  python set_admin.py remove USER_ID  # Убрать администратора
  python set_admin.py list            # Показать всех администраторов
"""

import sys
from database import Database

def main():
    db = Database()
    
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python set_admin.py add USER_ID     # Добавить администратора")
        print("  python set_admin.py remove USER_ID  # Убрать администратора")
        print("  python set_admin.py list            # Показать всех администраторов")
        return
    
    command = sys.argv[1].lower()
    
    if command == "list":
        users = db.get_all_users()
        admins = [u for u in users if db.is_admin(u['user_id'])]
        
        if not admins:
            print("Нет администраторов")
        else:
            print(f"Администраторы ({len(admins)}):")
            for admin in admins:
                print(f"  - {admin['full_name']} (@{admin['username']}, ID: {admin['user_id']})")
        return
    
    if len(sys.argv) < 3:
        print("Ошибка: укажите USER_ID")
        return
    
    try:
        user_id = int(sys.argv[2])
    except ValueError:
        print("Ошибка: USER_ID должен быть числом")
        return
    
    if command == "add":
        if db.set_admin(user_id, True):
            user = db.get_user(user_id)
            if user:
                print(f"✅ Пользователь {user['full_name']} (ID: {user_id}) теперь администратор")
            else:
                print(f"✅ Пользователь ID: {user_id} добавлен как администратор")
                print("   (пользователь ещё не зарегистрировался в боте)")
        else:
            print(f"❌ Ошибка при добавлении администратора")
    
    elif command == "remove":
        if db.set_admin(user_id, False):
            user = db.get_user(user_id)
            if user:
                print(f"✅ У пользователя {user['full_name']} (ID: {user_id}) убран статус администратора")
            else:
                print(f"✅ У пользователя ID: {user_id} убран статус администратора")
        else:
            print(f"❌ Ошибка при удалении администратора")
    
    else:
        print(f"Неизвестная команда: {command}")
        print("Доступные команды: add, remove, list")

if __name__ == "__main__":
    main()

