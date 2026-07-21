from decimal import Decimal

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.core.roles import ASSIGNABLE_ROLES, SALES_ROLES, normalize_role
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
from app.services.notification_service import ActivityLogService
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException

class EmployeeService:

    @staticmethod
    def _staff_roles():
        return list(ASSIGNABLE_ROLES)

    @staticmethod
    def _validate_supervisor(
        db: Session,
        supervisor_id: int | None,
        expected_role: UserRole,
        field_name: str,
    ) -> None:
        if supervisor_id is None:
            return
        supervisor = UserRepository.get_by_id(db, supervisor_id)
        if (
            not supervisor
            or not supervisor.is_active
            or supervisor.role != expected_role
        ):
            raise ValueError(
                f"{field_name} must be an active {expected_role.value}."
            )

    @staticmethod
    def _to_response(db: Session, user: User) -> EmployeeResponse:
        effective, assigned, source = resolve_employee_monthly_target(db, user)
        leads_assigned = 0
        revenue = Decimal("0")
        if user.role in SALES_ROLES:
            leads_assigned = (
                db.query(func.count(Prospect.id))
                .filter(Prospect.assigned_to_id == user.id)
                .scalar()
                or 0
            )
            revenue = Decimal(
                str(
                    AnalyticsRepository.payment_collected(
                        db, employee_id=user.id
                    )
                    or 0
                )
            )
        assigned_target = (
            Decimal(str(user.monthly_sales_target))
            if user.monthly_sales_target is not None
            else None
        )
        role_value = (
            user.role.value if hasattr(user.role, "value") else str(user.role)
        )
        manager = getattr(user, "reports_to_manager", None)
        sales_head = getattr(user, "reports_to_sales_head", None)
        return EmployeeResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            phone=getattr(user, "phone", None),
            department=getattr(user, "department", None),
            designation=getattr(user, "designation", None),
            employee_code=user.employee_id,
            role=role_value,
            status="active" if user.is_active else "inactive",
            is_active=bool(user.is_active),
            monthly_target=assigned_target,
            assigned_target=assigned_target,
            effective_target=effective,
            target_assigned=assigned,
            target_source=source,
            leads_assigned=int(leads_assigned),
            revenue=revenue,
            reports_to_manager_id=user.reports_to_manager_id,
            reports_to_manager_name=(
                manager.name if manager is not None else None
            ),
            reports_to_sales_head_id=user.reports_to_sales_head_id,
            reports_to_sales_head_name=(
                sales_head.name if sales_head is not None else None
            ),
            last_login=user.last_login,
            created_at=getattr(user, "created_at", None),
            updated_at=getattr(user, "updated_at", None),
        )

    @staticmethod
    def _load_user(db: Session, employee_id: int) -> User | None:
        return (
            db.query(User)
            .options(
                joinedload(User.reports_to_manager),
                joinedload(User.reports_to_sales_head),
            )
            .filter(User.id == employee_id)
            .first()
        )

    @staticmethod
    def list(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
        is_active: bool | None = None,
        role: str | None = None,
        sales_only: bool = False,
    ) -> EmployeeListResponse:
        if sales_only:
            # Dashboard / assign dropdowns: sales employees only (not mgr/head)
            roles = [UserRole.employee]
        elif role:
            roles = [normalize_role(role)]
            if roles[0] not in ASSIGNABLE_ROLES:
                roles = EmployeeService._staff_roles()
        else:
            roles = EmployeeService._staff_roles()

        query = (
            db.query(User)
            .options(
                joinedload(User.reports_to_manager),
                joinedload(User.reports_to_sales_head),
            )
            .filter(User.role.in_(roles))
        )

        if is_active is not None:
            query = query.filter(User.is_active.is_(is_active))

        if search:
            pattern = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    User.name.ilike(pattern),
                    User.email.ilike(pattern),
                    User.employee_id.ilike(pattern),
                    User.phone.ilike(pattern),
                    User.department.ilike(pattern),
                    User.designation.ilike(pattern),
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
        user = EmployeeService._load_user(db, employee_id)
        if not user or user.role not in ASSIGNABLE_ROLES:
            raise ValueError("Employee not found.")
        return EmployeeService._to_response(db, user)

    @staticmethod
    def create(
        db: Session,
        payload: EmployeeCreate,
        actor_id: int | None = None,
    ) -> EmployeeResponse:
        if UserRepository.get_by_email(db, payload.email):
            raise ValueError("Email already exists.")

        role = normalize_role(payload.role or UserRole.employee)
        if role not in ASSIGNABLE_ROLES:
            raise ValueError(
                "role must be employee, accountant, processing_team, "
                "manager, or sales_head."
            )

        code = payload.employee_code
        if code and UserRepository.get_by_employee_id(db, code):
            raise ValueError("Employee ID already exists.")

        if not code:
            count = (
                db.query(func.count(User.id))
                .filter(User.role.in_(list(ASSIGNABLE_ROLES)))
                .scalar()
                or 0
            )
            code = f"EMP{count + 1:04d}"
            while UserRepository.get_by_employee_id(db, code):
                count += 1
                code = f"EMP{count + 1:04d}"

        monthly_target = (
            payload.monthly_target if role in SALES_ROLES else None
        )

        manager_id = None
        sales_head_id = None
        if role == UserRole.employee:
            manager_id = payload.reports_to_manager_id
            sales_head_id = payload.reports_to_sales_head_id
            EmployeeService._validate_supervisor(
                db, manager_id, UserRole.manager, "reportsToManagerId"
            )
            EmployeeService._validate_supervisor(
                db, sales_head_id, UserRole.sales_head, "reportsToSalesHeadId"
            )

        user = User(
            name=payload.name,
            email=str(payload.email).lower(),
            employee_id=code,
            phone=(payload.phone or None),
            department=(payload.department or None),
            designation=(payload.designation or None),
            password_hash=hash_password(payload.password),
            role=role,
            is_active=payload.is_active,
            monthly_sales_target=monthly_target,
            reports_to_manager_id=manager_id,
            reports_to_sales_head_id=sales_head_id,
        )

        try:
            db.add(user)
            db.commit()

        except IntegrityError as e:
            db.rollback()

            constraint = getattr(e.orig.diag, "constraint_name", "")
            messages = {
                "users_email_key": (409, "Email already exists."),
                "users_employee_id_key": (409, "Employee ID already exists."),
                "users_pkey": (
                    500,
                    "Internal database sequence error. Please contact the administrator.",
                ),
            }
            if constraint in messages:
                status, detail = messages[constraint]
                raise HTTPException(status_code=status, detail=detail) from e

            raise HTTPException(
                status_code=500,
                detail="Unable to create employee.",
            ) from e

        ActivityLogService.log(
            db,
            action="user_create",
            entity_type="user",
            entity_id=user.id,
            description=(
                f"User {user.employee_id} ({user.name}) created "
                f"with role {role.value}"
            ),
            user_id=actor_id,
            detail={
                "employeeId": user.employee_id,
                "name": user.name,
                "role": role.value,
                "email": user.email,
            },
        )

        return EmployeeService.get(db, user.id)

    @staticmethod
    def update(
        db: Session,
        employee_id: int,
        payload: EmployeeUpdate,
    ) -> EmployeeResponse:
        user = UserRepository.get_by_id(db, employee_id)
        if not user or user.role not in ASSIGNABLE_ROLES:
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

        if "phone" in data:
            user.phone = data["phone"] or None

        if "department" in data:
            user.department = data["department"] or None

        if "designation" in data:
            user.designation = data["designation"] or None

        if "password" in data and data["password"]:
            user.password_hash = hash_password(data["password"])

        if "is_active" in data and data["is_active"] is not None:
            user.is_active = data["is_active"]

        if "role" in data and data["role"] is not None:
            role = normalize_role(data["role"])
            if role not in ASSIGNABLE_ROLES:
                raise ValueError(
                    "role must be employee, accountant, processing_team, "
                    "manager, or sales_head."
                )
            user.role = role
            if role not in SALES_ROLES:
                user.monthly_sales_target = None
            if role != UserRole.employee:
                user.reports_to_manager_id = None
                user.reports_to_sales_head_id = None

        if data.get("clear_monthly_target"):
            user.monthly_sales_target = None
        elif "monthly_target" in data and data["monthly_target"] is not None:
            if user.role in SALES_ROLES:
                user.monthly_sales_target = data["monthly_target"]

        if user.role == UserRole.employee:
            if "reports_to_manager_id" in data:
                mid = data["reports_to_manager_id"]
                EmployeeService._validate_supervisor(
                    db, mid, UserRole.manager, "reportsToManagerId"
                )
                user.reports_to_manager_id = mid
            if "reports_to_sales_head_id" in data:
                sid = data["reports_to_sales_head_id"]
                EmployeeService._validate_supervisor(
                    db, sid, UserRole.sales_head, "reportsToSalesHeadId"
                )
                user.reports_to_sales_head_id = sid

        db.commit()
        return EmployeeService.get(db, user.id)

    @staticmethod
    def reset_password(db: Session, employee_id: int, new_password: str) -> None:
        user = UserRepository.get_by_id(db, employee_id)
        if not user or user.role not in ASSIGNABLE_ROLES:
            raise ValueError("Employee not found.")
        user.password_hash = hash_password(new_password)
        db.commit()

    @staticmethod
    def deactivate(db: Session, employee_id: int) -> None:
        user = UserRepository.get_by_id(db, employee_id)
        if not user or user.role not in ASSIGNABLE_ROLES:
            raise ValueError("Employee not found.")
        user.is_active = False
        db.commit()
