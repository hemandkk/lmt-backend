import enum
from sqlalchemy import (
    String,
    Boolean,
    Enum,
    Integer,
    Column,
    DateTime,
    ForeignKey,
    Numeric,
)
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.db.mixins import TimestampMixin


class UserRole(str, enum.Enum):
    admin = "admin"
    employee = "employee"
    accountant = "accountant"
    processing_team = "processing_team"
    manager = "manager"
    sales_head = "sales_head"


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)

    email = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    employee_id = Column(
        String(50),
        unique=True,
        nullable=True,
        index=True,
    )

    name = Column(String(255))

    phone = Column(String(30), nullable=True)

    department = Column(String(100), nullable=True)

    designation = Column(String(100), nullable=True)

    password_hash = Column(
        String,
        nullable=False,
    )

    role = Column(
        Enum(UserRole),
        nullable=False,
    )

    is_active = Column(
        Boolean,
        default=True,
    )

    monthly_sales_target = Column(
        Numeric(12, 2),
        nullable=True,
        default=None,
    )

    reports_to_manager_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    reports_to_sales_head_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    last_login = Column(
        DateTime(timezone=True)
    )

    last_logout = Column(
        DateTime(timezone=True)
    )

    prospects = relationship(
        "Prospect",
        back_populates="assigned_to",
        foreign_keys="Prospect.assigned_to_id",
    )

    notifications = relationship(
        "Notification",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    activity_logs = relationship(
        "ActivityLog",
        back_populates="user",
    )

    reports_to_manager = relationship(
        "User",
        remote_side=[id],
        foreign_keys=[reports_to_manager_id],
        backref="managed_employees",
    )

    reports_to_sales_head = relationship(
        "User",
        remote_side=[id],
        foreign_keys=[reports_to_sales_head_id],
        backref="sales_head_employees",
    )
