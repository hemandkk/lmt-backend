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

from app.db.session import get_db

from app.db.models.prospect_document import DocumentType

from app.schemas.document import (
    DocumentResponse,
    DocumentListResponse,
    DocumentUpdate,
)

from app.services.document_service import DocumentService


router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
)


# -------------------------------------------------------
# Upload Document
# -------------------------------------------------------

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
):

    try:

        return DocumentService.upload_document(
            db=db,
            prospect_id=prospect_id,
            document_type=document_type,
            file=file,
            remarks=remarks,
        )

    except ValueError as ex:

        raise HTTPException(
            status_code=400,
            detail=str(ex),
        )


# -------------------------------------------------------
# List Documents
# -------------------------------------------------------

@router.get(
    "/prospects/{prospect_id}",
    response_model=DocumentListResponse,
)
def list_documents(
    prospect_id: int,
    db: Session = Depends(get_db),
):

    documents = DocumentService.get_documents(
        db,
        prospect_id,
    )

    return {
        "items": documents,
        "total": len(documents),
    }


# -------------------------------------------------------
# Get One Document
# -------------------------------------------------------

@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
)
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
):

    try:

        return DocumentService.get_document(
            db,
            document_id,
        )

    except ValueError as ex:

        raise HTTPException(
            status_code=404,
            detail=str(ex),
        )


# -------------------------------------------------------
# Update
# -------------------------------------------------------

@router.put(
    "/{document_id}",
    response_model=DocumentResponse,
)
def update_document(
    document_id: int,
    payload: DocumentUpdate,
    db: Session = Depends(get_db),
):

    try:

        return DocumentService.update_document(
            db,
            document_id,
            payload,
        )

    except ValueError as ex:

        raise HTTPException(
            status_code=404,
            detail=str(ex),
        )


# -------------------------------------------------------
# Delete
# -------------------------------------------------------

@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
):

    try:

        DocumentService.delete_document(
            db,
            document_id,
        )

    except ValueError as ex:

        raise HTTPException(
            status_code=404,
            detail=str(ex),
        )