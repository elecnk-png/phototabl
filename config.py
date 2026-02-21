import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Токен бота (обязательно из переменных окружения)
BOT_TOKEN = os.getenv('BOT_TOKEN')

# Настройки бота
MAX_PHOTOS_PER_ENTRY = 5
PHOTOS_DIR = 'photos'
EXPORTS_DIR = 'exports'

# Создаем директории, если их нет
os.makedirs(PHOTOS_DIR, exist_ok=True)
os.makedirs(EXPORTS_DIR, exist_ok=True)

# Настройки логирования
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Режим отладки
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

# Webhook настройки (для BotHost)
USE_WEBHOOK = os.getenv('USE_WEBHOOK', 'False').lower() == 'true'
WEBHOOK_URL = os.getenv('WEBHOOK_URL', '')
WEBHOOK_PORT = int(os.getenv('PORT', 8443))
