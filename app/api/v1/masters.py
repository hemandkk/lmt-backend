from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from sqlalchemy.orm import Session

from app.db.models.user import User
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.permissions import require_admin
from app.schemas.master import (
    CourseCreate,
    CourseResponse,
    IncentiveSlabResponse,
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
        raise HTTPException(status_code=400, detail=str(ex))


@router.delete("/courses/{course_id}")
def delete_course(
    course_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    try:
        MasterService.delete_course(db, course_id)
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex))
    return {"message": "Course deleted."}


# ==========================================================
# Incentive slabs — all can read; only admin can update
# ==========================================================

@router.get(
    "/incentive-slabs",
    response_model=list[IncentiveSlabResponse],
)
def get_incentive_slabs(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return MasterService.get_incentive_slabs(db)


@router.put(
    "/incentive-slabs",
    response_model=list[IncentiveSlabResponse],
)
def update_incentive_slabs(
    payload: UpdateIncentiveSlabsRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    return MasterService.update_incentive_slabs(db, payload)
