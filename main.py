from pathlib import Path
from contextlib import asynccontextmanager

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
from app.db.models.specialization import Specialization
from app.db.models.state import State
from app.db.models.branch import Branch
from app.db.models.incentive_slab import IncentiveSlab
from app.db.models.notification import Notification
from app.db.models.payment import Payment
from app.db.models.prospect import Prospect
from app.db.models.prospect_document import ProspectDocument
from app.db.models.user import User, UserRole
from app.core.config import settings

from app.db.session import SessionLocal, engine
from app.repositories.settings_repository import (
    FALLBACK_DEFAULT_TARGET,
    SettingsRepository,
)

# Setup directories
UPLOAD_DIR = Path("app/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def ensure_schema_updates() -> None:
    """
    Applies safe, idempotent column/index patches.
    """
    with engine.begin() as conn:
        inspector = inspect(conn)
        tables = inspector.get_table_names()

        if "prospects" in tables:
            existing = {col["name"] for col in inspector.get_columns("prospects")}
            if "source" not in existing:
                conn.execute(text("ALTER TABLE prospects ADD COLUMN source VARCHAR(100)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_prospects_source ON prospects (source)"))
            if "follow_up_date" not in existing:
                conn.execute(text("ALTER TABLE prospects ADD COLUMN follow_up_date DATE"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_prospects_follow_up_date ON prospects (follow_up_date)"))
            if "created_by_id" not in existing:
                conn.execute(text("ALTER TABLE prospects ADD COLUMN created_by_id INTEGER REFERENCES users(id)"))
            if "updated_by_id" not in existing:
                conn.execute(text("ALTER TABLE prospects ADD COLUMN updated_by_id INTEGER REFERENCES users(id)"))
            if "admission_stage" not in existing:
                conn.execute(text("ALTER TABLE prospects ADD COLUMN admission_stage VARCHAR(50) NOT NULL DEFAULT 'registered'"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_prospects_admission_stage ON prospects (admission_stage)"))

        if "users" in tables:
            user_cols = {col["name"] for col in inspector.get_columns("users")}
            if "monthly_sales_target" not in user_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN monthly_sales_target NUMERIC(12, 2) DEFAULT NULL"))
            else:
                try:
                    conn.execute(text("ALTER TABLE users ALTER COLUMN monthly_sales_target DROP DEFAULT"))
                except Exception:
                    pass

            if "phone" not in user_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN phone VARCHAR(30)"))
            if "department" not in user_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN department VARCHAR(100)"))
            if "designation" not in user_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN designation VARCHAR(100)"))

            for role_value in ("accountant", "processing_team", "manager", "sales_head"):
                try:
                    conn.execute(text(f"ALTER TYPE userrole ADD VALUE IF NOT EXISTS '{role_value}'"))
                except Exception:
                    try:
                        conn.execute(text(f"ALTER TYPE userrole ADD VALUE '{role_value}'"))
                    except Exception:
                        pass

            if "reports_to_manager_id" not in user_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN reports_to_manager_id INTEGER REFERENCES users(id) ON DELETE SET NULL"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_reports_to_manager_id ON users (reports_to_manager_id)"))
            if "reports_to_sales_head_id" not in user_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN reports_to_sales_head_id INTEGER REFERENCES users(id) ON DELETE SET NULL"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_reports_to_sales_head_id ON users (reports_to_sales_head_id)"))

        if "payments" in tables:
            pay_cols = {col["name"] for col in inspector.get_columns("payments")}
            if "verification_status" not in pay_cols:
                conn.execute(text("ALTER TABLE payments ADD COLUMN verification_status VARCHAR(30) NOT NULL DEFAULT 'not_verified'"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_payments_verification_status ON payments (verification_status)"))
            if "verified_at" not in pay_cols:
                conn.execute(text("ALTER TABLE payments ADD COLUMN verified_at TIMESTAMPTZ"))


def seed_default_admin_user() -> None:
    """
    Seeds default admin configurations into clean DB.
    """
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
            print("🚀 SEEDER: New admin user instantiated.", flush=True)
        else:
            user.employee_id = "ADM001"
            user.name = "Admin User"
            user.role = UserRole.admin
            user.is_active = True
            print("ℹ️ SEEDER: Admin record matched. Properties updated.", flush=True)
        db.commit()
        print("✅ SEEDER: Transaction successfully committed to lmt_db.", flush=True)
    except Exception as e:
        db.rollback()
        print(f"❌ SEEDER CRASHED: {e}", flush=True)
    finally:
        db.close()



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

# 💡 MODERN LIFESPAN LIFECYCLE HANDLER
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("⏳ STARTUP: Initializing application tables and rules...", flush=True)
    
    # 1. Safely handle table generation
    Base.metadata.create_all(bind=engine)
    
    # 2. Run manual patch migrations
    ensure_schema_updates()
    
    # 3. Seed your data completely
    seed_default_admin_user()
    seed_default_incentive_slabs()
    seed_default_sales_target()
    
    yield
    print("🛑 SHUTTING DOWN: Closing app hooks...", flush=True)


# Initialize FastAPI with modern Lifespan hook
app = FastAPI(lifespan=lifespan)

origins = [
    origin.strip()
    for origin in settings.CORS_ORIGINS.split(",")
    if origin.strip()
]
# Add CORS Middleware configurations
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Route Mounting
app.include_router(api_router, prefix=settings.API_V1_STR)
app.include_router(payment_router, prefix=f"{settings.API_V1_STR}/payments", tags=["payments"])

app.mount(
    "/uploads",
    StaticFiles(directory=str(UPLOAD_DIR)),
    name="uploads",
)
