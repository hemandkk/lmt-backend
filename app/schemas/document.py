from datetime import datetime
from typing import Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    field_validator,
)

from app.core.file_storage import FileStorage
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
        # 💡 ADD THIS VALIDATOR BLOCK:
    @field_validator("file_url", mode="after")
    @classmethod
    def convert_to_presigned_url(cls, v: str) -> str:
        if not v:
            return v
        return FileStorage.get_view_url(v)


# ---------------------------------------------------------
# List Response
# ---------------------------------------------------------

class DocumentListResponse(BaseModel):

    items: list[DocumentResponse]

    total: int