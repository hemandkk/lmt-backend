from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.prospects import router as prospect_router
from app.api.v1.masters import router as masters_router


from app.api.v1.documents import (
    router as document_router,
)

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(prospect_router)
api_router.include_router(masters_router)


api_router.include_router(
    document_router,
)

""" from fastapi import APIRouter

from app.api.v1 import auth

api_router = APIRouter()

api_router.include_router(auth.router)


 """