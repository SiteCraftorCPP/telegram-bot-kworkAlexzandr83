#!/bin/bash

# Скрипт для деплоя на VPS

echo "🚀 Начало деплоя..."

# Обновление системы
echo "📦 Обновление системы..."
apt update && apt upgrade -y

# Установка Python и pip
echo "🐍 Установка Python..."
apt install python3 python3-pip -y

# Установка зависимостей
echo "📚 Установка зависимостей..."
cd /root/tgbotkworkAlexzandr83
pip3 install -r requirements.txt

# Копирование .env файла (если его нет)
if [ ! -f .env ]; then
    echo "⚠️  Не найден .env файл. Создайте его вручную!"
    exit 1
fi

# Настройка systemd
echo "⚙️  Настройка systemd..."
cp systemd.service /etc/systemd/system/tg-bot-registration.service
systemctl daemon-reload
systemctl enable tg-bot-registration.service
systemctl restart tg-bot-registration.service

# Проверка статуса
echo "✅ Проверка статуса..."
systemctl status tg-bot-registration.service

echo "🎉 Деплой завершён!"

