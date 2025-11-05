#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для установки/снятия статуса администратора
Использование:
  python set_admin.py add USER_ID     # Добавить администратора
  python set_admin.py remove USER_ID  # Убрать администратора
  python set_admin.py list            # Показать всех администраторов
"""

import sys
import os
from database import Database

# Установка UTF-8 для Windows
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')

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
            print("No admins found")
        else:
            print(f"Admins ({len(admins)}):")
            for admin in admins:
                username = admin['username'] if admin['username'] else 'no username'
                print(f"  - ID: {admin['user_id']}, @{username}")
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
                print(f"[OK] User ID: {user_id} is now admin")
            else:
                print(f"[OK] User ID: {user_id} added as admin")
                print("   (user hasn't registered in bot yet)")
        else:
            print(f"[ERROR] Failed to add admin")
    
    elif command == "remove":
        if db.set_admin(user_id, False):
            print(f"[OK] User ID: {user_id} admin status removed")
        else:
            print(f"[ERROR] Failed to remove admin")
    
    else:
        print(f"Неизвестная команда: {command}")
        print("Доступные команды: add, remove, list")

if __name__ == "__main__":
    main()

