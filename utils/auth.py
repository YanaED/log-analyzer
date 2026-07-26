import secrets
from datetime import datetime, timedelta
from typing import Optional, Tuple

from pymongo import MongoClient
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from werkzeug.security import generate_password_hash, check_password_hash

import config


class UserManager:
    """Управление пользователями (регистрация, подтверждение, поиск) в MongoDB."""

    USERS_COLLECTION = "users"

    def __init__(self) -> None:
        self.client = MongoClient(
            config.MONGO_CONNECTION_STRING,
            serverSelectionTimeoutMS=5000,
        )
        self.db = self.client[config.MONGO_DB_NAME]
        self.serializer = URLSafeTimedSerializer(config.SECRET_KEY)
        self._ensure_indexes()

    @property
    def collection(self):
        return self.db[self.USERS_COLLECTION]

    def _ensure_indexes(self) -> None:
        try:
            self.collection.create_index("email", unique=True)
        except Exception:
            # Индекс уже существует или Mongo недоступна — не критично
            pass

    def find_by_email(self, email: str) -> Optional[dict]:
        email_norm = email.lower().strip()
        return self.collection.find_one({"email": email_norm})

    def create_user(
        self,
        email: str,
        password: str,
        require_confirmation: bool = True,
    ) -> Tuple[Optional[dict], Optional[str], Optional[str]]:
        """
        Создание пользователя.

        Returns: (user_doc, verification_code_plain, error_message)
        verification_code_plain — 6 цифр для письма, если нужно подтверждение; иначе None.
        """
        email_norm = email.lower().strip()

        if self.find_by_email(email_norm):
            return None, None, "Пользователь с таким e-mail уже зарегистрирован"

        password_hash = generate_password_hash(password)

        is_confirmed = not require_confirmation
        verification_code_plain = None
        verification_code_hash = None
        verification_code_expires_at = None

        if require_confirmation:
            verification_code_plain = f"{secrets.randbelow(900_000) + 100_000:06d}"
            verification_code_hash = generate_password_hash(verification_code_plain)
            verification_code_expires_at = datetime.utcnow() + timedelta(minutes=30)

        user_doc = {
            "email": email_norm,
            "password_hash": password_hash,
            "is_confirmed": is_confirmed,
            "confirmation_token": None,
            "verification_code_hash": verification_code_hash,
            "verification_code_expires_at": verification_code_expires_at,
            "created_at": datetime.utcnow(),
        }

        try:
            result = self.collection.insert_one(user_doc)
            user_doc["_id"] = result.inserted_id
            return user_doc, verification_code_plain, None
        except Exception as e:
            return None, None, f"Ошибка сохранения пользователя: {e}"

    def confirm_by_code(self, email: str, code: str) -> Tuple[bool, str]:
        """Подтверждение e-mail по коду из письма (без перехода по ссылке)."""
        email_norm = (email or "").lower().strip()
        code_clean = (code or "").strip().replace(" ", "")
        if not email_norm or not code_clean:
            return False, "Введите e-mail и код"
        user = self.find_by_email(email_norm)
        if not user:
            return False, "Пользователь не найден"
        if user.get("is_confirmed"):
            return False, "Этот e-mail уже подтверждён — войдите на вкладке «Вход»"
        h = user.get("verification_code_hash")
        exp = user.get("verification_code_expires_at")
        if not h:
            return False, "Код не найден. Запросите повторную отправку или зарегистрируйтесь снова"
        if exp and datetime.utcnow() > exp:
            return False, "Срок действия кода истёк. Нажмите «Выслать код повторно»"
        if not check_password_hash(h, code_clean):
            return False, "Неверный код"
        try:
            self.collection.update_one(
                {"_id": user["_id"]},
                {
                    "$set": {"is_confirmed": True},
                    "$unset": {
                        "verification_code_hash": "",
                        "verification_code_expires_at": "",
                        "confirmation_token": "",
                    },
                },
            )
        except Exception as e:
            return False, f"Не удалось сохранить подтверждение: {e}"
        return True, "E-mail подтверждён. Теперь можно войти."

    def regenerate_verification_code(self, email: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Новый код для неподтверждённого пользователя.
        Возвращает (plain_code, error_message).
        """
        email_norm = (email or "").lower().strip()
        if not email_norm:
            return None, "Введите e-mail"
        user = self.find_by_email(email_norm)
        if not user:
            return None, "Пользователь с таким e-mail не найден"
        if user.get("is_confirmed"):
            return None, "Этот e-mail уже подтверждён"
        plain = f"{secrets.randbelow(900_000) + 100_000:06d}"
        code_hash = generate_password_hash(plain)
        exp = datetime.utcnow() + timedelta(minutes=30)
        try:
            self.collection.update_one(
                {"_id": user["_id"]},
                {
                    "$set": {
                        "verification_code_hash": code_hash,
                        "verification_code_expires_at": exp,
                    }
                },
            )
        except Exception as e:
            return None, f"Ошибка: {e}"
        return plain, None

    def confirm_by_token(self, token: str, max_age_seconds: int = 60 * 60 * 24) -> Tuple[bool, str]:
        """Подтверждение e-mail по токену."""
        try:
            email = self.serializer.loads(token, max_age=max_age_seconds)
        except SignatureExpired:
            return False, "Ссылка подтверждения истекла"
        except BadSignature:
            return False, "Некорректная ссылка подтверждения"

        email_norm = email.lower().strip()
        user = self.find_by_email(email_norm)
        if not user:
            return False, "Пользователь не найден"

        try:
            self.collection.update_one(
                {"_id": user["_id"]},
                {"$set": {"is_confirmed": True}, "$unset": {"confirmation_token": ""}},
            )
        except Exception as e:
            return False, f"Не удалось обновить статус пользователя: {e}"

        return True, "E-mail успешно подтверждён"

    @staticmethod
    def verify_password(user: dict, password: str) -> bool:
        return check_password_hash(user.get("password_hash", ""), password)

