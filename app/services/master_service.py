from decimal import Decimal

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.id_generator import generate_next_code
from app.db.models.course import Course
from app.db.models.incentive_slab import IncentiveSlab
from app.db.models.specialization import Specialization
from app.db.models.user import User, UserRole
from app.repositories.course_repository import CourseRepository
from app.repositories.incentive_repository import IncentiveRepository
from app.repositories.settings_repository import SettingsRepository
from app.repositories.specialization_repository import SpecializationRepository
from app.schemas.master import (
    BulkEmployeeMonthlyTargetRequest,
    BulkEmployeeMonthlyTargetResponse,
    CourseCreate,
    CourseUpdate,
    DefaultSalesTargetResponse,
    EmployeeSalesTargetAssign,
    EmployeeSalesTargetItem,
    IncentiveSlabCreate,
    IncentiveSlabUpdate,
    MasterImportResponse,
    SalesTargetOverviewResponse,
    SpecializationCreate,
    SpecializationUpdate,
    UpdateIncentiveSlabsRequest,
)
from app.services.master_import import (
    map_course_row,
    map_specialization_row,
    read_tabular_rows,
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
    def update_course(db: Session, course_id: int, payload: CourseUpdate):
        course = CourseRepository.get_by_id(db, course_id)
        if not course:
            raise ValueError("Course not found.")

        data = payload.model_dump(exclude_unset=True)
        if "name" in data and data["name"]:
            existing = CourseRepository.get_by_name(db, data["name"])
            if existing and existing.id != course.id:
                raise ValueError("Course already exists.")
        if "course_code" in data and data["course_code"]:
            existing_code = (
                db.query(Course)
                .filter(Course.course_code == data["course_code"])
                .first()
            )
            if existing_code and existing_code.id != course.id:
                raise ValueError(
                    f"Course code {data['course_code']} already exists."
                )

        for key, value in data.items():
            setattr(course, key, value)
        return CourseRepository.update(db, course)

    @staticmethod
    def delete_course(db: Session, course_id: int):
        course = CourseRepository.get_by_id(db, course_id)
        if not course:
            raise ValueError("Course not found.")
        CourseRepository.delete(db, course)

    @staticmethod
    async def import_courses(
        db: Session, file: UploadFile
    ) -> MasterImportResponse:
        rows = await read_tabular_rows(file)
        created = updated = skipped = 0
        errors: list[str] = []

        for index, raw in enumerate(rows, start=2):
            try:
                data = map_course_row(raw)
            except ValueError as exc:
                errors.append(f"Row {index}: {exc}")
                skipped += 1
                continue

            existing = CourseRepository.get_by_name(db, data["name"])
            if existing:
                for key, value in data.items():
                    if key == "course_code" and not value:
                        continue
                    if value is not None:
                        setattr(existing, key, value)
                CourseRepository.update(db, existing)
                updated += 1
                continue

            course_code = data["course_code"] or generate_next_code(
                db, Course, "course_code", "CRS"
            )
            if (
                db.query(Course)
                .filter(Course.course_code == course_code)
                .first()
            ):
                errors.append(
                    f"Row {index}: Course code {course_code} already exists."
                )
                skipped += 1
                continue

            CourseRepository.create(
                db,
                Course(
                    course_code=course_code,
                    name=data["name"],
                    specialization=data.get("specialization"),
                    duration=data.get("duration"),
                    fees=data.get("fees"),
                    description=data.get("description"),
                    is_active=data.get("is_active", True),
                ),
            )
            created += 1

        return MasterImportResponse(
            created=created,
            updated=updated,
            skipped=skipped,
            errors=errors,
        )

    # --------------------------------------------------
    # Specializations
    # --------------------------------------------------

    @staticmethod
    def get_specializations(db: Session, *, active_only: bool = False):
        return SpecializationRepository.get_all(db, active_only=active_only)

    @staticmethod
    def create_specialization(db: Session, payload: SpecializationCreate):
        existing = SpecializationRepository.get_by_name(db, payload.name)
        if existing:
            raise ValueError("Specialization already exists.")

        code = payload.specialization_code or generate_next_code(
            db, Specialization, "specialization_code", "SPC"
        )
        if SpecializationRepository.get_by_code(db, code):
            raise ValueError(f"Specialization code {code} already exists.")

        specialization = Specialization(
            specialization_code=code,
            name=payload.name,
            description=payload.description,
            is_active=payload.is_active,
        )
        return SpecializationRepository.create(db, specialization)

    @staticmethod
    def update_specialization(
        db: Session,
        specialization_id: int,
        payload: SpecializationUpdate,
    ):
        specialization = SpecializationRepository.get_by_id(
            db, specialization_id
        )
        if not specialization:
            raise ValueError("Specialization not found.")

        data = payload.model_dump(exclude_unset=True)
        if "name" in data and data["name"]:
            existing = SpecializationRepository.get_by_name(db, data["name"])
            if existing and existing.id != specialization.id:
                raise ValueError("Specialization already exists.")
        if "specialization_code" in data and data["specialization_code"]:
            existing_code = SpecializationRepository.get_by_code(
                db, data["specialization_code"]
            )
            if existing_code and existing_code.id != specialization.id:
                raise ValueError(
                    f"Specialization code {data['specialization_code']} "
                    "already exists."
                )

        for key, value in data.items():
            setattr(specialization, key, value)
        return SpecializationRepository.update(db, specialization)

    @staticmethod
    def delete_specialization(db: Session, specialization_id: int):
        specialization = SpecializationRepository.get_by_id(
            db, specialization_id
        )
        if not specialization:
            raise ValueError("Specialization not found.")
        SpecializationRepository.delete(db, specialization)

    @staticmethod
    async def import_specializations(
        db: Session, file: UploadFile
    ) -> MasterImportResponse:
        rows = await read_tabular_rows(file)
        created = updated = skipped = 0
        errors: list[str] = []

        for index, raw in enumerate(rows, start=2):
            try:
                data = map_specialization_row(raw)
            except ValueError as exc:
                errors.append(f"Row {index}: {exc}")
                skipped += 1
                continue

            existing = SpecializationRepository.get_by_name(db, data["name"])
            if existing:
                for key, value in data.items():
                    if key == "specialization_code" and not value:
                        continue
                    if value is not None:
                        setattr(existing, key, value)
                SpecializationRepository.update(db, existing)
                updated += 1
                continue

            code = data["specialization_code"] or generate_next_code(
                db, Specialization, "specialization_code", "SPC"
            )
            if SpecializationRepository.get_by_code(db, code):
                errors.append(
                    f"Row {index}: Specialization code {code} already exists."
                )
                skipped += 1
                continue

            SpecializationRepository.create(
                db,
                Specialization(
                    specialization_code=code,
                    name=data["name"],
                    description=data.get("description"),
                    is_active=data.get("is_active", True),
                ),
            )
            created += 1

        return MasterImportResponse(
            created=created,
            updated=updated,
            skipped=skipped,
            errors=errors,
        )

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
