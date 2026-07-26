from datetime import datetime
from typing import Any, Dict, Optional

from pymongo import MongoClient

import config


class AuditLogger:
    """Простая система аудита действий пользователей."""

    AUDIT_COLLECTION = "audit_logs"

    def __init__(self) -> None:
        self.client = MongoClient(
            config.MONGO_CONNECTION_STRING,
            serverSelectionTimeoutMS=5000,
        )
        self.db = self.client[config.MONGO_DB_NAME]
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        try:
            self.db[self.AUDIT_COLLECTION].create_index("created_at")
            self.db[self.AUDIT_COLLECTION].create_index("user_email")
            self.db[self.AUDIT_COLLECTION].create_index("action")
        except Exception:
            pass

    def log(
        self,
        action: str,
        user_email: Optional[str],
        status: str = "success",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        doc = {
            "action": action,
            "user_email": user_email,
            "status": status,
            "metadata": metadata or {},
            "created_at": datetime.utcnow(),
        }
        try:
            self.db[self.AUDIT_COLLECTION].insert_one(doc)
        except Exception:
            # Аудит не должен ломать работу основного приложения
            pass

    def get_recent(self, limit: int = 50) -> list[Dict[str, Any]]:
        """Получает последние записи аудита (по полю created_at)."""
        try:
            cursor = (
                self.db[self.AUDIT_COLLECTION]
                .find({}, projection={"_id": 0})
                .sort("created_at", -1)
                .limit(int(limit))
            )
            results = list(cursor)
            for doc in results:
                created = doc.get("created_at")
                if isinstance(created, datetime):
                    doc["created_at"] = created.strftime("%Y-%m-%d %H:%M:%S")
            return results
        except Exception:
            return []

