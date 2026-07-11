from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.api import api_router
from app.api.v1.payments import router as payment_router
from app.core.security import hash_password
from app.db.base import Base
from app.db.models.activity_log import ActivityLog
from app.db.models.notification import Notification
from app.db.models.payment import Payment
from app.db.models.prospect import Prospect
from app.db.models.prospect_document import ProspectDocument
from app.db.models.user import User, UserRole
from app.db.session import SessionLocal, engine

UPLOAD_DIR = Path("app/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="LMT API",
    version="1.0.0"
)

origins = [
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    api_router,
    prefix="/api/v1"
)

app.include_router(payment_router)


@app.on_event("startup")
def seed_default_admin_user():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "admin@example.com").first()
        if user is None:
            user = User(
                email="admin@example.com",
                employee_id="ADM001",
                name="Admin User",
                password_hash=hash_password("admin123"),
                role=UserRole.admin,
                is_active=True,
            )
            db.add(user)
        else:
            user.employee_id = "ADM001"
            user.name = "Admin User"
            user.password_hash = hash_password("admin123")
            user.role = UserRole.admin
            user.is_active = True
        db.commit()
    finally:
        db.close()


app.mount(
    "/uploads",
    StaticFiles(directory=str(UPLOAD_DIR)),
    name="uploads",
)