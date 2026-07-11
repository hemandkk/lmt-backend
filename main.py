from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text

from app.api.v1.api import api_router
from app.api.v1.payments import router as payment_router
from app.core.security import hash_password
from app.db.base import Base
from app.db.models.activity_log import ActivityLog
from app.db.models.app_setting import AppSetting
from app.db.models.course import Course
from app.db.models.incentive_slab import IncentiveSlab
from app.db.models.notification import Notification
from app.db.models.payment import Payment
from app.db.models.prospect import Prospect
from app.db.models.prospect_document import ProspectDocument
from app.db.models.user import User, UserRole
from app.db.session import SessionLocal, engine
from app.repositories.settings_repository import (
    FALLBACK_DEFAULT_TARGET,
    SettingsRepository,
)

UPLOAD_DIR = Path("app/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

Base.metadata.create_all(bind=engine)


def ensure_schema_updates() -> None:
    """
    create_all() does not ADD columns to existing tables.
    Apply safe, idempotent column/index patches here.
    """
    with engine.begin() as conn:
        inspector = inspect(conn)
        tables = inspector.get_table_names()

        if "prospects" in tables:
            existing = {col["name"] for col in inspector.get_columns("prospects")}

            if "source" not in existing:
                conn.execute(
                    text("ALTER TABLE prospects ADD COLUMN source VARCHAR(100)")
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_prospects_source "
                        "ON prospects (source)"
                    )
                )

            if "follow_up_date" not in existing:
                conn.execute(
                    text("ALTER TABLE prospects ADD COLUMN follow_up_date DATE")
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_prospects_follow_up_date "
                        "ON prospects (follow_up_date)"
                    )
                )

        if "users" in tables:
            user_cols = {col["name"] for col in inspector.get_columns("users")}
            if "monthly_sales_target" not in user_cols:
                # NULL = not assigned → master default applies
                conn.execute(
                    text(
                        "ALTER TABLE users "
                        "ADD COLUMN monthly_sales_target NUMERIC(12, 2) "
                        "DEFAULT NULL"
                    )
                )
            else:
                # Drop server default so new employees inherit master default
                try:
                    conn.execute(
                        text(
                            "ALTER TABLE users "
                            "ALTER COLUMN monthly_sales_target DROP DEFAULT"
                        )
                    )
                except Exception:
                    pass


def seed_default_incentive_slabs() -> None:
    """Seed starter slabs when the table is empty."""
    db = SessionLocal()
    try:
        if db.query(IncentiveSlab).count() > 0:
            return
        defaults = [
            (0, 25000, 1),
            (25000, 50000, 2),
            (50000, 100000, 3),
            (100000, None, 5),
        ]
        for min_amount, max_amount, rate in defaults:
            db.add(
                IncentiveSlab(
                    min_amount=min_amount,
                    max_amount=max_amount,
                    rate_percent=rate,
                    is_active=True,
                )
            )
        db.commit()
    finally:
        db.close()


def seed_default_sales_target() -> None:
    """Ensure master default monthly sales target exists."""
    from app.db.models.app_setting import DEFAULT_MONTHLY_SALES_TARGET

    db = SessionLocal()
    try:
        if SettingsRepository.get(db, DEFAULT_MONTHLY_SALES_TARGET) is None:
            SettingsRepository.set_default_monthly_sales_target(
                db, FALLBACK_DEFAULT_TARGET
            )
    finally:
        db.close()


ensure_schema_updates()
seed_default_incentive_slabs()
seed_default_sales_target()

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