import json
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.id_generator import generate_next_code
from app.db.models.prospect import Prospect
from app.db.models.prospect_document import DocumentType
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

DOC_TYPES = {item.value for item in DocumentType}


def _parse_json_payload(raw: str, model_cls):
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid JSON in payload: {exc}",
        ) from exc

    try:
        return model_cls.model_validate(data)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=exc.errors(),
        ) from exc


def _extract_document_files(
    form_files: list[tuple[str, UploadFile]],
) -> dict[str, UploadFile]:
    """
    Accepts:
      document_aadhaar, document_photo, ...
      documents[aadhaar], doc_aadhaar
      or field name equal to doc type
    """
    mapping: dict[str, UploadFile] = {}
    for field_name, upload in form_files:
        if not upload or not upload.filename:
            continue
        name = field_name.strip()
        key = None
        for prefix in ("document_", "documents[", "doc_"):
            if name.startswith(prefix):
                key = name[len(prefix) :].rstrip("]")
                break
        if key is None and name in DOC_TYPES:
            key = name
        if key and key in DOC_TYPES:
            mapping[key] = upload
    return mapping


def _extract_receipt_files(
    form_files: list[tuple[str, UploadFile]],
) -> dict[int, UploadFile]:
    """
    Accepts:
      receipt_0, receipt_1, receipts[0], payment_receipt_0
    """
    mapping: dict[int, UploadFile] = {}
    for field_name, upload in form_files:
        if not upload or not upload.filename:
            continue
        name = field_name.strip()
        index = None
        for prefix in ("receipt_", "receipts[", "payment_receipt_"):
            if name.startswith(prefix):
                raw = name[len(prefix) :].rstrip("]")
                if raw.isdigit():
                    index = int(raw)
                break
        if index is not None:
            mapping[index] = upload
    return mapping


@router.get("/utility/next-prospect-id")
def get_next_prospect_id(db: Session = Depends(get_db)):
    try:
        prospect_id = generate_next_code(
            db=db,
            model=Prospect,
            field="prospect_id",
            prefix="PRO",
            digits=4,
        )
        return {"next_id": prospect_id, "prospectId": prospect_id}
    except Exception as ex:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate prospect id: {ex}",
        ) from ex


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
async def create_prospect(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """
    Create lead.
    - application/json: body = ProspectCreate (payments inline, no files)
    - multipart/form-data:
        payload: JSON string of ProspectCreate (camelCase OK)
        document_aadhaar / document_photo / ... : files
        receipt_0 / receipt_1 / ... : payment receipt files
    """
    content_type = (request.headers.get("content-type") or "").lower()
    actor_id = current_user.id if current_user else None

    try:
        if "multipart/form-data" in content_type:
            form = await request.form()
            raw_payload = form.get("payload") or form.get("data")
            if not raw_payload or not isinstance(raw_payload, str):
                raise HTTPException(
                    status_code=400,
                    detail="multipart create requires form field 'payload' (JSON string).",
                )
            payload = _parse_json_payload(raw_payload, ProspectCreate)
            uploads = [
                (key, value)
                for key, value in form.multi_items()
                if isinstance(value, UploadFile)
            ]
            return ProspectService.create(
                db,
                payload,
                actor_id=actor_id,
                document_files=_extract_document_files(uploads),
                receipt_files=_extract_receipt_files(uploads),
            )

        body = await request.json()
        payload = ProspectCreate.model_validate(body)
        return ProspectService.create(db, payload, actor_id=actor_id)

    except HTTPException:
        raise
    except ValidationError as ex:
        raise HTTPException(status_code=422, detail=ex.errors())
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))


@router.put("/{prospect_id}", response_model=ProspectResponse)
async def update_prospect(
    prospect_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """
    Edit lead (also used from list more-actions → edit).
    Supports JSON and multipart (same shape as create).
    """
    content_type = (request.headers.get("content-type") or "").lower()
    actor_id = current_user.id if current_user else None

    try:
        if "multipart/form-data" in content_type:
            form = await request.form()
            raw_payload = form.get("payload") or form.get("data")
            if not raw_payload or not isinstance(raw_payload, str):
                raise HTTPException(
                    status_code=400,
                    detail="multipart update requires form field 'payload' (JSON string).",
                )
            payload = _parse_json_payload(raw_payload, ProspectUpdate)
            uploads = [
                (key, value)
                for key, value in form.multi_items()
                if isinstance(value, UploadFile)
            ]
            return ProspectService.update(
                db,
                prospect_id,
                payload,
                actor_id=actor_id,
                document_files=_extract_document_files(uploads),
                receipt_files=_extract_receipt_files(uploads),
            )

        body = await request.json()
        payload = ProspectUpdate.model_validate(body)
        return ProspectService.update(
            db, prospect_id, payload, actor_id=actor_id
        )

    except HTTPException:
        raise
    except ValidationError as ex:
        raise HTTPException(status_code=422, detail=ex.errors())
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex))


@router.post(
    "/{prospect_id}/documents/{doc_type}",
    response_model=ProspectResponse,
)
async def upload_lead_document(
    prospect_id: int,
    doc_type: DocumentType,
    file: UploadFile = File(...),
    remarks: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """List more-action / edit: upload or replace a single document type."""
    try:
        DocumentType(doc_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid document type.") from exc

    try:
        return ProspectService.update(
            db,
            prospect_id,
            ProspectUpdate(documents=[]),
            actor_id=current_user.id if current_user else None,
            document_files={doc_type.value: file},
        )
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex))


@router.post(
    "/{prospect_id}/payments",
    response_model=ProspectResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_lead_payment(
    prospect_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """
    List more-action: add a payment to an existing lead.
    JSON body = LeadPaymentInput, or multipart with payload + receipt file.
    """
    from app.schemas.prospect import LeadPaymentInput

    content_type = (request.headers.get("content-type") or "").lower()
    actor_id = current_user.id if current_user else None
    receipt_files: dict[int, UploadFile] = {}

    try:
        if "multipart/form-data" in content_type:
            form = await request.form()
            raw = form.get("payload") or form.get("data")
            if not raw or not isinstance(raw, str):
                raise HTTPException(
                    status_code=400,
                    detail="multipart requires 'payload' JSON field.",
                )
            payment = _parse_json_payload(raw, LeadPaymentInput)
            uploads = [
                (k, v)
                for k, v in form.multi_items()
                if isinstance(v, UploadFile)
            ]
            # Single receipt may be named "receipt" or "receipt_0"
            for name, upload in uploads:
                if name in ("receipt", "receipt_0", "file") or name.startswith(
                    "receipt"
                ):
                    receipt_files[0] = upload
                    break
        else:
            payment = LeadPaymentInput.model_validate(await request.json())

        return ProspectService.update(
            db,
            prospect_id,
            ProspectUpdate(payments=[payment], replace_payments=False),
            actor_id=actor_id,
            receipt_files=receipt_files,
        )
    except HTTPException:
        raise
    except ValidationError as ex:
        raise HTTPException(status_code=422, detail=ex.errors())
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
