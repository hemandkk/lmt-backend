from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy.orm import Session

from app.core.id_generator import generate_next_code
from app.db.models.prospect import Prospect
from app.db.models.user import User
from app.db.session import get_db
from app.dependencies.auth import get_optional_user
from app.schemas.prospect import (
    ProspectCreate,
    ProspectListResponse,
    ProspectResponse,
    ProspectUpdate,
)
from app.services.prospect_service import ProspectService

router = APIRouter(
    prefix="/prospects",
    tags=["Prospects"],
)


@router.get("/utility/next-prospect-id")
def get_next_prospect_id(db: Session = Depends(get_db)):
    prospect_id = generate_next_code(
        db=db,
        model=Prospect,
        field="prospect_id",
        prefix="PSP",
    )
    return {"next_id": prospect_id}


@router.get("", response_model=ProspectListResponse)
def list_prospects(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, alias="pageSize", ge=1, le=100),
    search: str | None = None,
    stage: str | None = None,
    db: Session = Depends(get_db),
):
    return ProspectService.list(db, page, page_size, search, stage)


@router.get("/{prospect_id}", response_model=ProspectResponse)
def get_prospect(prospect_id: int, db: Session = Depends(get_db)):
    try:
        return ProspectService.get(db, prospect_id)
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex))


@router.post(
    "",
    response_model=ProspectResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_prospect(
    payload: ProspectCreate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    try:
        return ProspectService.create(
            db,
            payload,
            actor_id=current_user.id if current_user else None,
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))


@router.put("/{prospect_id}", response_model=ProspectResponse)
def update_prospect(
    prospect_id: int,
    payload: ProspectUpdate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    try:
        return ProspectService.update(
            db,
            prospect_id,
            payload,
            actor_id=current_user.id if current_user else None,
        )
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex))


@router.delete("/{prospect_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_prospect(
    prospect_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    try:
        ProspectService.delete(
            db,
            prospect_id,
            actor_id=current_user.id if current_user else None,
        )
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex))


@router.patch("/{prospect_id}/stage", response_model=ProspectResponse)
def update_stage(
    prospect_id: int,
    stage: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    try:
        return ProspectService.change_stage(
            db,
            prospect_id,
            stage,
            actor_id=current_user.id if current_user else None,
        )
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex))


@router.patch("/{prospect_id}/exam", response_model=ProspectResponse)
def update_exam(
    prospect_id: int,
    attended: bool,
    certified: bool,
    db: Session = Depends(get_db),
):
    try:
        return ProspectService.update_exam(
            db, prospect_id, attended, certified
        )
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex))
