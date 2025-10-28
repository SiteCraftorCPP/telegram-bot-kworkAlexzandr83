#!/bin/bash

# Скрипт для деплоя на VPS

echo "🚀 Начало деплоя..."

# Обновление системы
echo "📦 Обновление системы..."
apt update

# Установка Python и pip
echo "🐍 Установка Python..."
apt install python3 python3-pip git -y

# Клонирование репозитория (если ещё не клонирован)
if [ ! -d "tgbotkworkAlexzandr83" ]; then
    echo "📥 Клонирование репозитория..."
    git clone https://github.com/YOUR_USERNAME/telegram-bot-kworkAlexzandr83.git tgbotkworkAlexzandr83
fi

cd tgbotkworkAlexzandr83

# Установка зависимостей
echo "📚 Установка зависимостей..."
pip3 install -r requirements.txt

# Копирование .env файла (если его нет)
if [ ! -f .env ]; then
    echo "⚠️  Не найден .env файл. Создайте его вручную!"
    cp env_example.txt .env
    echo "📝 Создан .env файл из примера. Отредактируйте его!"
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
sleep 2
systemctl status tg-bot-registration.service --no-pager

echo "🎉 Деплой завершён!"

