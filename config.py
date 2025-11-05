import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv(encoding='utf-8-sig')

# Токен бота (получить у @BotFather)
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# ID канала для уведомлений (например: -1001234567890)
NOTIFICATION_CHANNEL_ID = os.getenv("NOTIFICATION_CHANNEL_ID", "YOUR_CHANNEL_ID_HERE")

# Данные для Яндекс Парк API
YANDEX_PARK_ID = os.getenv("YANDEX_PARK_ID", "138738dbd66d49c88675ac0020ba7ca4")
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY", "QTkYBGXCHhLlCFOqlVMErQpwJEXzXDYMg")
YANDEX_CLIENT_ID = os.getenv("YANDEX_CLIENT_ID", "taxi/park/138738dbd66d49c88675ac0020ba7ca4")

# Список администраторов (будут всегда иметь права админа)
ADMIN_USER_IDS = [
    6933111964,
    38648491,
    1040874391
]

# Если не нашли в .env, пробуем прочитать напрямую
if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
    try:
        with open('.env', 'r', encoding='utf-8-sig') as f:
            for line in f:
                if line.startswith('BOT_TOKEN='):
                    BOT_TOKEN = line.split('=', 1)[1].strip()
                elif line.startswith('NOTIFICATION_CHANNEL_ID='):
                    NOTIFICATION_CHANNEL_ID = line.split('=', 1)[1].strip()
                elif line.startswith('YANDEX_PARK_ID='):
                    YANDEX_PARK_ID = line.split('=', 1)[1].strip()
                elif line.startswith('YANDEX_API_KEY='):
                    YANDEX_API_KEY = line.split('=', 1)[1].strip()
                elif line.startswith('YANDEX_CLIENT_ID='):
                    YANDEX_CLIENT_ID = line.split('=', 1)[1].strip()
    except:
        pass

