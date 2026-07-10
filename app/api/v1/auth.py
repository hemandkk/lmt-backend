from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from sqlalchemy.orm import Session

from app.db.session import get_db

from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
)

from app.services.auth_service import (
    AuthService,
)

from app.repositories.user_repository import (
    UserRepository,
)
from app.core.security import hash_password

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post("/login")
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
):

    result = AuthService.login(
        db,
        payload.username,
        payload.password,
    )
    print("###########")
    print(result)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    user, access_token = result

    refresh_token = create_refresh_token(
        {
            "sub": str(user.id),
            "role": user.role.value,
        }
    )
    print("$#$#$#")
    print(refresh_token)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "employee_id": user.employee_id,
            "role": user.role.value,
        },
    }


@router.post("/refresh")
def refresh(
    payload: RefreshRequest,
    db: Session = Depends(get_db),
):

    claims = decode_token(
        payload.refresh_token
    )

    if claims["type"] != "refresh":
        raise HTTPException(
            status_code=401,
            detail="Invalid token",
        )

    user = UserRepository.get_by_id(
        db,
        int(claims["sub"]),
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
def logout():
    return {
        "message": "Logged out"
    }