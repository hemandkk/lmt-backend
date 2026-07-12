from decimal import Decimal

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.models.prospect import Prospect
from app.db.models.user import User, UserRole
from app.repositories.analytics_repository import AnalyticsRepository
from app.repositories.user_repository import UserRepository
from app.schemas.employee import (
    EmployeeCreate,
    EmployeeListResponse,
    EmployeeResponse,
    EmployeeUpdate,
)
from app.services.master_service import resolve_employee_monthly_target


class EmployeeService:

    @staticmethod
    def _to_response(db: Session, user: User) -> EmployeeResponse:
        effective, assigned, source = resolve_employee_monthly_target(db, user)
        leads_assigned = (
            db.query(func.count(Prospect.id))
            .filter(Prospect.assigned_to_id == user.id)
            .scalar()
            or 0
        )
        revenue = AnalyticsRepository.payment_collected(
            db, employee_id=user.id
        )
        return EmployeeResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            employee_code=user.employee_id,
            role=user.role.value if hasattr(user.role, "value") else str(user.role),
            is_active=bool(user.is_active),
            assigned_target=(
                Decimal(str(user.monthly_sales_target))
                if user.monthly_sales_target is not None
                else None
            ),
            effective_target=effective,
            target_assigned=assigned,
            target_source=source,
            leads_assigned=int(leads_assigned),
            revenue=Decimal(str(revenue or 0)),
            last_login=user.last_login,
            created_at=getattr(user, "created_at", None),
            updated_at=getattr(user, "updated_at", None),
        )

    @staticmethod
    def list(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
        is_active: bool | None = None,
    ) -> EmployeeListResponse:
        query = db.query(User).filter(User.role == UserRole.employee)

        if is_active is not None:
            query = query.filter(User.is_active.is_(is_active))

        if search:
            pattern = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    User.name.ilike(pattern),
                    User.email.ilike(pattern),
                    User.employee_id.ilike(pattern),
                )
            )

        total = query.count()
        users = (
            query.order_by(User.name.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        items = [EmployeeService._to_response(db, u) for u in users]
        return EmployeeListResponse.build(items, total, page, page_size)

    @staticmethod
    def get(db: Session, employee_id: int) -> EmployeeResponse:
        user = UserRepository.get_by_id(db, employee_id)
        if not user or user.role != UserRole.employee:
            raise ValueError("Employee not found.")
        return EmployeeService._to_response(db, user)

    @staticmethod
    def create(db: Session, payload: EmployeeCreate) -> EmployeeResponse:
        if UserRepository.get_by_email(db, payload.email):
            raise ValueError("Email already exists.")

        code = payload.employee_code
        if code and UserRepository.get_by_employee_id(db, code):
            raise ValueError("Employee ID already exists.")

        if not code:
            # Generate simple EMP00N code
            count = (
                db.query(func.count(User.id))
                .filter(User.role == UserRole.employee)
                .scalar()
                or 0
            )
            code = f"EMP{count + 1:04d}"
            while UserRepository.get_by_employee_id(db, code):
                count += 1
                code = f"EMP{count + 1:04d}"

        user = User(
            name=payload.name,
            email=str(payload.email).lower(),
            employee_id=code,
            password_hash=hash_password(payload.password),
            role=UserRole.employee,
            is_active=payload.is_active,
            monthly_sales_target=payload.monthly_target,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return EmployeeService._to_response(db, user)

    @staticmethod
    def update(
        db: Session,
        employee_id: int,
        payload: EmployeeUpdate,
    ) -> EmployeeResponse:
        user = UserRepository.get_by_id(db, employee_id)
        if not user or user.role != UserRole.employee:
            raise ValueError("Employee not found.")

        data = payload.model_dump(exclude_unset=True)

        if "email" in data and data["email"] is not None:
            email = str(data["email"]).lower()
            existing = UserRepository.get_by_email(db, email)
            if existing and existing.id != user.id:
                raise ValueError("Email already exists.")
            user.email = email

        if "employee_code" in data and data["employee_code"] is not None:
            code = data["employee_code"]
            existing = UserRepository.get_by_employee_id(db, code)
            if existing and existing.id != user.id:
                raise ValueError("Employee ID already exists.")
            user.employee_id = code

        if "name" in data and data["name"] is not None:
            user.name = data["name"]

        if "password" in data and data["password"]:
            user.password_hash = hash_password(data["password"])

        if "is_active" in data and data["is_active"] is not None:
            user.is_active = data["is_active"]

        if data.get("clear_monthly_target"):
            user.monthly_sales_target = None
        elif "monthly_target" in data and data["monthly_target"] is not None:
            user.monthly_sales_target = data["monthly_target"]

        db.commit()
        db.refresh(user)
        return EmployeeService._to_response(db, user)

    @staticmethod
    def deactivate(db: Session, employee_id: int) -> None:
        user = UserRepository.get_by_id(db, employee_id)
        if not user or user.role != UserRole.employee:
            raise ValueError("Employee not found.")
        user.is_active = False
        db.commit()
