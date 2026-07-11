import json
from typing import Any, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile as FastAPIUploadFile,
    status,
)
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.id_generator import generate_next_code
from app.db.models.prospect import Prospect
from app.db.models.prospect_document import DocumentType
from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.dependencies.auth import get_current_user, get_optional_user
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


def _is_upload(value: Any) -> bool:
    """True for Starlette/FastAPI upload file objects."""
    return hasattr(value, "filename") and hasattr(value, "file")

# Flat form field names the frontend may send (camelCase + snake_case)
LEAD_FORM_FIELDS = {
    "name",
    "email",
    "phone",
    "password",
    "prospect_id",
    "prospectId",
    "fatherName",
    "father_name",
    "motherName",
    "mother_name",
    "dob",
    "courseId",
    "course_id",
    "specialization",
    "address",
    "deliveryAddress",
    "delivery_address",
    "deliveryDate",
    "delivery_date",
    "estimatedValue",
    "estimated_deal_value",
    "notes",
    "assignedToId",
    "assigned_to_id",
    "source",
    "followUpDate",
    "follow_up_date",
    "stage",
}


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


def _maybe_parse_json_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return value
    if text[0] in "[{":
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return value
    return value


def _extract_document_files(
    form_files: list[tuple[str, Any]],
) -> dict[str, Any]:
    """
    Accepts:
      document_aadhaar, document_photo, ...
      documents[aadhaar], doc_aadhaar
      or field name equal to doc type
    """
    mapping: dict[str, Any] = {}
    for field_name, upload in form_files:
        if not _is_upload(upload) or not upload.filename:
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
    form_files: list[tuple[str, Any]],
) -> dict[int, Any]:
    """
    Accepts:
      receipt_0, receipt_1, receipts[0], payment_receipt_0
    """
    mapping: dict[int, Any] = {}
    for field_name, upload in form_files:
        if not _is_upload(upload) or not upload.filename:
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


def _pair_documents_with_doctypes(form) -> dict[str, Any]:
    """
    Frontend pattern:
      documents: <file>, docTypes: aadhaar
      documents: <file>, docTypes: photo
    (or all documents then all docTypes — paired by index)
    """
    document_files: list[Any] = []
    doc_types: list[str] = []

    for key, value in form.multi_items():
        if key in ("documents", "document") and _is_upload(value):
            if value.filename:
                document_files.append(value)
        elif key in ("docTypes", "docType", "document_types", "documentTypes"):
            if isinstance(value, str) and value.strip():
                doc_types.append(value.strip())
            elif _is_upload(value):
                raw = value.file.read()
                try:
                    value.file.seek(0)
                except Exception:
                    pass
                text = (
                    raw.decode("utf-8", errors="ignore").strip()
                    if isinstance(raw, (bytes, bytearray))
                    else str(raw).strip()
                )
                if text:
                    doc_types.append(text)

    mapping: dict[str, Any] = {}
    for index, upload in enumerate(document_files):
        if index >= len(doc_types):
            break
        doc_type = doc_types[index]
        if doc_type in DOC_TYPES:
            mapping[doc_type] = upload
    return mapping


def _build_lead_from_flat_form(form, model_cls):
    """
    Build ProspectCreate/ProspectUpdate from flat multipart fields
    (name, email, courseId, payments JSON string, etc.).
    """
    data: dict[str, Any] = {}

    for key in LEAD_FORM_FIELDS:
        if key not in form:
            continue
        value = form.get(key)
        if _is_upload(value):
            continue
        if value is None:
            continue
        if isinstance(value, str) and value.strip() == "":
            # keep empty password as "" so validator can null it
            if key != "password":
                continue
        data[key] = value

    # payments may be JSON string "[]" or object list
    if "payments" in form:
        payments_raw = form.get("payments")
        if isinstance(payments_raw, str):
            data["payments"] = _maybe_parse_json_value(payments_raw)
        elif payments_raw is not None and not _is_upload(payments_raw):
            data["payments"] = payments_raw

    # documents metadata JSON (optional)
    if "documentsMeta" in form or "documents_meta" in form:
        meta_raw = form.get("documentsMeta") or form.get("documents_meta")
        if isinstance(meta_raw, str):
            data["documents"] = _maybe_parse_json_value(meta_raw)

    try:
        return model_cls.model_validate(data)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc


def _parse_multipart_lead(form, model_cls):
    """
    Supports:
      1) payload/data = JSON string (preferred compact format)
      2) flat form fields from the lead screen + documents/docTypes files
    """
    raw_payload = form.get("payload") or form.get("data")
    if isinstance(raw_payload, str) and raw_payload.strip():
        payload = _parse_json_payload(raw_payload, model_cls)
    else:
        payload = _build_lead_from_flat_form(form, model_cls)

    uploads = [
        (key, value)
        for key, value in form.multi_items()
        if _is_upload(value)
    ]

    document_files = _extract_document_files(uploads)
    # Merge frontend documents[] + docTypes[] pairing
    document_files.update(_pair_documents_with_doctypes(form))
    receipt_files = _extract_receipt_files(uploads)

    return payload, document_files, receipt_files


def _employee_scope_id(user: User) -> int | None:
    """Employees only see their own leads; admins see all."""
    if user.role == UserRole.employee:
        return user.id
    return None


def _ensure_prospect_access(prospect, user: User) -> None:
    if user.role == UserRole.admin:
        return
    if prospect.assigned_to_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this prospect.",
        )


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
    assigned_to_id: int | None = Query(None, alias="assignedToId"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Admin: all prospects (optional assignedToId filter).
    Employee: only prospects assigned to the logged-in user.
    """
    scope_id = _employee_scope_id(current_user)
    if scope_id is not None:
        # Employees cannot override scope
        assigned_to_id = scope_id
    elif assigned_to_id is None:
        assigned_to_id = None  # admin sees all

    return ProspectService.list(
        db,
        page,
        page_size,
        search,
        stage,
        assigned_to_id=assigned_to_id,
    )


@router.get("/{prospect_id}", response_model=ProspectResponse)
def get_prospect(
    prospect_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        prospect = ProspectService.get(db, prospect_id)
        _ensure_prospect_access(prospect, current_user)
        return prospect
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
    - application/json: ProspectCreate body
    - multipart/form-data (either):
        A) payload=<JSON> + document_aadhaar/receipt_0 files
        B) flat fields (name, email, courseId, ...) +
           documents[] files paired with docTypes[]
    """
    content_type = (request.headers.get("content-type") or "").lower()
    actor_id = current_user.id if current_user else None

    try:
        if "multipart/form-data" in content_type:
            form = await request.form()
            payload, document_files, receipt_files = _parse_multipart_lead(
                form, ProspectCreate
            )

            # Auto-assign to logged-in employee if not provided
            if (
                current_user
                and current_user.role == UserRole.employee
                and not payload.assigned_to_id
            ):
                payload.assigned_to_id = current_user.id

            return ProspectService.create(
                db,
                payload,
                actor_id=actor_id,
                document_files=document_files,
                receipt_files=receipt_files,
            )

        body = await request.json()
        payload = ProspectCreate.model_validate(body)
        if (
            current_user
            and current_user.role == UserRole.employee
            and not payload.assigned_to_id
        ):
            payload.assigned_to_id = current_user.id

        return ProspectService.create(db, payload, actor_id=actor_id)

    except HTTPException:
        raise
    except ValidationError as ex:
        raise HTTPException(status_code=422, detail=ex.errors())
    except IntegrityError as ex:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Could not create lead (duplicate or invalid data).",
        ) from ex
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))


@router.put("/{prospect_id}", response_model=ProspectResponse)
async def update_prospect(
    prospect_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Edit lead. Supports same JSON / multipart formats as create.
    """
    content_type = (request.headers.get("content-type") or "").lower()
    actor_id = current_user.id

    try:
        existing = ProspectService.get(db, prospect_id)
        _ensure_prospect_access(existing, current_user)

        if "multipart/form-data" in content_type:
            form = await request.form()
            payload, document_files, receipt_files = _parse_multipart_lead(
                form, ProspectUpdate
            )
            # Employees cannot reassign leads to someone else
            if (
                current_user.role == UserRole.employee
                and payload.assigned_to_id is not None
                and payload.assigned_to_id != current_user.id
            ):
                raise HTTPException(
                    status_code=403,
                    detail="Employees cannot reassign leads.",
                )
            return ProspectService.update(
                db,
                prospect_id,
                payload,
                actor_id=actor_id,
                document_files=document_files,
                receipt_files=receipt_files,
            )

        body = await request.json()
        payload = ProspectUpdate.model_validate(body)
        if (
            current_user.role == UserRole.employee
            and payload.assigned_to_id is not None
            and payload.assigned_to_id != current_user.id
        ):
            raise HTTPException(
                status_code=403,
                detail="Employees cannot reassign leads.",
            )
        return ProspectService.update(
            db, prospect_id, payload, actor_id=actor_id
        )

    except HTTPException:
        raise
    except ValidationError as ex:
        raise HTTPException(status_code=422, detail=ex.errors())
    except IntegrityError as ex:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Could not update lead (duplicate or invalid data).",
        ) from ex
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex))


@router.post(
    "/{prospect_id}/documents/{doc_type}",
    response_model=ProspectResponse,
)
async def upload_lead_document(
    prospect_id: int,
    doc_type: DocumentType,
    file: FastAPIUploadFile = File(...),
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
    receipt_files: dict[int, Any] = {}

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
                if _is_upload(v)
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
    current_user: User = Depends(get_current_user),
):
    try:
        prospect = ProspectService.get(db, prospect_id)
        _ensure_prospect_access(prospect, current_user)
        ProspectService.delete(
            db,
            prospect_id,
            actor_id=current_user.id,
        )
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex))


@router.patch("/{prospect_id}/stage", response_model=ProspectResponse)
def update_stage(
    prospect_id: int,
    stage: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        prospect = ProspectService.get(db, prospect_id)
        _ensure_prospect_access(prospect, current_user)
        return ProspectService.change_stage(
            db,
            prospect_id,
            stage,
            actor_id=current_user.id,
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
