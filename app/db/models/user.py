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
    func
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column
)
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.db.mixins import TimestampMixin

class UserRole(str, enum.Enum):
    admin = "admin"
    employee = "employee"
    accountant = "accountant"
    processing_team = "processing_team"

class User(TimestampMixin, Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)

    email = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True
    )

    employee_id = Column(
        String(50),
        unique=True,
        nullable=True,
        index=True
    )

    name = Column(String(255))

    phone = Column(String(30), nullable=True)

    department = Column(String(100), nullable=True)

    designation = Column(String(100), nullable=True)

    password_hash = Column(
        String,
        nullable=False
    )

    role = Column(
        Enum(UserRole),
        nullable=False
    )

    is_active = Column(
        Boolean,
        default=True
    )

    monthly_sales_target = Column(
        Numeric(12, 2),
        nullable=True,
        default=None,
    )

    last_login = Column(
        DateTime(timezone=True)
    )

    last_logout = Column(
        DateTime(timezone=True)
    )

    """ profile = relationship(
        "EmployeeProfile",
        back_populates="user",
        uselist=False
    ) """
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