from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)
from jose import JWTError
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.db.session import get_db

from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RefreshRequest,
)

from app.services.auth_service import (
    AuthService,
)

from app.repositories.user_repository import (
    UserRepository,
)

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

from app.core.roles import role_value
from app.dependencies.auth import get_current_user
from app.db.models.user import User

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)

limiter = Limiter(key_func=get_remote_address)


def _user_payload(user: User) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "employee_id": user.employee_id,
        "role": role_value(user),
    }


@router.post("/login")
@limiter.limit("5/minute")
def login(
    request: Request,
    payload: LoginRequest,
    db: Session = Depends(get_db),
):
    result = AuthService.login(
        db,
        payload.username,
        payload.password,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    user, access_token = result

    user.last_login = datetime.now(timezone.utc)
    db.commit()

    refresh_token = create_refresh_token(
        {
            "sub": str(user.id),
            "role": role_value(user),
        }
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": _user_payload(user),
    }


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return {"user": _user_payload(current_user)}


@router.post("/refresh")
@limiter.limit("10/minute")
def refresh(
    request: Request,
    payload: RefreshRequest,
    db: Session = Depends(get_db),
):
    try:
        claims = decode_token(payload.refresh_token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    if claims.get("type") != "refresh":
        raise HTTPException(
            status_code=401,
            detail="Invalid token",
        )

    user = UserRepository.get_by_id(
        db,
        int(claims["sub"]),
    )
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid token",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user.",
        )

    token_iat = claims.get("iat")
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
            raise HTTPException(
                status_code=401,
                detail="Token has been revoked",
            )

    access_token = create_access_token(
        {
            "sub": str(user.id),
            "role": user.role.value,
        }
    )

    return {
        "access_token": access_token
    }


@router.post("/logout")
def logout(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user.last_logout = datetime.now(timezone.utc)
    db.commit()

    return {
        "message": "Logged out successfully"
    }


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    current_user.password_hash = hash_password(payload.new_password)
    db.commit()

    return {"message": "Password changed successfully"}
