#!/bin/bash
# Скрипт для быстрого обновления бота на VPS
# Использование: bash update_vps.sh

set -e  # Остановка при ошибке

echo "═══════════════════════════════════════════════════════════════"
echo "  ОБНОВЛЕНИЕ БОТА НА VPS"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Переменные (измени под свой проект)
PROJECT_DIR="/path/to/tgbotkworkAlexzandr83"  # ИЗМЕНИ НА СВОЙ ПУТЬ!
REPO_URL="https://github.com/SiteCraftorCPP/telegram-bot-kworkAlexzandr83.git"

# Проверка директории
if [ ! -d "$PROJECT_DIR" ]; then
    echo "❌ Директория $PROJECT_DIR не найдена!"
    echo "   Создай директорию или измени PROJECT_DIR в скрипте"
    exit 1
fi

cd "$PROJECT_DIR"

echo "📁 Рабочая директория: $PROJECT_DIR"
echo ""

# 1. Остановка процессов
echo "🛑 Останавливаем процессы..."
pkill -f "bot.py" || echo "   (bot.py не запущен)"
pkill -f "order_checker.py" || echo "   (order_checker.py не запущен)"
sleep 2
echo "✅ Процессы остановлены"
echo ""

# 2. Обновление кода из GitHub
echo "📥 Обновляем код из GitHub..."
if [ -d ".git" ]; then
    git pull origin main
else
    echo "   Репозиторий не найден, клонируем..."
    cd ..
    git clone "$REPO_URL" "$(basename $PROJECT_DIR)"
    cd "$PROJECT_DIR"
fi
echo "✅ Код обновлен"
echo ""

# 3. Установка зависимостей (если нужно)
if [ -f "requirements.txt" ]; then
    echo "📦 Проверяем зависимости..."
    pip3 install -q -r requirements.txt
    echo "✅ Зависимости установлены"
    echo ""
fi

# 4. Тестовый запуск API (опционально)
read -p "🧪 Запустить тест API? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "   Запускаем тест..."
    python3 test_orders_api.py
    echo ""
fi

# 5. Запуск бота
echo "🚀 Запускаем бота..."
nohup python3 bot.py > bot.log 2>&1 &
BOT_PID=$!
echo "   PID бота: $BOT_PID"
sleep 2

# Проверка что бот запустился
if ps -p $BOT_PID > /dev/null; then
    echo "✅ Бот запущен (PID: $BOT_PID)"
else
    echo "❌ Ошибка запуска бота! Смотри bot.log"
    exit 1
fi
echo ""

# 6. Запуск order_checker
echo "🔄 Запускаем order_checker..."
nohup python3 order_checker.py > order_checker_new.log 2>&1 &
CHECKER_PID=$!
echo "   PID order_checker: $CHECKER_PID"
sleep 2

# Проверка что order_checker запустился
if ps -p $CHECKER_PID > /dev/null; then
    echo "✅ Order checker запущен (PID: $CHECKER_PID)"
else
    echo "❌ Ошибка запуска order_checker! Смотри order_checker_new.log"
    exit 1
fi
echo ""

# 7. Показываем логи
echo "═══════════════════════════════════════════════════════════════"
echo "  ОБНОВЛЕНИЕ ЗАВЕРШЕНО"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "📊 Просмотр логов:"
echo "   tail -f $PROJECT_DIR/order_checker_new.log"
echo "   tail -f $PROJECT_DIR/bot.log"
echo ""
echo "🔍 Проверка процессов:"
echo "   ps aux | grep -E 'bot.py|order_checker.py'"
echo ""
echo "🛑 Остановка процессов:"
echo "   pkill -f bot.py"
echo "   pkill -f order_checker.py"
echo ""


