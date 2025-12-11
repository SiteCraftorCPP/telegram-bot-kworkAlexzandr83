# Команды для быстрого обновления на VPS

## 🚀 Быстрое обновление (1 команда)

```bash
cd /path/to/tgbotkworkAlexzandr83 && git pull origin main && pkill -f bot.py && pkill -f order_checker.py && nohup python3 bot.py > bot.log 2>&1 & nohup python3 order_checker.py > order_checker_new.log 2>&1 &
```

---

## 📋 Пошаговое обновление

### 1. Подключись к VPS
```bash
ssh user@your-vps-ip
```

### 2. Перейди в директорию проекта
```bash
cd /path/to/tgbotkworkAlexzandr83
# Или если клонируешь впервые:
# git clone https://github.com/SiteCraftorCPP/telegram-bot-kworkAlexzandr83.git
# cd telegram-bot-kworkAlexzandr83
```

### 3. Останови старые процессы
```bash
pkill -f bot.py
pkill -f order_checker.py
```

### 4. Обнови код из GitHub
```bash
git pull origin main
```

### 5. Установи зависимости (если нужно)
```bash
pip3 install -r requirements.txt
```

### 6. (Опционально) Тест API перед запуском
```bash
python3 test_orders_api.py
```

### 7. Запусти бота
```bash
nohup python3 bot.py > bot.log 2>&1 &
```

### 8. Запусти order_checker
```bash
nohup python3 order_checker.py > order_checker_new.log 2>&1 &
```

### 9. Проверь что всё работает
```bash
# Проверка процессов
ps aux | grep -E 'bot.py|order_checker.py'

# Просмотр логов
tail -f order_checker_new.log
```

---

## 🔧 Использование скрипта update_vps.sh

### Подготовка:
1. Загрузи `update_vps.sh` на VPS
2. Отредактируй переменную `PROJECT_DIR` в скрипте (укажи свой путь)
3. Сделай скрипт исполняемым:
```bash
chmod +x update_vps.sh
```

### Запуск:
```bash
bash update_vps.sh
```

Скрипт автоматически:
- ✅ Остановит старые процессы
- ✅ Обновит код из GitHub
- ✅ Установит зависимости
- ✅ Запустит бота и order_checker
- ✅ Покажет статус

---

## 📊 Полезные команды

### Просмотр логов в реальном времени:
```bash
# Лог order_checker
tail -f order_checker_new.log

# Лог бота
tail -f bot.log

# Оба лога одновременно
tail -f bot.log order_checker_new.log
```

### Проверка процессов:
```bash
ps aux | grep -E 'bot.py|order_checker.py'
```

### Остановка всех процессов:
```bash
pkill -f bot.py
pkill -f order_checker.py
```

### Перезапуск (если что-то сломалось):
```bash
pkill -f bot.py && pkill -f order_checker.py && sleep 2 && nohup python3 bot.py > bot.log 2>&1 & nohup python3 order_checker.py > order_checker_new.log 2>&1 &
```

### Проверка последних изменений:
```bash
git log --oneline -5
```

---

## ⚠️ Если что-то пошло не так

### Бот не запускается:
```bash
# Смотри логи
cat bot.log

# Проверь зависимости
pip3 install -r requirements.txt

# Проверь конфиг
cat config.py
```

### Order_checker не работает:
```bash
# Смотри логи
cat order_checker_new.log

# Запусти тест API
python3 test_orders_api.py
```

### Проблемы с git:
```bash
# Если конфликты
git stash
git pull origin main
git stash pop

# Если нужно сбросить изменения
git reset --hard origin/main
```

---

## 🔄 Автоматическое обновление через cron

Добавь в crontab для автоматического обновления каждый час:

```bash
crontab -e
```

Добавь строку:
```
0 * * * * cd /path/to/tgbotkworkAlexzandr83 && git pull origin main > /dev/null 2>&1
```

---

## 📝 Чек-лист после обновления

- [ ] Код обновлен (`git pull` выполнен)
- [ ] Старые процессы остановлены
- [ ] Бот запущен (`ps aux | grep bot.py`)
- [ ] Order_checker запущен (`ps aux | grep order_checker.py`)
- [ ] Логи показывают нормальную работу (`tail -f order_checker_new.log`)
- [ ] Тест через админ-панель бота (поиск по номеру показывает заказы)

---

**Репозиторий:** https://github.com/SiteCraftorCPP/telegram-bot-kworkAlexzandr83  
**Последнее обновление:** 2024-11-20


