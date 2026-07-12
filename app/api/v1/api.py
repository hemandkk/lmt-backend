from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.prospects import router as prospect_router
from app.api.v1.masters import router as masters_router
from app.api.v1.documents import router as document_router
from app.api.v1.payments import router as payment_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.reports import router as reports_router
from app.api.v1.exports import router as exports_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.activity_logs import router as activity_logs_router
from app.api.v1.employees import router as employees_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(prospect_router)
api_router.include_router(masters_router)
api_router.include_router(document_router)
api_router.include_router(payment_router)
api_router.include_router(dashboard_router)
api_router.include_router(reports_router)
api_router.include_router(exports_router)
api_router.include_router(notifications_router)
api_router.include_router(activity_logs_router)
api_router.include_router(employees_router)
