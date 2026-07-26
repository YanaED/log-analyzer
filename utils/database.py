"""
Модуль для работы с базой данных MongoDB
Реализует трехуровневую модель хранения данных
"""
from pymongo import MongoClient
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import config


class DatabaseManager:
    """Класс для управления подключением и операциями с MongoDB
    
    Реализует трехуровневую модель хранения:
    - Уровень 1: raw_logs_unified - сырые данные
    - Уровень 2: нормализованные коллекции по форматам
    - Уровень 3: aggregated_metrics - агрегированные метрики
    """
    
    # Константы для имен коллекций
    RAW_LOGS_COLLECTION = "raw_logs_unified"
    AGGREGATED_METRICS_COLLECTION = "aggregated_metrics"
    
    def __init__(self):
        self.client = None
        self.db = None
        self._connect()
    
    def _connect(self):
        """Подключение к MongoDB"""
        try:
            self.client = MongoClient(
                config.MONGO_CONNECTION_STRING,
                serverSelectionTimeoutMS=5000
            )
            self.db = self.client[config.MONGO_DB_NAME]
            self.client.admin.command('ping')
            print("Успешное подключение к MongoDB")
            return True
        except Exception as e:
            print(f"Ошибка подключения к MongoDB: {e}")
            self.client = None
            self.db = None
            return False
    
    def is_connected(self) -> bool:
        """Проверка подключения к базе данных"""
        if self.db is None:
            return False
        try:
            self.client.admin.command('ping')
            return True
        except:
            return False
    
    def get_collections_info(self, owner_email: Optional[str] = None) -> List[Dict]:
        """Получение информации о коллекциях с логами. Одна сбойная коллекция не роняет весь список."""
        if not self.is_connected() or self.db is None:
            return []

        # При включённой авторизации показываем только данные текущего пользователя
        if not owner_email:
            return []
        
        owner_filter = {"owner_email": owner_email} if owner_email else {}

        collections_info = []
        try:
            raw_collection = self.db[self.RAW_LOGS_COLLECTION]
            raw_count = raw_collection.count_documents(owner_filter)
            collections_info.append({
                'name': self.RAW_LOGS_COLLECTION,
                'count': raw_count,
                'type': 'raw',
                'file_source': 'unified'
            })
        except Exception as e:
            print(f"Ошибка при чтении raw-коллекции: {e}")
        
        try:
            for collection_name in self.db.list_collection_names():
                if not collection_name.endswith('_normalized'):
                    continue
                try:
                    collection = self.db[collection_name]
                    count = collection.count_documents(owner_filter)
                    log_format = collection_name.replace('_normalized', '')
                    collections_info.append({
                        'name': collection_name,
                        'count': count,
                        'type': 'normalized',
                        'file_source': log_format
                    })
                except Exception as e:
                    print(f"Ошибка при чтении коллекции {collection_name}: {e}")
        except Exception as e:
            print(f"Ошибка при переборе коллекций: {e}")
        
        try:
            metrics_collection = self.db[self.AGGREGATED_METRICS_COLLECTION]
            metrics_count = metrics_collection.count_documents(owner_filter)
            collections_info.append({
                'name': self.AGGREGATED_METRICS_COLLECTION,
                'count': metrics_count,
                'type': 'aggregated',
                'file_source': 'metrics'
            })
        except Exception as e:
            print(f"Ошибка при чтении метрик: {e}")
        
        return collections_info
    
    def get_logs_from_collection(
        self,
        collection_name: str,
        limit: Optional[int] = None,
        filters: Optional[Dict] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        ip_address: Optional[str] = None,
        status_code: Optional[int] = None,
        level: Optional[str] = None,
        owner_email: Optional[str] = None,
    ) -> List[Dict]:
        """Получение логов из коллекции с опциональными фильтрами
        
        Поддерживает фильтрацию на уровне MongoDB для оптимизации производительности.
        Работает с нормализованными коллекциями.
        """
        if not self.is_connected() or collection_name not in self.db.list_collection_names():
            return []

        if not owner_email:
            return []
        
        if limit is None or limit <= 0 or limit == 100:
            # 100 — старый дефолт; всегда подставляем конфиг, чтобы загружать больше
            limit = getattr(config, 'DEFAULT_LOAD_LIMIT', 1000)
        limit = min(limit, getattr(config, 'MAX_TABLE_ROWS', 50000))
        
        try:
            collection = self.db[collection_name]
            
            # Построение MongoDB-запроса
            query = filters or {}
            if owner_email:
                query["owner_email"] = owner_email
            
            # Фильтр по дате
            if date_from or date_to:
                date_filter = {}
                if date_from:
                    date_filter['$gte'] = date_from
                if date_to:
                    date_filter['$lte'] = date_to
                query['timestamp'] = date_filter
            
            # Фильтр по IP-адресу
            if ip_address:
                query['ip_address'] = ip_address
            
            # Фильтр по статус-коду
            if status_code is not None:
                query['http_status'] = status_code
            
            # Фильтр по уровню
            if level:
                query['level'] = level
            
            logs = list(collection.find(query).limit(limit).sort('timestamp', -1))
            
            # Преобразование для JSON-сериализации
            for log in logs:
                if '_id' in log:
                    log['_id'] = str(log['_id'])
                for key, value in log.items():
                    if isinstance(value, datetime):
                        log[key] = value.strftime('%Y-%m-%d %H:%M:%S')
            
            return logs
        except Exception as e:
            print(f"Ошибка при получении логов: {e}")
            return []
    
    def get_raw_logs(self, filename: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """Получение сырых логов из коллекции raw_logs_unified"""
        if not self.is_connected():
            return []
        
        try:
            collection = self.db[self.RAW_LOGS_COLLECTION]
            query = {}
            if filename:
                query['file_source'] = filename
            
            logs = list(collection.find(query).limit(limit).sort('uploaded_at', -1))
            
            for log in logs:
                if '_id' in log:
                    log['_id'] = str(log['_id'])
                for key, value in log.items():
                    if isinstance(value, datetime):
                        log[key] = value.strftime('%Y-%m-%d %H:%M:%S')
            
            return logs
        except Exception as e:
            print(f"Ошибка при получении сырых логов: {e}")
            return []
    
    def get_aggregated_metrics(
        self,
        log_format: Optional[str] = None,
        interval_type: str = 'hour',
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict]:
        """Получение агрегированных метрик"""
        if not self.is_connected():
            return []
        
        try:
            collection = self.db[self.AGGREGATED_METRICS_COLLECTION]
            query = {'interval_type': interval_type}
            
            if log_format:
                query['log_format'] = log_format
            
            if date_from or date_to:
                date_filter = {}
                if date_from:
                    date_filter['$gte'] = date_from
                if date_to:
                    date_filter['$lte'] = date_to
                query['time_interval'] = date_filter
            
            metrics = list(collection.find(query).limit(limit).sort('time_interval', -1))
            
            for metric in metrics:
                if '_id' in metric:
                    metric['_id'] = str(metric['_id'])
                for key, value in metric.items():
                    if isinstance(value, datetime):
                        metric[key] = value.strftime('%Y-%m-%d %H:%M:%S')
            
            return metrics
        except Exception as e:
            print(f"Ошибка при получении агрегированных метрик: {e}")
            return []
    
    def _ensure_indexes(self, collection_name: str, log_format: Optional[str] = None):
        """Создание индексов для оптимизации запросов
        
        Args:
            collection_name: Имя коллекции
            log_format: Формат лога для создания специализированных индексов
        """
        if not self.is_connected():
            return
        
        try:
            collection = self.db[collection_name]
            
            # Базовые индексы для всех коллекций
            if collection_name == self.RAW_LOGS_COLLECTION:
                # Индексы для сырых данных
                collection.create_index([("uploaded_at", 1)], background=True)
                collection.create_index([("file_source", 1)], background=True)
                collection.create_index([("log_format", 1)], background=True)
                collection.create_index([("parse_status", 1)], background=True)
                collection.create_index([("owner_email", 1)], background=True, sparse=True)
            elif collection_name == self.AGGREGATED_METRICS_COLLECTION:
                # Индексы для агрегированных метрик
                collection.create_index([("time_interval", 1), ("interval_type", 1)], background=True)
                collection.create_index([("log_format", 1)], background=True)
                collection.create_index([("timestamp", -1)], background=True)
                collection.create_index([("owner_email", 1)], background=True, sparse=True)
            else:
                # Индексы для нормализованных коллекций
                collection.create_index([("timestamp", 1)], background=True, sparse=True)
                collection.create_index([("level", 1)], background=True, sparse=True)
                collection.create_index([("timestamp", 1), ("level", 1)], background=True, sparse=True)
                collection.create_index([("owner_email", 1)], background=True, sparse=True)
                
                # Специализированные индексы в зависимости от формата
                if log_format in ['apache', 'nginx']:
                    collection.create_index([("ip_address", 1)], background=True, sparse=True)
                    collection.create_index([("http_status", 1)], background=True, sparse=True)
                    collection.create_index([("url", 1)], background=True, sparse=True)
                elif log_format == 'json':
                    collection.create_index([("ip_address", 1)], background=True, sparse=True)
                    collection.create_index([("http_status", 1)], background=True, sparse=True)
            
        except Exception as e:
            print(f"Ошибка при создании индексов для {collection_name}: {e}")
    
    def save_raw_logs_batch(
        self,
        filename: str,
        log_format: str,
        lines: List[str],
        parse_status: str = "success",
        owner_email: Optional[str] = None,
    ) -> bool:
        """Сохранение сырых данных в коллекцию raw_logs_unified (Уровень 1)"""
        if not self.is_connected():
            return False
        
        try:
            collection = self.db[self.RAW_LOGS_COLLECTION]
            
            # Создаем индексы при первом сохранении
            if collection.count_documents({}) == 0:
                self._ensure_indexes(self.RAW_LOGS_COLLECTION)
            
            raw_records = []
            for line in lines:
                if line.strip():
                    raw_records.append({
                        'raw_line': line,
                        'file_source': filename,
                        'log_format': log_format,
                        'uploaded_at': datetime.now(),
                        'parse_status': parse_status,
                        'owner_email': owner_email
                    })
            
            if raw_records:
                collection.insert_many(raw_records)
            return True
        except Exception as e:
            print(f"Ошибка при сохранении сырых логов: {e}")
            return False
    
    @staticmethod
    def _sanitize_filename_for_collection(filename: str) -> str:
        """Имя файла → безопасная строка для имени коллекции (без смешивания файлов)."""
        import re
        name = str(filename).strip()
        for ext in ('.xlsx', '.xls', '.log', '.txt', '.json', '.csv'):
            if name.lower().endswith(ext):
                name = name[: -len(ext)]
                break
        name = re.sub(r'[^\w\-_]', '_', name)
        name = name.strip('_') or 'file'
        return name[:80]
    
    def get_normalized_collection_name(self, log_format: str, filename: Optional[str] = None) -> str:
        """Имя коллекции для нормализованных данных. При указании filename — отдельная коллекция на файл (данные не смешиваются)."""
        format_map = {
            'apache': 'nginx_access',
            'nginx': 'nginx_access',
            'json': 'json_app',
            'csv': 'csv_data',
            'text': 'text_logs',
            'xlsx': 'excel',
        }
        base = format_map.get(log_format, log_format)
        if filename:
            safe = self._sanitize_filename_for_collection(filename)
            return f"{base}_{safe}_normalized"
        return f"{base}_normalized"
    
    def save_normalized_logs_batch(
        self,
        log_format: str,
        records: List[Dict],
        filename: Optional[str] = None,
        owner_email: Optional[str] = None,
    ) -> bool:
        """Сохранение нормализованных данных в коллекцию (Уровень 2). При filename — своя коллекция на файл."""
        if not self.is_connected():
            return False
        
        try:
            collection_name = self.get_normalized_collection_name(log_format, filename)
            collection = self.db[collection_name]
            
            # Создаем индексы при первом сохранении
            if collection.count_documents({}) == 0:
                self._ensure_indexes(collection_name, log_format)
            
            # Очищаем записи от NULL-значений для оптимизации
            normalized_records = []
            for record in records:
                # Удаляем raw_message и message, оставляем только структурированные поля
                normalized = {k: v for k, v in record.items() 
                            if v is not None and k not in ['raw_message', 'message']}
                # Добавляем обязательные поля
                normalized['file_source'] = record.get('file_source', 'unknown')
                normalized['uploaded_at'] = record.get('uploaded_at', datetime.now())
                if owner_email:
                    normalized['owner_email'] = owner_email
                normalized_records.append(normalized)
            
            if normalized_records:
                collection.insert_many(normalized_records)
            return True
        except Exception as e:
            print(f"Ошибка при сохранении нормализованных логов: {e}")
            return False
    
    def aggregate_and_save_metrics(
        self,
        log_format: str,
        records: List[Dict],
        interval_type: str = 'hour',
        owner_email: Optional[str] = None,
    ) -> bool:
        """Агрегация и сохранение метрик (Уровень 3)
        
        Args:
            log_format: Формат логов
            records: Список нормализованных записей
            interval_type: Тип интервала ('hour' или 'day')
        """
        if not self.is_connected() or not records:
            return False
        
        try:
            collection = self.db[self.AGGREGATED_METRICS_COLLECTION]
            
            # Создаем индексы при первом сохранении
            if collection.count_documents({}) == 0:
                self._ensure_indexes(self.AGGREGATED_METRICS_COLLECTION)
            
            # Группировка по временным интервалам
            metrics_by_interval = {}
            
            for record in records:
                if 'timestamp' not in record or record['timestamp'] is None:
                    continue
                
                timestamp = record['timestamp']
                # Преобразование строки в datetime, если необходимо
                if isinstance(timestamp, str):
                    try:
                        timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    except:
                        try:
                            # Альтернативный формат
                            timestamp = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                        except:
                            continue
                elif not isinstance(timestamp, datetime):
                    continue
                
                # Определение интервала
                if interval_type == 'hour':
                    interval_start = timestamp.replace(minute=0, second=0, microsecond=0)
                else:  # day
                    interval_start = timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
                
                interval_key = interval_start.isoformat()
                
                if interval_key not in metrics_by_interval:
                    metrics_by_interval[interval_key] = {
                        'time_interval': interval_start,
                        'interval_type': interval_type,
                        'log_format': log_format,
                        'timestamp': interval_start,
                        'request_count': 0,
                        'status_distribution': {},
                        'level_distribution': {},
                        'unique_ips': set(),
                        'unique_urls': set()
                    }
                
                metrics = metrics_by_interval[interval_key]
                metrics['request_count'] += 1
                
                # Распределение по статусам
                if 'http_status' in record and record['http_status']:
                    status = record['http_status']
                    metrics['status_distribution'][status] = metrics['status_distribution'].get(status, 0) + 1
                
                # Распределение по уровням
                if 'level' in record and record['level']:
                    level = record['level']
                    metrics['level_distribution'][level] = metrics['level_distribution'].get(level, 0) + 1
                
                # Уникальные IP
                if 'ip_address' in record and record['ip_address']:
                    metrics['unique_ips'].add(record['ip_address'])
                
                # Уникальные URL
                if 'url' in record and record['url']:
                    metrics['unique_urls'].add(record['url'])
            
            # Преобразование в формат для сохранения
            metrics_docs = []
            for interval_key, metrics in metrics_by_interval.items():
                # Конвертируем ключи в строки для MongoDB (MongoDB требует строковые ключи)
                status_dist = {str(k): v for k, v in metrics['status_distribution'].items()}
                level_dist = {str(k): v for k, v in metrics['level_distribution'].items()}
                
                doc = {
                    'time_interval': metrics['time_interval'],
                    'interval_type': metrics['interval_type'],
                    'log_format': metrics['log_format'],
                    'timestamp': metrics['timestamp'],
                    'request_count': metrics['request_count'],
                    'status_distribution': status_dist,
                    'level_distribution': level_dist,
                    'unique_ips_count': len(metrics['unique_ips']),
                    'unique_urls_count': len(metrics['unique_urls']),
                    'owner_email': owner_email,
                    'created_at': datetime.now()
                }
                metrics_docs.append(doc)
            
            if metrics_docs:
                collection.insert_many(metrics_docs)
            return True
        except Exception as e:
            print(f"Ошибка при агрегации метрик: {e}")
            return False
    
    def save_logs_batch(
        self,
        filename: str,
        log_format: str,
        raw_lines: List[str],
        normalized_records: List[Dict],
        owner_email: Optional[str] = None,
    ) -> bool:
        """Сохранение логов на всех трех уровнях
        
        Args:
            filename: Имя файла
            log_format: Формат лога (apache, nginx, json, csv, text)
            raw_lines: Список сырых строк
            normalized_records: Список нормализованных записей
        """
        if not self.is_connected():
            return False
        
        try:
            # Уровень 1: Сохранение сырых данных
            self.save_raw_logs_batch(filename, log_format, raw_lines, owner_email=owner_email)
            
            # Уровень 2: Сохранение нормализованных данных (отдельная коллекция на файл)
            if normalized_records:
                self.save_normalized_logs_batch(
                    log_format,
                    normalized_records,
                    filename=filename,
                    owner_email=owner_email,
                )
                
                # Уровень 3: Агрегация и сохранение метрик
                self.aggregate_and_save_metrics(log_format, normalized_records, 'hour', owner_email=owner_email)
                self.aggregate_and_save_metrics(log_format, normalized_records, 'day', owner_email=owner_email)
            
            return True
        except Exception as e:
            print(f"Ошибка при сохранении логов: {e}")
            return False
    
    def clear_collection(self, collection_name: str) -> bool:
        """Очистка коллекции"""
        if not self.is_connected():
            return False
        
        try:
            collection = self.db[collection_name]
            collection.delete_many({})
            return True
        except Exception as e:
            print(f"Ошибка при очистке коллекции: {e}")
            return False
    
    def clear_all_logs(self, owner_email: Optional[str] = None) -> int:
        """Очистка логов на всех уровнях.

        Если `owner_email` указан — удаляются только данные конкретного пользователя.
        Если не указан — выполняется очистка как раньше (удаление коллекций целиком).
        """
        if not self.is_connected():
            return 0
        
        collections_deleted = 0
        try:
            if owner_email:
                # Удаляем только записи пользователя без удаления коллекций целиком
                if self.RAW_LOGS_COLLECTION in self.db.list_collection_names():
                    self.db[self.RAW_LOGS_COLLECTION].delete_many({'owner_email': owner_email})
                    collections_deleted += 1
            else:
                # Старое поведение: удаляем коллекцию полностью
                if self.RAW_LOGS_COLLECTION in self.db.list_collection_names():
                    self.db[self.RAW_LOGS_COLLECTION].drop()
                    collections_deleted += 1
            
            # Удаление нормализованных коллекций (удаляем коллекции полностью)
            collections_to_drop = []
            for collection_name in self.db.list_collection_names():
                if collection_name.endswith('_normalized'):
                    collections_to_drop.append(collection_name)
            
            for collection_name in collections_to_drop:
                if owner_email:
                    self.db[collection_name].delete_many({'owner_email': owner_email})
                    collections_deleted += 1
                else:
                    self.db[collection_name].drop()
                    collections_deleted += 1
            
            # Удаление агрегированных метрик (удаляем коллекцию полностью)
            if self.AGGREGATED_METRICS_COLLECTION in self.db.list_collection_names():
                if owner_email:
                    self.db[self.AGGREGATED_METRICS_COLLECTION].delete_many({'owner_email': owner_email})
                    collections_deleted += 1
                else:
                    self.db[self.AGGREGATED_METRICS_COLLECTION].drop()
                    collections_deleted += 1
        except Exception as e:
            print(f"Ошибка при удалении коллекций: {e}")
        
        return collections_deleted
    
    def drop_normalized_collection(self, collection_name: str) -> bool:
        """Удаление одной нормализованной коллекции по имени. Безопасно: только *_normalized."""
        if not self.is_connected():
            return False
        if not collection_name or not collection_name.endswith('_normalized'):
            return False
        if collection_name not in self.db.list_collection_names():
            return False
        try:
            self.db[collection_name].drop()
            return True
        except Exception as e:
            print(f"Ошибка при удалении коллекции {collection_name}: {e}")
            return False
    
    def get_collection_stats(self, collection_name: str) -> Dict:
        """Получение статистики по коллекции"""
        if not self.is_connected() or collection_name not in self.db.list_collection_names():
            return {}
        
        try:
            collection = self.db[collection_name]
            total = collection.count_documents({})
            
            stats = {'total': total}
            
            # Статистика по уровням (если поле есть)
            try:
                pipeline = [
                    {'$match': {'level': {'$exists': True, '$ne': None}}},
                    {'$group': {'_id': '$level', 'count': {'$sum': 1}}},
                    {'$sort': {'count': -1}}
                ]
                level_stats = list(collection.aggregate(pipeline))
                if level_stats:
                    stats['level_stats'] = level_stats
            except:
                pass
            
            # Статистика по источникам
            try:
                source_stats = list(collection.aggregate([
                    {'$match': {'file_source': {'$exists': True, '$ne': None}}},
                    {'$group': {'_id': '$file_source', 'count': {'$sum': 1}}},
                    {'$sort': {'count': -1}}
                ]))
                if source_stats:
                    stats['source_stats'] = source_stats
            except:
                pass
            
            # Статистика по HTTP статусам (если поле есть)
            try:
                status_stats = list(collection.aggregate([
                    {'$match': {'http_status': {'$exists': True, '$ne': None}}},
                    {'$group': {'_id': '$http_status', 'count': {'$sum': 1}}},
                    {'$sort': {'count': -1}},
                    {'$limit': 10}
                ]))
                if status_stats:
                    stats['status_stats'] = status_stats
            except:
                pass
            
            return stats
        except Exception as e:
            print(f"Ошибка при получении статистики: {e}")
            return {}

