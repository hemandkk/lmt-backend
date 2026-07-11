from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)

from sqlalchemy.orm import Session

from app.db.session import get_db

from app.schemas.prospect import (
    ProspectCreate,
    ProspectUpdate,
    ProspectResponse,
    ProspectListResponse,
)
from app.db.models.prospect import Prospect

from app.services.prospect_service import ProspectService
from app.core.id_generator import generate_next_code
router = APIRouter(
    prefix="/prospects",
    tags=["Prospects"],
)



# --------------------------------------------------------
# Next Prospects ID
# --------------------------------------------------------
@router.get("/utility/next-prospect-id")
def get_next_prospect_id(db: Session = Depends(get_db)):
    prospect_id = generate_next_code(
                    db=db,
                    model=Prospect,
                    field="prospect_id",
                    prefix="PSP",
                )
    print("prospect_id")
    print(prospect_id)
    return {
        "next_id": prospect_id
    }


# --------------------------------------------------------
# List Prospects
# --------------------------------------------------------

@router.get(
    "",
    response_model=ProspectListResponse,
)
def list_prospects(
    page: int = Query(1, ge=1),
    page_size: int = Query(
        20,
        alias="pageSize",
        ge=1,
        le=100,
    ),
    search: str | None = None,
    stage: str | None = None,
    db: Session = Depends(get_db),
):

    return ProspectService.list(
        db,
        page,
        page_size,
        search,
        stage,
    )


# --------------------------------------------------------
# Get Prospect
# --------------------------------------------------------

@router.get(
    "/{prospect_id}",
    response_model=ProspectResponse,
)
def get_prospect(
    prospect_id: int,
    db: Session = Depends(get_db),
):

    try:

        return ProspectService.get(
            db,
            prospect_id,
        )

    except ValueError as ex:

        raise HTTPException(
            status_code=404,
            detail=str(ex),
        )


# --------------------------------------------------------
# Create Prospect
# --------------------------------------------------------

@router.post(
    "",
    response_model=ProspectResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_prospect(
    payload: ProspectCreate,
    db: Session = Depends(get_db),
):

    try:

        return ProspectService.create(
            db,
            payload,
        )

    except ValueError as ex:

        raise HTTPException(
            status_code=400,
            detail=str(ex),
        )


# --------------------------------------------------------
# Update Prospect
# --------------------------------------------------------

@router.put(
    "/{prospect_id}",
    response_model=ProspectResponse,
)
def update_prospect(
    prospect_id: int,
    payload: ProspectUpdate,
    db: Session = Depends(get_db),
):

    try:

        return ProspectService.update(
            db,
            prospect_id,
            payload,
        )

    except ValueError as ex:

        raise HTTPException(
            status_code=404,
            detail=str(ex),
        )


# --------------------------------------------------------
# Delete Prospect
# --------------------------------------------------------

@router.delete(
    "/{prospect_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_prospect(
    prospect_id: int,
    db: Session = Depends(get_db),
):

    try:

        ProspectService.delete(
            db,
            prospect_id,
        )

    except ValueError as ex:

        raise HTTPException(
            status_code=404,
            detail=str(ex),
        )


# --------------------------------------------------------
# Change Stage
# --------------------------------------------------------

@router.patch(
    "/{prospect_id}/stage",
    response_model=ProspectResponse,
)
def update_stage(
    prospect_id: int,
    stage: str,
    db: Session = Depends(get_db),
):

    try:

        return ProspectService.change_stage(
            db,
            prospect_id,
            stage,
        )

    except ValueError as ex:

        raise HTTPException(
            status_code=404,
            detail=str(ex),
        )


# --------------------------------------------------------
# Update Exam
# --------------------------------------------------------

@router.patch(
    "/{prospect_id}/exam",
    response_model=ProspectResponse,
)
def update_exam(
    prospect_id: int,
    attended: bool,
    certified: bool,
    db: Session = Depends(get_db),
):

    try:

        return ProspectService.update_exam(
            db,
            prospect_id,
            attended,
            certified,
        )

    except ValueError as ex:

        raise HTTPException(
            status_code=404,
            detail=str(ex),
        )