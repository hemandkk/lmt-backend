from datetime import datetime, timedelta, timezone
from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not plain_password or not hashed_password:
        return False
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False


def create_access_token(data: dict):
    now = datetime.now(timezone.utc)
    payload = data.copy()

    payload["type"] = "access"
    payload["iat"] = now
    payload["exp"] = now + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=ALGORITHM,
    )


def create_refresh_token(data: dict):
    now = datetime.now(timezone.utc)
    payload = data.copy()

    payload["type"] = "refresh"
    payload["iat"] = now
    payload["exp"] = now + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=ALGORITHM,
    )


def decode_token(token: str):
    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[ALGORITHM],
    )
