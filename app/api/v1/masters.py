from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import (
    get_current_user,
)
from app.schemas.master import (
    CourseCreate,
    CourseResponse,
    IncentiveSlabResponse,
    UpdateIncentiveSlabsRequest,
)
from app.services.master_service import (
    MasterService,
)

router = APIRouter(
    prefix="/masters",
    tags=["Masters"],
)


# ==========================================================
# Courses
# ==========================================================

@router.get(
    "/courses",
    response_model=list[CourseResponse],
)
def get_courses(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):

    return MasterService.get_courses(db)


@router.post(
    "/courses",
    response_model=CourseResponse,
)
def create_course(
    payload: CourseCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):

    try:
        return MasterService.create_course(
            db,
            payload,
        )

    except ValueError as ex:

        raise HTTPException(
            status_code=400,
            detail=str(ex),
        )


@router.delete(
    "/courses/{course_id}",
)
def delete_course(
    course_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):

    MasterService.delete_course(
        db,
        course_id,
    )

    return {
        "message": "Course deleted."
    }


# ==========================================================
# Incentive Slabs
# ==========================================================

@router.get(
    "/incentive-slabs",
    response_model=list[
        IncentiveSlabResponse
    ],
)
def get_incentive_slabs(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):

    return MasterService.get_incentive_slabs(
        db,
    )


@router.put(
    "/incentive-slabs",
    response_model=list[
        IncentiveSlabResponse
    ],
)
def update_incentive_slabs(
    payload: UpdateIncentiveSlabsRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):

    return MasterService.update_incentive_slabs(
        db,
        payload,
    )