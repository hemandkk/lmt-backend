from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.db.models.prospect_document import DocumentType
from app.db.models.user import User
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.permissions import ensure_prospect_access, deny_if_cannot_mutate_leads
from app.repositories.document_repository import DocumentRepository
from app.schemas.document import (
    DocumentListResponse,
    DocumentResponse,
    DocumentUpdate,
)
from app.services.document_service import DocumentService

router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
)


@router.post(
    "/prospects/{prospect_id}",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_document(
    prospect_id: int,
    document_type: DocumentType = Form(...),
    remarks: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deny_if_cannot_mutate_leads(current_user)
    ensure_prospect_access(db, prospect_id, current_user)
    try:
        return DocumentService.upload_document(
            db=db,
            prospect_id=prospect_id,
            document_type=document_type,
            file=file,
            remarks=remarks,
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))


@router.get(
    "/prospects/{prospect_id}",
    response_model=DocumentListResponse,
)
def list_documents(
    prospect_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_prospect_access(db, prospect_id, current_user)
    documents = DocumentService.get_documents(db, prospect_id)
    return {"items": documents, "total": len(documents)}


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        document = DocumentService.get_document(db, document_id)
        ensure_prospect_access(db, document.prospect_id, current_user)
        return document
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex))


@router.put("/{document_id}", response_model=DocumentResponse)
def update_document(
    document_id: int,
    payload: DocumentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deny_if_cannot_mutate_leads(current_user)
    try:
        document = DocumentService.get_document(db, document_id)
        ensure_prospect_access(db, document.prospect_id, current_user)
        return DocumentService.update_document(db, document_id, payload)
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex))


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deny_if_cannot_mutate_leads(current_user)
    try:
        document = DocumentService.get_document(db, document_id)
        ensure_prospect_access(db, document.prospect_id, current_user)
        DocumentService.delete_document(db, document_id)
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex))
