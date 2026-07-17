from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.id_generator import generate_next_code
from app.db.models.course import Course
from app.db.models.incentive_slab import IncentiveSlab
from app.db.models.user import User, UserRole
from app.repositories.course_repository import CourseRepository
from app.repositories.incentive_repository import IncentiveRepository
from app.repositories.settings_repository import SettingsRepository
from app.schemas.master import (
    BulkEmployeeMonthlyTargetRequest,
    BulkEmployeeMonthlyTargetResponse,
    CourseCreate,
    DefaultSalesTargetResponse,
    EmployeeSalesTargetAssign,
    EmployeeSalesTargetItem,
    IncentiveSlabCreate,
    IncentiveSlabUpdate,
    SalesTargetOverviewResponse,
    UpdateIncentiveSlabsRequest,
)


def resolve_employee_monthly_target(
    db: Session,
    user: User | None,
) -> tuple[Decimal, bool, str]:
    """
    Returns (effective_target, target_assigned, target_source).
    Assigned employee target wins; otherwise master default.
    """
    default_target = SettingsRepository.get_default_monthly_sales_target(db)
    if user is not None and user.monthly_sales_target is not None:
        return (
            Decimal(str(user.monthly_sales_target)),
            True,
            "assigned",
        )
    return default_target, False, "default"


class MasterService:

    @staticmethod
    def get_courses(db: Session):
        return CourseRepository.get_all(db)

    @staticmethod
    def create_course(db: Session, payload: CourseCreate):
        existing = CourseRepository.get_by_name(db, payload.name)
        if existing:
            raise ValueError("Course already exists.")

        course_code = payload.course_code or generate_next_code(
            db, Course, "course_code", "CRS"
        )

        existing_code = (
            db.query(Course)
            .filter(Course.course_code == course_code)
            .first()
        )
        if existing_code:
            raise ValueError(f"Course code {course_code} already exists.")

        course = Course(
            course_code=course_code,
            name=payload.name,
            specialization=payload.specialization,
            duration=payload.duration,
            fees=payload.fees,
            description=payload.description,
            is_active=payload.is_active,
        )

        return CourseRepository.create(db, course)

    @staticmethod
    def delete_course(db: Session, course_id: int):
        course = CourseRepository.get_by_id(db, course_id)
        if not course:
            raise ValueError("Course not found.")
        CourseRepository.delete(db, course)

    # --------------------------------------------------
    # Incentive slabs
    # --------------------------------------------------

    @staticmethod
    def get_incentive_slabs(db: Session, include_inactive: bool = False):
        return IncentiveRepository.get_all(
            db, include_inactive=include_inactive
        )

    @staticmethod
    def get_incentive_slab(db: Session, slab_id: int) -> IncentiveSlab:
        slab = IncentiveRepository.get_by_id(db, slab_id)
        if not slab:
            raise ValueError("Incentive slab not found.")
        return slab

    @staticmethod
    def create_incentive_slab(
        db: Session, payload: IncentiveSlabCreate
    ) -> IncentiveSlab:
        slab = IncentiveSlab(
            min_leads=payload.min_leads,
            max_leads=payload.max_leads,
            incentive_amount=payload.incentive_amount,
            is_active=payload.is_active,
        )
        return IncentiveRepository.create(db, slab)

    @staticmethod
    def update_incentive_slab(
        db: Session,
        slab_id: int,
        payload: IncentiveSlabUpdate,
    ) -> IncentiveSlab:
        slab = MasterService.get_incentive_slab(db, slab_id)
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(slab, key, value)
        if (
            slab.max_leads is not None
            and slab.min_leads is not None
            and slab.max_leads < slab.min_leads
        ):
            raise ValueError("maxLeads must be >= minLeads")
        return IncentiveRepository.update(db, slab)

    @staticmethod
    def delete_incentive_slab(db: Session, slab_id: int) -> None:
        slab = MasterService.get_incentive_slab(db, slab_id)
        IncentiveRepository.delete(db, slab)

    @staticmethod
    def update_incentive_slabs(
        db: Session,
        payload: UpdateIncentiveSlabsRequest,
    ):
        IncentiveRepository.delete_all(db)

        slabs = []
        for item in payload.slabs:
            slab = IncentiveSlab(
                min_leads=item.min_leads,
                max_leads=item.max_leads,
                incentive_amount=item.incentive_amount,
                is_active=item.is_active,
            )
            slabs.append(IncentiveRepository.create(db, slab))

        return slabs

    # --------------------------------------------------
    # Sales targets
    # --------------------------------------------------

    @staticmethod
    def get_sales_target_overview(db: Session) -> SalesTargetOverviewResponse:
        default_target = SettingsRepository.get_default_monthly_sales_target(db)
        employees = (
            db.query(User)
            .filter(User.role == UserRole.employee, User.is_active.is_(True))
            .order_by(User.name.asc())
            .all()
        )
        items: list[EmployeeSalesTargetItem] = []
        for user in employees:
            effective, assigned, source = resolve_employee_monthly_target(
                db, user
            )
            items.append(
                EmployeeSalesTargetItem(
                    employee_id=user.id,
                    employee_code=user.employee_id,
                    employee_name=user.name or "Unknown",
                    assigned_target=(
                        Decimal(str(user.monthly_sales_target))
                        if user.monthly_sales_target is not None
                        else None
                    ),
                    effective_target=effective,
                    target_assigned=assigned,
                    target_source=source,
                )
            )
        return SalesTargetOverviewResponse(
            default_monthly_target=default_target,
            employees=items,
        )

    @staticmethod
    def get_default_sales_target(db: Session) -> DefaultSalesTargetResponse:
        return DefaultSalesTargetResponse(
            default_monthly_target=SettingsRepository.get_default_monthly_sales_target(
                db
            )
        )

    @staticmethod
    def set_default_sales_target(
        db: Session, amount: Decimal
    ) -> DefaultSalesTargetResponse:
        value = SettingsRepository.set_default_monthly_sales_target(db, amount)
        return DefaultSalesTargetResponse(default_monthly_target=value)

    @staticmethod
    def assign_employee_sales_target(
        db: Session,
        employee_id: int,
        payload: EmployeeSalesTargetAssign,
    ) -> EmployeeSalesTargetItem:
        user = (
            db.query(User)
            .filter(
                User.id == employee_id,
                User.role == UserRole.employee,
            )
            .first()
        )
        if not user:
            raise ValueError("Employee not found.")

        user.monthly_sales_target = payload.monthly_target
        db.commit()
        db.refresh(user)

        effective, assigned, source = resolve_employee_monthly_target(db, user)
        return EmployeeSalesTargetItem(
            employee_id=user.id,
            employee_code=user.employee_id,
            employee_name=user.name or "Unknown",
            assigned_target=Decimal(str(user.monthly_sales_target)),
            effective_target=effective,
            target_assigned=assigned,
            target_source=source,
        )

    @staticmethod
    def clear_employee_sales_target(
        db: Session, employee_id: int
    ) -> EmployeeSalesTargetItem:
        """Remove assignment so master default applies (fresh joiner case)."""
        user = (
            db.query(User)
            .filter(
                User.id == employee_id,
                User.role == UserRole.employee,
            )
            .first()
        )
        if not user:
            raise ValueError("Employee not found.")

        user.monthly_sales_target = None
        db.commit()
        db.refresh(user)

        effective, assigned, source = resolve_employee_monthly_target(db, user)
        return EmployeeSalesTargetItem(
            employee_id=user.id,
            employee_code=user.employee_id,
            employee_name=user.name or "Unknown",
            assigned_target=None,
            effective_target=effective,
            target_assigned=assigned,
            target_source=source,
        )

    @staticmethod
    def get_employee_sales_target(
        db: Session, employee_id: int
    ) -> EmployeeSalesTargetItem:
        user = (
            db.query(User)
            .filter(
                User.id == employee_id,
                User.role == UserRole.employee,
            )
            .first()
        )
        if not user:
            raise ValueError("Employee not found.")

        effective, assigned, source = resolve_employee_monthly_target(db, user)
        return EmployeeSalesTargetItem(
            employee_id=user.id,
            employee_code=user.employee_id,
            employee_name=user.name or "Unknown",
            assigned_target=(
                Decimal(str(user.monthly_sales_target))
                if user.monthly_sales_target is not None
                else None
            ),
            effective_target=effective,
            target_assigned=assigned,
            target_source=source,
        )

    @staticmethod
    def bulk_assign_employee_sales_targets(
        db: Session,
        payload: BulkEmployeeMonthlyTargetRequest,
    ) -> BulkEmployeeMonthlyTargetResponse:
        results: list[EmployeeSalesTargetItem] = []
        for item in payload.items:
            user = (
                db.query(User)
                .filter(
                    User.id == item.employee_id,
                    User.role == UserRole.employee,
                )
                .first()
            )
            if not user:
                raise ValueError(f"Employee not found: {item.employee_id}")

            if item.monthly_target is None:
                user.monthly_sales_target = None
            else:
                user.monthly_sales_target = item.monthly_target

        db.commit()

        for item in payload.items:
            user = (
                db.query(User)
                .filter(User.id == item.employee_id)
                .first()
            )
            if not user:
                continue
            effective, assigned, source = resolve_employee_monthly_target(
                db, user
            )
            results.append(
                EmployeeSalesTargetItem(
                    employee_id=user.id,
                    employee_code=user.employee_id,
                    employee_name=user.name or "Unknown",
                    assigned_target=(
                        Decimal(str(user.monthly_sales_target))
                        if user.monthly_sales_target is not None
                        else None
                    ),
                    effective_target=effective,
                    target_assigned=assigned,
                    target_source=source,
                )
            )

        return BulkEmployeeMonthlyTargetResponse(
            default_monthly_target=SettingsRepository.get_default_monthly_sales_target(
                db
            ),
            employees=results,
        )
