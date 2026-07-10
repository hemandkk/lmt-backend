from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status


class FileService:
    ALLOWED_EXTENSIONS = {
        ".pdf",
        ".png",
        ".jpg",
        ".jpeg",
        ".doc",
        ".docx",
    }

    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

    UPLOAD_ROOT = Path("uploads")

    async def upload_file(
        self,
        *,
        file: UploadFile,
        folder: str,
    ) -> str:
        extension = Path(file.filename).suffix.lower()

        if extension not in self.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported file type.",
            )

        content = await file.read()

        if len(content) > self.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File exceeds maximum allowed size (10 MB).",
            )

        upload_dir = self.UPLOAD_ROOT / folder
        upload_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{uuid.uuid4().hex}{extension}"

        file_path = upload_dir / filename

        with open(file_path, "wb") as buffer:
            buffer.write(content)

        return str(file_path).replace("\\", "/")

    def delete_file(
        self,
        file_path: str,
    ) -> None:

        path = Path(file_path)

        if path.exists():
            path.unlink()

    def file_exists(
        self,
        file_path: str,
    ) -> bool:

        return Path(file_path).exists()