from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.models.user import User
from app.db.session import get_db
from app.repositories.user_repository import UserRepository

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login"
)

optional_oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login",
    auto_error=False,
)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )

    try:
        payload = decode_token(token)

    except JWTError:
        raise credentials_exception

    if payload.get("type") != "access":
        raise credentials_exception

    user_id = payload.get("sub")

    if user_id is None:
        raise credentials_exception

    user = UserRepository.get_by_id(
        db,
        int(user_id),
    )

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user.",
        )

    token_iat = payload.get("iat")
    if token_iat is not None and user.last_logout is not None:
        if isinstance(token_iat, (int, float)):
            token_iat_dt = datetime.fromtimestamp(
                token_iat, tz=timezone.utc
            )
        else:
            token_iat_dt = token_iat
            if token_iat_dt.tzinfo is None:
                token_iat_dt = token_iat_dt.replace(
                    tzinfo=timezone.utc
                )

        last_logout = user.last_logout
        if last_logout.tzinfo is None:
            last_logout = last_logout.replace(tzinfo=timezone.utc)

        if token_iat_dt <= last_logout:
            raise credentials_exception

    return user


def get_optional_user(
    token: Optional[str] = Depends(optional_oauth2_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    if not token:
        return None
    try:
        return get_current_user(token=token, db=db)
    except HTTPException:
        return None
