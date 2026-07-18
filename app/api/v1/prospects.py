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
from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.id_generator import generate_next_code
from app.core.roles import (
    admission_stage_allowed_for_role,
    can_change_admission_stage,
    can_mutate_leads,
    intersect_admission_filters,
    is_employee,
    prospect_visible_to_user,
    visible_admission_stages_for_role,
)
from app.db.models.prospect import Prospect
from app.db.models.prospect_document import DocumentType
from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.dependencies.auth import get_current_user, get_optional_user
from app.dependencies.permissions import (
    deny_if_cannot_mutate_leads,
    require_admin,
)
from app.schemas.prospect import (
    ProspectCreate,
    ProspectListResponse,
    ProspectPaymentListResponse,
    ProspectResponse,
    ProspectTimelineResponse,
    ProspectUpdate,
    TimelineItem,
)
from app.schemas.document import DocumentListResponse, DocumentResponse
from app.services.admission_stage_service import parse_admission_stage
from app.services.prospect_service import ProspectService
from app.services.document_service import DocumentService
from app.services.export_service import ExportService
from app.services.notification_service import ActivityLogService
from app.repositories.payment_repository import PaymentRepository


class StageUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    stage: str


class AdmissionStageUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    admission_stage: str = Field(
        validation_alias=AliasChoices(
            "admissionStage",
            "admission_stage",
            "stage",
        ),
    )


class AssignProspectRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    assigned_to_id: Optional[int] = Field(
        default=None,
        validation_alias=AliasChoices(
            "assignedToId", "assigned_to_id", "employeeId", "employee_id"
        ),
    )


class ExamUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    attended: Optional[bool] = Field(
        default=None,
        validation_alias=AliasChoices(
            "attended", "examAttended", "exam_attended"
        ),
    )
    certified: Optional[bool] = Field(
        default=None,
        validation_alias=AliasChoices(
            "certified", "examCertified", "exam_certified"
        ),
    )

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
    "university",
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
    """Sales employees only see their own leads."""
    if is_employee(user):
        return user.id
    return None


def _ensure_prospect_access(prospect, user: User) -> None:
    if prospect_visible_to_user(prospect, user):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have access to this prospect.",
    )


def _parse_admission_stage_filters(
    admission_stage: str | None,
    admission_stages_csv: str | None,
    current_user: User,
) -> list[str] | None:
    """
    Resolve admissionStage / admissionStages query params with role force-filters.
    Returns:
      - None: no admission-stage filter
      - []: empty result (requested stages outside role visibility)
      - list[str]: IN filter values
    """
    requested = []
    if admission_stages_csv:
        for part in admission_stages_csv.split(","):
            part = part.strip()
            if part:
                requested.append(parse_admission_stage(part))
    elif admission_stage:
        requested.append(parse_admission_stage(admission_stage))

    forced = visible_admission_stages_for_role(current_user)
    resolved = intersect_admission_filters(requested or None, forced)
    if resolved is None:
        return None
    return [s.value for s in resolved]


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
    admission_stage: str | None = Query(None, alias="admissionStage"),
    admission_stages: str | None = Query(None, alias="admissionStages"),
    course_id: int | None = Query(None, alias="courseId"),
    assigned_to_id: int | None = Query(None, alias="assignedToId"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Role-scoped lead list:
    - admin: all (optional filters)
    - employee: assigned leads only
    - accountant: all leads in certificate_waiting (any assignee)
    - processing_team: all leads in waiting_result / result_announced
    """
    scope_id = _employee_scope_id(current_user)
    if scope_id is not None:
        assigned_to_id = scope_id

    # Accountant / processing_team: stage-scoped across all employees
    if visible_admission_stages_for_role(current_user) is not None:
        assigned_to_id = None

    try:
        stage_filter = _parse_admission_stage_filters(
            admission_stage, admission_stages, current_user
        )
        return ProspectService.list(
            db,
            page,
            page_size,
            search,
            stage,
            admission_stages=stage_filter,
            assigned_to_id=assigned_to_id,
            course_id=course_id,
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex


@router.get("/export")
def export_prospects(
    search: str | None = None,
    stage: str | None = None,
    admission_stage: str | None = Query(None, alias="admissionStage"),
    admission_stages: str | None = Query(None, alias="admissionStages"),
    course_id: int | None = Query(None, alias="courseId"),
    assigned_to_id: int | None = Query(None, alias="assignedToId"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Download filtered leads as Excel (.xlsx).
    Same role scoping and filters as list.
    """
    if not can_mutate_leads(current_user) and current_user.role != UserRole.admin:
        # accountant / processing may still export their scoped lists
        pass

    scope_id = _employee_scope_id(current_user)
    if scope_id is not None:
        assigned_to_id = scope_id
    if visible_admission_stages_for_role(current_user) is not None:
        assigned_to_id = None

    try:
        stage_filter = _parse_admission_stage_filters(
            admission_stage, admission_stages, current_user
        )
        return ExportService.export_prospects_xlsx(
            db,
            search=search,
            stage=stage,
            admission_stages=stage_filter,
            assigned_to_id=assigned_to_id,
            course_id=course_id,
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex


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
    current_user: User = Depends(get_current_user),
):
    """
    Create lead.
    - application/json: ProspectCreate body
    - multipart/form-data (either):
        A) payload=<JSON> + document_aadhaar/receipt_0 files
        B) flat fields (name, email, courseId, ...) +
           documents[] files paired with docTypes[]
    """
    deny_if_cannot_mutate_leads(current_user)
    content_type = (request.headers.get("content-type") or "").lower()
    actor_id = current_user.id

    try:
        if "multipart/form-data" in content_type:
            form = await request.form()
            payload, document_files, receipt_files = _parse_multipart_lead(
                form, ProspectCreate
            )

            # Employees always own leads they create; admin may pass assignedToId
            if current_user and current_user.role == UserRole.employee:
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
        if current_user and current_user.role == UserRole.employee:
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
    deny_if_cannot_mutate_leads(current_user)
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


@router.get(
    "/{prospect_id}/documents",
    response_model=DocumentListResponse,
)
def list_prospect_documents(
    prospect_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List documents for a lead (same data as GET /documents/prospects/{id})."""
    try:
        prospect = ProspectService.get(db, prospect_id)
        _ensure_prospect_access(prospect, current_user)
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex))

    documents = DocumentService.get_documents(db, prospect_id)
    return {"items": documents, "total": len(documents)}


@router.post(
    "/{prospect_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_prospect_document(
    prospect_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Listing more-action: upload a document via multipart.
    Accepts docType/documentType/document_type + file/document/documents.
    """
    deny_if_cannot_mutate_leads(current_user)
    try:
        prospect = ProspectService.get(db, prospect_id)
        _ensure_prospect_access(prospect, current_user)
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex))

    form = await request.form()
    doc_type_raw = (
        form.get("docType")
        or form.get("documentType")
        or form.get("document_type")
        or form.get("doc_type")
        or form.get("type")
    )
    if not doc_type_raw or not isinstance(doc_type_raw, str):
        raise HTTPException(
            status_code=400,
            detail="document type is required (docType / documentType).",
        )

    try:
        document_type = DocumentType(doc_type_raw.strip())
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid document type: {doc_type_raw}",
        ) from exc

    remarks = form.get("remarks")
    if remarks is not None and not isinstance(remarks, str):
        remarks = None

    upload = None
    preferred_names = {
        "file",
        "document",
        "documents",
        "receipt",
        "upload",
    }
    for name, value in form.multi_items():
        if _is_upload(value) and value.filename and name in preferred_names:
            upload = value
            break
    if upload is None:
        for _, value in form.multi_items():
            if _is_upload(value) and value.filename:
                upload = value
                break

    if upload is None:
        raise HTTPException(status_code=400, detail="file is required.")

    try:
        return DocumentService.upload_document(
            db=db,
            prospect_id=prospect_id,
            document_type=document_type,
            file=upload,
            remarks=remarks,
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex
    except IntegrityError as ex:
        raise HTTPException(
            status_code=400,
            detail="Could not save document (duplicate id). Please retry.",
        ) from ex


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
    current_user: User = Depends(get_current_user),
):
    """List more-action / edit: upload or replace a single document type."""
    deny_if_cannot_mutate_leads(current_user)
    try:
        prospect = ProspectService.get(db, prospect_id)
        _ensure_prospect_access(prospect, current_user)
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex))

    try:
        DocumentType(doc_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid document type.") from exc

    try:
        return ProspectService.update(
            db,
            prospect_id,
            ProspectUpdate(documents=[]),
            actor_id=current_user.id,
            document_files={doc_type.value: file},
        )
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex))


@router.get(
    "/{prospect_id}/payments",
    response_model=ProspectPaymentListResponse,
)
def list_prospect_payments(
    prospect_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List payments for a lead."""
    try:
        prospect = ProspectService.get(db, prospect_id)
        _ensure_prospect_access(prospect, current_user)
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex))

    items = PaymentRepository(db).get_by_prospect(prospect_id)
    return {"items": items, "total": len(items)}


@router.get(
    "/{prospect_id}/timeline",
    response_model=ProspectTimelineResponse,
)
def get_prospect_timeline(
    prospect_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, alias="pageSize", ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Lead activity timeline: activity logs + payments + document uploads,
    newest first.
    """
    try:
        prospect = ProspectService.get(db, prospect_id)
        _ensure_prospect_access(prospect, current_user)
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex))

    items: list[TimelineItem] = []

    logs = ActivityLogService.list(
        db,
        page=1,
        page_size=200,
        prospect_id=prospect_id,
    )
    for log in logs["items"]:
        items.append(
            TimelineItem(
                id=f"log-{log['id']}",
                type=log["action"],
                title=log["action"].replace("_", " ").title(),
                description=log["description"],
                created_at=log["created_at"],
                user_id=log["user_id"],
                user_name=log.get("user_name"),
                meta={"entityType": log["entity_type"], "entityId": log["entity_id"]},
            )
        )

    for payment in prospect.payments or []:
        ptype = (
            payment.payment_type.value
            if hasattr(payment.payment_type, "value")
            else str(payment.payment_type)
        )
        items.append(
            TimelineItem(
                id=f"payment-{payment.id}",
                type="payment",
                title=f"Payment received ({ptype})",
                description=f"Amount {payment.amount}"
                + (f" — {payment.notes}" if payment.notes else ""),
                created_at=payment.created_at,
                user_id=payment.created_by,
                user_name=None,
                meta={
                    "paymentId": payment.payment_id,
                    "amount": str(payment.amount),
                    "paymentType": ptype,
                    "paymentDate": str(payment.payment_date),
                },
            )
        )

    for doc in prospect.documents or []:
        dtype = (
            doc.document_type.value
            if hasattr(doc.document_type, "value")
            else str(doc.document_type)
        )
        items.append(
            TimelineItem(
                id=f"document-{doc.id}",
                type="document",
                title=f"Document uploaded ({dtype})",
                description=doc.original_filename or dtype,
                created_at=doc.created_at,
                user_id=None,
                user_name=None,
                meta={
                    "documentId": doc.document_id,
                    "docType": dtype,
                    "fileUrl": doc.file_url,
                },
            )
        )

    items.sort(key=lambda x: x.created_at, reverse=True)
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    return {"items": items[start:end], "total": total}


@router.post(
    "/{prospect_id}/payments",
    response_model=ProspectResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_lead_payment(
    prospect_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List more-action: add a payment to an existing lead.
    Supports:
    - JSON body (LeadPaymentInput)
    - multipart with payload/data JSON + receipt
    - flat multipart: amount, paymentType, paymentDate, notes, receipt
    """
    from app.schemas.prospect import LeadPaymentInput

    try:
        prospect = ProspectService.get(db, prospect_id)
        _ensure_prospect_access(prospect, current_user)
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex))

    content_type = (request.headers.get("content-type") or "").lower()
    actor_id = current_user.id
    receipt_files: dict[int, Any] = {}

    try:
        if "multipart/form-data" in content_type:
            form = await request.form()
            raw = form.get("payload") or form.get("data")
            if raw and isinstance(raw, str):
                payment = _parse_json_payload(raw, LeadPaymentInput)
            else:
                # Flat listing-page form fields
                flat = {
                    "amount": form.get("amount"),
                    "paymentType": form.get("paymentType")
                    or form.get("payment_type"),
                    "paymentMethod": form.get("paymentMethod")
                    or form.get("payment_method"),
                    "paymentDate": form.get("paymentDate")
                    or form.get("payment_date"),
                    "transactionNumber": form.get("transactionNumber")
                    or form.get("transaction_number"),
                    "notes": form.get("notes"),
                }
                flat = {k: v for k, v in flat.items() if v is not None and v != ""}
                if "amount" not in flat or "paymentType" not in flat:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "multipart requires 'payload' JSON, or flat fields "
                            "amount + paymentType (+ paymentDate)."
                        ),
                    )
                payment = LeadPaymentInput.model_validate(flat)

            uploads = [
                (k, v)
                for k, v in form.multi_items()
                if _is_upload(v)
            ]
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


@router.post(
    "/{prospect_id}/sync-sheets",
    response_model=ProspectResponse,
)
def sync_prospect_to_sheets(
    prospect_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Admin: manually (re)sync a lead row to Google Sheets.
    Useful after a failed automatic sync.
    """
    from app.services.google_sheets_service import GoogleSheetsService

    try:
        prospect = ProspectService.get(db, prospect_id)
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex)) from ex

    synced = GoogleSheetsService.sync_prospect(
        db, prospect, actor_id=current_user.id
    )
    return ProspectService.get(db, synced.id)


@router.delete("/{prospect_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_prospect(
    prospect_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deny_if_cannot_mutate_leads(current_user)
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
    payload: StageUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deny_if_cannot_mutate_leads(current_user)
    try:
        prospect = ProspectService.get(db, prospect_id)
        _ensure_prospect_access(prospect, current_user)
        return ProspectService.change_stage(
            db,
            prospect_id,
            payload.stage,
            actor_id=current_user.id,
        )
    except ValueError as ex:
        detail = str(ex)
        status_code = (
            status.HTTP_400_BAD_REQUEST
            if detail.lower().startswith("invalid stage")
            else status.HTTP_404_NOT_FOUND
        )
        raise HTTPException(status_code=status_code, detail=detail)


@router.patch(
    "/{prospect_id}/admission-stage",
    response_model=ProspectResponse,
)
def update_admission_stage(
    prospect_id: int,
    payload: AdmissionStageUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Listing-page update for admission funnel stage.
    Does not change CRM `stage` (new/won/…).
    Restricted stages (waiting_result, result_announced, completed, delivered)
    require admin or processing_team. Accountant cannot change any stage.
    """
    if not can_change_admission_stage(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to change admission stage.",
        )
    try:
        target = parse_admission_stage(payload.admission_stage)
    except ValueError as ex:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ex),
        ) from ex

    if not admission_stage_allowed_for_role(current_user, target):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Only admin or processing_team may set admission stage "
                f"'{target.value}'."
            ),
        )

    try:
        prospect = ProspectService.get(db, prospect_id)
        _ensure_prospect_access(prospect, current_user)
        return ProspectService.change_admission_stage(
            db,
            prospect_id,
            target,
            actor_id=current_user.id,
        )
    except ValueError as ex:
        detail = str(ex)
        status_code = (
            status.HTTP_400_BAD_REQUEST
            if "admission stage" in detail.lower()
            else status.HTTP_404_NOT_FOUND
        )
        raise HTTPException(status_code=status_code, detail=detail) from ex


@router.patch("/{prospect_id}/assign", response_model=ProspectResponse)
def assign_prospect(
    prospect_id: int,
    payload: AssignProspectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Admin more-action: assign or reassign a lead to an employee.
    Body: { "assignedToId": <employeeUserId> } or null to unassign.
    """
    try:
        return ProspectService.assign(
            db,
            prospect_id,
            payload.assigned_to_id,
            actor_id=current_user.id,
        )
    except ValueError as ex:
        detail = str(ex)
        code = (
            status.HTTP_400_BAD_REQUEST
            if "assignedToId" in detail or "employee" in detail.lower()
            else status.HTTP_404_NOT_FOUND
        )
        raise HTTPException(status_code=code, detail=detail) from ex


@router.patch("/{prospect_id}/exam", response_model=ProspectResponse)
def update_exam(
    prospect_id: int,
    payload: ExamUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deny_if_cannot_mutate_leads(current_user)
    if payload.attended is None and payload.certified is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide examAttended and/or examCertified.",
        )
    try:
        prospect = ProspectService.get(db, prospect_id)
        _ensure_prospect_access(prospect, current_user)
        return ProspectService.update_exam(
            db,
            prospect_id,
            attended=payload.attended,
            certified=payload.certified,
            actor_id=current_user.id,
        )
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex))
