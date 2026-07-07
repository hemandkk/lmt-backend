from datetime import datetime
from typing import Optional

from pydantic import (
    BaseModel,
    ConfigDict,
)

from app.db.models.prospect_document import (
    DocumentType,
)


# ---------------------------------------------------------
# Upload Request Metadata
# ---------------------------------------------------------

class DocumentUploadRequest(BaseModel):
    """
    Metadata supplied along with the uploaded file.
    The file itself comes from UploadFile in FastAPI.
    """

    document_type: DocumentType

    remarks: Optional[str] = None


# ---------------------------------------------------------
# Update Document
# ---------------------------------------------------------

class DocumentUpdate(BaseModel):

    remarks: Optional[str] = None

    verified: Optional[bool] = None


# ---------------------------------------------------------
# Response
# ---------------------------------------------------------

class DocumentResponse(BaseModel):

    id: int

    document_id: str

    prospect_id: int

    document_type: DocumentType

    original_filename: str

    stored_filename: str

    file_url: str

    mime_type: Optional[str]

    file_size: Optional[int]

    remarks: Optional[str]

    verified: bool

    created_at: datetime

    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )


# ---------------------------------------------------------
# List Response
# ---------------------------------------------------------

class DocumentListResponse(BaseModel):

    items: list[DocumentResponse]

    total: int