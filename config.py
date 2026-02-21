import os

# Токен бота из переменных окружения
BOT_TOKEN = os.getenv('BOT_TOKEN')

if not BOT_TOKEN:
    raise ValueError("Не задан BOT_TOKEN в переменных окружения!")

# Настройки бота
MAX_PHOTOS_PER_ENTRY = 5

# Создаем необходимые директории
os.makedirs('photos', exist_ok=True)
os.makedirs('exports', exist_ok=True)

# Настройки логирования
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Режим отладки
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

# Webhook настройки (для BotHost)
USE_WEBHOOK = os.getenv('USE_WEBHOOK', 'False').lower() == 'true'
WEBHOOK_URL = os.getenv('WEBHOOK_URL', '')
WEBHOOK_PORT = int(os.getenv('PORT', 8443))
