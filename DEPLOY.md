# Инструкция по деплою на VPS

## Быстрый старт

1. **Подключитесь к VPS:**
```bash
ssh root@your-vps-ip
```

2. **Клонируйте репозиторий:**
```bash
git clone https://github.com/YOUR_USERNAME/telegram-bot-kworkAlexzandr83.git
cd telegram-bot-kworkAlexzandr83
```

3. **Создайте файл .env:**
```bash
nano .env
```

Добавьте:
```
BOT_TOKEN=your_bot_token_here
NOTIFICATION_CHANNEL_ID=your_channel_id_here
```

4. **Запустите скрипт деплоя:**
```bash
chmod +x deploy.sh
./deploy.sh
```

5. **Проверьте статус:**
```bash
systemctl status tg-bot-registration.service
```

## Ручная установка

Если скрипт не работает, выполните команды вручную:

```bash
# Обновление системы
apt update && apt upgrade -y

# Установка Python
apt install python3 python3-pip -y

# Установка зависимостей
pip3 install -r requirements.txt

# Настройка systemd
cp systemd.service /etc/systemd/system/tg-bot-registration.service
systemctl daemon-reload
systemctl enable tg-bot-registration.service
systemctl start tg-bot-registration.service

# Проверка логов
journalctl -u tg-bot-registration.service -f
```

## Полезные команды

- **Посмотреть логи:** `journalctl -u tg-bot-registration.service -f`
- **Перезапустить бота:** `systemctl restart tg-bot-registration.service`
- **Остановить бота:** `systemctl stop tg-bot-registration.service`
- **Включить автозапуск:** `systemctl enable tg-bot-registration.service`

## Обновление бота

```bash
cd /root/tgbotkworkAlexzandr83
git pull origin main
systemctl restart tg-bot-registration.service
```

