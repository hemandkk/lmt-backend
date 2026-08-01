from decimal import Decimal

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.db.models.user import User
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.permissions import require_admin
from app.schemas.master import (
    BranchCreate,
    BranchResponse,
    BranchUpdate,
    BulkEmployeeMonthlyTargetRequest,
    BulkEmployeeMonthlyTargetResponse,
    CourseCreate,
    CourseResponse,
    CourseUpdate,
    DefaultSalesTargetResponse,
    DefaultSalesTargetUpdate,
    DepartmentCreate,
    DepartmentResponse,
    DepartmentUpdate,
    DesignationCreate,
    DesignationResponse,
    DesignationUpdate,
    EmployeeSalesTargetAssign,
    EmployeeSalesTargetItem,
    IncentiveSlabCreate,
    IncentiveSlabResponse,
    IncentiveSlabUpdate,
    MasterImportResponse,
    SalesTargetOverviewResponse,
    SpecializationCreate,
    SpecializationResponse,
    SpecializationUpdate,
    StateCreate,
    StateResponse,
    StateUpdate,
    UpdateIncentiveSlabsRequest,
)
from app.services.master_service import MasterService

router = APIRouter(
    prefix="/masters",
    tags=["Masters"],
)


# ==========================================================
# Courses — all authenticated users can read;
# create/update/delete/import are admin-only
# ==========================================================

@router.get(
    "/courses",
    response_model=list[CourseResponse],
)
def get_courses(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return MasterService.get_courses(db)


@router.post(
    "/courses",
    response_model=CourseResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_course(
    payload: CourseCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    try:
        return MasterService.create_course(db, payload)
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex


@router.post(
    "/courses/import",
    response_model=MasterImportResponse,
)
async def import_courses(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """
    Import courses from CSV or Excel (.xlsx).
    Headers (case-insensitive): name (required), courseCode, specialization,
    duration, fees, description, active.
    Existing names are updated; new names are created.
    """
    try:
        return await MasterService.import_courses(db, file)
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex


@router.put(
    "/courses/{course_id}",
    response_model=CourseResponse,
)
def update_course(
    course_id: int,
    payload: CourseUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    try:
        return MasterService.update_course(db, course_id, payload)
    except ValueError as ex:
        detail = str(ex)
        code = 404 if detail == "Course not found." else 400
        raise HTTPException(status_code=code, detail=detail) from ex


@router.delete("/courses/{course_id}")
def delete_course(
    course_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    try:
        MasterService.delete_course(db, course_id)
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex)) from ex
    return {"message": "Course deleted."}


# ==========================================================
# Specializations — lead dropdown master (not FK-linked).
# Read: all authenticated; write/import: admin.
# ==========================================================

@router.get(
    "/specializations",
    response_model=list[SpecializationResponse],
)
def get_specializations(
    active_only: bool = Query(False, alias="activeOnly"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return MasterService.get_specializations(db, active_only=active_only)


@router.post(
    "/specializations",
    response_model=SpecializationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_specialization(
    payload: SpecializationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    try:
        return MasterService.create_specialization(db, payload)
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex


@router.post(
    "/specializations/import",
    response_model=MasterImportResponse,
)
async def import_specializations(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """
    Import specializations from CSV or Excel (.xlsx).
    Headers (case-insensitive): name (required), specializationCode,
    description, active.
    Existing names are updated; new names are created.
    """
    try:
        return await MasterService.import_specializations(db, file)
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex


@router.put(
    "/specializations/{specialization_id}",
    response_model=SpecializationResponse,
)
def update_specialization(
    specialization_id: int,
    payload: SpecializationUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    try:
        return MasterService.update_specialization(
            db, specialization_id, payload
        )
    except ValueError as ex:
        detail = str(ex)
        code = 404 if detail == "Specialization not found." else 400
        raise HTTPException(status_code=code, detail=detail) from ex


@router.delete("/specializations/{specialization_id}")
def delete_specialization(
    specialization_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    try:
        MasterService.delete_specialization(db, specialization_id)
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex)) from ex
    return {"message": "Specialization deleted."}


# ==========================================================
# Designations — employee dropdown master.
# Read: all authenticated; write: admin.
# ==========================================================

@router.get(
    "/designations",
    response_model=list[DesignationResponse],
)
def get_designations(
    active_only: bool = Query(False, alias="activeOnly"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return MasterService.get_designations(db, active_only=active_only)


@router.post(
    "/designations",
    response_model=DesignationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_designation(
    payload: DesignationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    try:
        return MasterService.create_designation(db, payload)
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex


@router.put(
    "/designations/{designation_id}",
    response_model=DesignationResponse,
)
def update_designation(
    designation_id: int,
    payload: DesignationUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    try:
        return MasterService.update_designation(db, designation_id, payload)
    except ValueError as ex:
        detail = str(ex)
        code = 404 if detail == "Designation not found." else 400
        raise HTTPException(status_code=code, detail=detail) from ex


@router.delete("/designations/{designation_id}")
def delete_designation(
    designation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    try:
        MasterService.delete_designation(db, designation_id)
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex)) from ex
    return {"message": "Designation deleted."}


# ==========================================================
# Departments — employee dropdown master.
# Read: all authenticated; write: admin.
# ==========================================================

@router.get(
    "/departments",
    response_model=list[DepartmentResponse],
)
def get_departments(
    active_only: bool = Query(False, alias="activeOnly"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return MasterService.get_departments(db, active_only=active_only)


@router.post(
    "/departments",
    response_model=DepartmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_department(
    payload: DepartmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    try:
        return MasterService.create_department(db, payload)
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex


@router.put(
    "/departments/{department_id}",
    response_model=DepartmentResponse,
)
def update_department(
    department_id: int,
    payload: DepartmentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    try:
        return MasterService.update_department(db, department_id, payload)
    except ValueError as ex:
        detail = str(ex)
        code = 404 if detail == "Department not found." else 400
        raise HTTPException(status_code=code, detail=detail) from ex


@router.delete("/departments/{department_id}")
def delete_department(
    department_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    try:
        MasterService.delete_department(db, department_id)
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex)) from ex
    return {"message": "Department deleted."}


# ==========================================================
# States — read: all authenticated; write: admin
# ==========================================================

@router.get("/states", response_model=list[StateResponse])
def get_states(
    active_only: bool = Query(False, alias="activeOnly"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return MasterService.get_states(db, active_only=active_only)


@router.post(
    "/states",
    response_model=StateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_state(
    payload: StateCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    try:
        return MasterService.create_state(db, payload)
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex


@router.put("/states/{state_id}", response_model=StateResponse)
def update_state(
    state_id: int,
    payload: StateUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    try:
        return MasterService.update_state(db, state_id, payload)
    except ValueError as ex:
        detail = str(ex)
        code = 404 if detail == "State not found." else 400
        raise HTTPException(status_code=code, detail=detail) from ex


@router.delete("/states/{state_id}")
def delete_state(
    state_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    try:
        MasterService.delete_state(db, state_id)
    except ValueError as ex:
        detail = str(ex)
        code = 404 if detail == "State not found." else 400
        raise HTTPException(status_code=code, detail=detail) from ex
    return {"message": "State deleted."}


# ==========================================================
# Branches — read: all authenticated; write: admin
# ==========================================================

@router.get("/branches", response_model=list[BranchResponse])
def get_branches(
    active_only: bool = Query(False, alias="activeOnly"),
    state_id: int | None = Query(None, alias="stateId"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return MasterService.get_branches(
        db, active_only=active_only, state_id=state_id
    )


@router.post(
    "/branches",
    response_model=BranchResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_branch(
    payload: BranchCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    try:
        return MasterService.create_branch(db, payload)
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex


@router.put("/branches/{branch_id}", response_model=BranchResponse)
def update_branch(
    branch_id: int,
    payload: BranchUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    try:
        return MasterService.update_branch(db, branch_id, payload)
    except ValueError as ex:
        detail = str(ex)
        code = 404 if detail == "Branch not found." else 400
        raise HTTPException(status_code=code, detail=detail) from ex


@router.delete("/branches/{branch_id}")
def delete_branch(
    branch_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    try:
        MasterService.delete_branch(db, branch_id)
    except ValueError as ex:
        detail = str(ex)
        code = 404 if detail == "Branch not found." else 400
        raise HTTPException(status_code=code, detail=detail) from ex
    return {"message": "Branch deleted."}


# ==========================================================
# Incentive slabs — read: all; CRUD: admin
# ==========================================================

@router.get(
    "/incentive-slabs",
    response_model=list[IncentiveSlabResponse],
)
def get_incentive_slabs(
    include_inactive: bool = Query(False, alias="includeInactive"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return MasterService.get_incentive_slabs(
        db, include_inactive=include_inactive
    )


@router.get(
    "/incentive-slabs/{slab_id}",
    response_model=IncentiveSlabResponse,
)
def get_incentive_slab(
    slab_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return MasterService.get_incentive_slab(db, slab_id)
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex)) from ex


@router.post(
    "/incentive-slabs",
    response_model=IncentiveSlabResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_incentive_slab(
    payload: IncentiveSlabCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    return MasterService.create_incentive_slab(db, payload)


@router.put(
    "/incentive-slabs/{slab_id}",
    response_model=IncentiveSlabResponse,
)
def update_incentive_slab(
    slab_id: int,
    payload: IncentiveSlabUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    try:
        return MasterService.update_incentive_slab(db, slab_id, payload)
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex


@router.delete(
    "/incentive-slabs/{slab_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_incentive_slab(
    slab_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    try:
        MasterService.delete_incentive_slab(db, slab_id)
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex)) from ex


@router.put(
    "/incentive-slabs",
    response_model=list[IncentiveSlabResponse],
)
def replace_incentive_slabs(
    payload: UpdateIncentiveSlabsRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Bulk replace all slabs (admin)."""
    return MasterService.update_incentive_slabs(db, payload)


# ==========================================================
# Sales targets — master default + optional employee assign
# ==========================================================

@router.get(
    "/sales-targets",
    response_model=SalesTargetOverviewResponse,
)
def get_sales_targets(
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """
    Master default monthly target + each employee's assigned/effective target.
    """
    return MasterService.get_sales_target_overview(db)


@router.get(
    "/sales-targets/default",
    response_model=DefaultSalesTargetResponse,
)
def get_default_sales_target(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return MasterService.get_default_sales_target(db)


@router.put(
    "/sales-targets/default",
    response_model=DefaultSalesTargetResponse,
)
def set_default_sales_target(
    payload: DefaultSalesTargetUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Set org-wide default monthly target (used when employee has none)."""
    return MasterService.set_default_sales_target(
        db, payload.default_monthly_target
    )


@router.put(
    "/sales-targets/employees/{employee_id}",
    response_model=EmployeeSalesTargetItem,
)
def assign_employee_sales_target(
    employee_id: int,
    payload: EmployeeSalesTargetAssign,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Assign a custom monthly target to an employee."""
    try:
        return MasterService.assign_employee_sales_target(
            db, employee_id, payload
        )
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex)) from ex


@router.delete(
    "/sales-targets/employees/{employee_id}",
    response_model=EmployeeSalesTargetItem,
)
def clear_employee_sales_target(
    employee_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """
    Clear employee assignment so master default applies
    (fresh joiners / unassigned case).
    """
    try:
        return MasterService.clear_employee_sales_target(db, employee_id)
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex)) from ex


# ==========================================================
# Monthly targets CRUD (preferred aliases)
# Master default + per-employee override
# Fallback: if employee has no target → master default
# ==========================================================

@router.get(
    "/monthly-targets",
    response_model=SalesTargetOverviewResponse,
)
def list_monthly_targets(
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """List master default + every employee's assigned/effective target."""
    return MasterService.get_sales_target_overview(db)


@router.get(
    "/monthly-targets/default",
    response_model=DefaultSalesTargetResponse,
)
def get_monthly_target_default(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return MasterService.get_default_sales_target(db)


@router.post(
    "/monthly-targets/default",
    response_model=DefaultSalesTargetResponse,
    status_code=status.HTTP_201_CREATED,
)
@router.put(
    "/monthly-targets/default",
    response_model=DefaultSalesTargetResponse,
)
def upsert_monthly_target_default(
    payload: DefaultSalesTargetUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Create/update org-wide master monthly target."""
    return MasterService.set_default_sales_target(
        db, payload.default_monthly_target
    )


@router.get(
    "/monthly-targets/employees/{employee_id}",
    response_model=EmployeeSalesTargetItem,
)
def get_employee_monthly_target(
    employee_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    try:
        return MasterService.get_employee_sales_target(db, employee_id)
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex)) from ex


@router.post(
    "/monthly-targets/employees/{employee_id}",
    response_model=EmployeeSalesTargetItem,
    status_code=status.HTTP_201_CREATED,
)
@router.put(
    "/monthly-targets/employees/{employee_id}",
    response_model=EmployeeSalesTargetItem,
)
@router.patch(
    "/monthly-targets/employees/{employee_id}",
    response_model=EmployeeSalesTargetItem,
)
def set_employee_monthly_target(
    employee_id: int,
    payload: EmployeeSalesTargetAssign,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Assign/update a custom monthly target for one employee."""
    try:
        return MasterService.assign_employee_sales_target(
            db, employee_id, payload
        )
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex)) from ex


@router.delete(
    "/monthly-targets/employees/{employee_id}",
    response_model=EmployeeSalesTargetItem,
)
def delete_employee_monthly_target(
    employee_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Clear employee target so master default is used for calculations."""
    try:
        return MasterService.clear_employee_sales_target(db, employee_id)
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex)) from ex


@router.put(
    "/monthly-targets/employees",
    response_model=BulkEmployeeMonthlyTargetResponse,
)
def bulk_set_employee_monthly_targets(
    payload: BulkEmployeeMonthlyTargetRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """
    Bulk assign/clear employee targets.
    Pass monthlyTarget: null to clear (use master default).
    """
    try:
        return MasterService.bulk_assign_employee_sales_targets(db, payload)
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex)) from ex
