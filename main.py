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

        if "incentive_slabs" in tables:
            slab_cols = {
                col["name"] for col in inspector.get_columns("incentive_slabs")
            }
            had_amount_based = (
                "min_amount" in slab_cols or "rate_percent" in slab_cols
            )
            # Migrate amount/% slabs → lead-count + fixed incentive amount
            if "min_leads" not in slab_cols:
                conn.execute(
                    text(
                        "ALTER TABLE incentive_slabs "
                        "ADD COLUMN min_leads INTEGER"
                    )
                )
            if "max_leads" not in slab_cols:
                conn.execute(
                    text(
                        "ALTER TABLE incentive_slabs "
                        "ADD COLUMN max_leads INTEGER"
                    )
                )
            if "incentive_amount" not in slab_cols:
                conn.execute(
                    text(
                        "ALTER TABLE incentive_slabs "
                        "ADD COLUMN incentive_amount NUMERIC(12, 2)"
                    )
                )

            if had_amount_based:
                # Old amount-based rows are meaningless under the new scheme
                conn.execute(text("DELETE FROM incentive_slabs"))
                for old_col in ("min_amount", "max_amount", "rate_percent"):
                    if old_col in slab_cols:
                        conn.execute(
                            text(
                                f"ALTER TABLE incentive_slabs "
                                f"DROP COLUMN IF EXISTS {old_col}"
                            )
                        )

            conn.execute(
                text(
                    "UPDATE incentive_slabs "
                    "SET min_leads = 0 "
                    "WHERE min_leads IS NULL"
                )
            )
            conn.execute(
                text(
                    "UPDATE incentive_slabs "
                    "SET incentive_amount = 0 "
                    "WHERE incentive_amount IS NULL"
                )
            )
            try:
                conn.execute(
                    text(
                        "ALTER TABLE incentive_slabs "
                        "ALTER COLUMN min_leads SET NOT NULL"
                    )
                )
                conn.execute(
                    text(
                        "ALTER TABLE incentive_slabs "
                        "ALTER COLUMN incentive_amount SET NOT NULL"
                    )
                )
            except Exception:
                pass


def seed_default_incentive_slabs() -> None:
    """Seed starter lead-count slabs when the table is empty."""
    db = SessionLocal()
    try:
        if db.query(IncentiveSlab).count() > 0:
            return
        # (min_leads, max_leads, incentive_amount)
        defaults = [
            (0, 9, 0),
            (10, 15, 500),
            (16, 25, 1000),
            (26, None, 2000),
        ]
        for min_leads, max_leads, amount in defaults:
            db.add(
                IncentiveSlab(
                    min_leads=min_leads,
                    max_leads=max_leads,
                    incentive_amount=amount,
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
                password_hash=hash_password("asdf1234"),
                role=UserRole.admin,
                is_active=True,
            )
            db.add(user)
        else:
            # Keep existing password — do not reset on every restart
            user.employee_id = "ADM001"
            user.name = "Admin User"
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