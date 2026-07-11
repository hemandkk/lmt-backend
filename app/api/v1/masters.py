from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.models.user import User
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.permissions import require_admin
from app.schemas.master import (
    CourseCreate,
    CourseResponse,
    DefaultSalesTargetResponse,
    DefaultSalesTargetUpdate,
    EmployeeSalesTargetAssign,
    EmployeeSalesTargetItem,
    IncentiveSlabCreate,
    IncentiveSlabResponse,
    IncentiveSlabUpdate,
    SalesTargetOverviewResponse,
    UpdateIncentiveSlabsRequest,
)
from app.services.master_service import MasterService

router = APIRouter(
    prefix="/masters",
    tags=["Masters"],
)


# ==========================================================
# Courses — all authenticated users can read;
# create/delete are admin-only
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
