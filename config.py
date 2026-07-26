"""
Конфигурация приложения для анализа лог-файлов
"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

# MongoDB
MONGO_HOST = os.getenv('MONGO_HOST', 'localhost')
MONGO_PORT = int(os.getenv('MONGO_PORT', 27017))
MONGO_DB_NAME = os.getenv('MONGO_DB_NAME', 'log_analysis_dashboard')
MONGO_CONNECTION_STRING = f"mongodb://{MONGO_HOST}:{MONGO_PORT}/"

# Приложение
APP_TITLE = "Анализатор лог-файлов"
APP_HOST = os.getenv('APP_HOST', '127.0.0.1')
APP_PORT = int(os.getenv('APP_PORT', 8050))
DEBUG_MODE = os.getenv('DEBUG', 'False').lower() == 'true'

# Обработка файлов
MAX_FILE_SIZE_MB = 100
BATCH_SIZE = 500
PREVIEW_LINES = 100
SUPPORTED_FORMATS = ['.log', '.txt', '.json', '.csv', '.xlsx']

# Визуализация и таблицы
CHART_HEIGHT = 400
CHART_HEIGHT_ALL_PAGE = 320
DEFAULT_TABLE_PAGE_SIZE = 10
DEFAULT_LOAD_LIMIT = 1000
MAX_TABLE_ROWS = 57000

# Экспорт
EXPORT_DIR = 'exports'
PDF_TEMPLATE = 'default_report_template'

# Безопасность
SECRET_KEY = os.getenv('APP_SECRET_KEY', 'change-this-secret-key-in-production')
ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', '')

# SMTP (подтверждение e-mail при регистрации)
SMTP_SERVER = os.getenv('SMTP_SERVER', '')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
SMTP_USE_TLS = os.getenv('SMTP_USE_TLS', 'true').lower() == 'true'
SMTP_USERNAME = os.getenv('SMTP_USERNAME', '')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
SMTP_FROM_EMAIL = os.getenv('SMTP_FROM_EMAIL', SMTP_USERNAME or 'no-reply@example.com')

# Публичный URL для ссылок в письмах (без завершающего «/»).
# Пример в локальной сети: http://192.168.1.10:8050
PUBLIC_APP_URL = os.getenv('PUBLIC_APP_URL', '').strip().rstrip('/')

