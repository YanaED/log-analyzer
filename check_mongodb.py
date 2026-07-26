"""
Скрипт для проверки подключения к MongoDB
"""
from pymongo import MongoClient
import sys
import config

def check_mongodb():
    """Проверка подключения к MongoDB"""
    print("=" * 50)
    print("Проверка подключения к MongoDB")
    print("=" * 50)
    
    try:
        print(f"Подключение к {config.MONGO_CONNECTION_STRING}...")
        client = MongoClient(
            config.MONGO_CONNECTION_STRING,
            serverSelectionTimeoutMS=5000
        )
        
        # Проверка подключения
        client.admin.command('ping')
        print("MongoDB подключена и работает!")
        
        # Информация о сервере
        server_info = client.server_info()
        print(f"Версия MongoDB: {server_info.get('version', 'unknown')}")
        
        # Проверка базы данных
        db = client[config.MONGO_DB_NAME]
        collections = db.list_collection_names()
        print(f"База данных: {config.MONGO_DB_NAME}")
        print(f"Коллекций в базе: {len(collections)}")
        
        if collections:
            print("   Коллекции:")
            for col in collections[:10]:  # Показываем первые 10
                count = db[col].count_documents({})
                print(f"   - {col}: {count} документов")
        
        client.close()
        print("\n Все проверки пройдены! Можно запускать приложение.")
        return True
        
    except Exception as e:
        print(f"\n Ошибка подключения к MongoDB: {e}")
        print("\n Решение проблемы:")
        print("1. Убедитесь, что MongoDB установлена и запущена")
        print("2. Проверьте, что MongoDB работает на порту 27017")
        print("3. Для Windows: net start MongoDB")
        print("4. Для Linux/Mac: sudo systemctl start mongod")
        print("5. Или запустите MongoDB вручную")
        return False

if __name__ == "__main__":
    success = check_mongodb()
    sys.exit(0 if success else 1)

