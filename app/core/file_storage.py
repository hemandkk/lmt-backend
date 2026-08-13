from __future__ import annotations

import logging
from pathlib import Path
import shutil
from urllib.parse import urlparse

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from fastapi import UploadFile

from app.core.config import settings

logger = logging.getLogger(__name__)


class FileStorage:
    BASE_UPLOAD_DIR = Path("app/uploads")
    PUBLIC_PREFIX = "/uploads"

    @classmethod
    def create_directory(cls, folder: Path) -> None:
        folder.mkdir(parents=True, exist_ok=True)

    @classmethod
    def _use_s3(cls) -> bool:
        return (settings.STORAGE_BACKEND or "local").lower() == "s3"

    @classmethod
    def _s3_configured(cls) -> bool:
        return bool(settings.S3_BUCKET)

    @classmethod
    def _s3_client(cls):
        # Crucial: signature_version='s3v4' is required for presigned secure URLs
        return boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL or None,
            region_name=settings.S3_REGION or "us-east-1",
            config=Config(signature_version="s3v4"),
        )

    @classmethod
    def _object_key(cls, folder: str, stored_filename: str) -> str:
        return f"{folder.strip('/')}/{stored_filename}"

    @classmethod
    def _key_from_url(cls, file_url: str) -> str | None:
        """Derive pure object key from saved file references."""
        if not file_url:
            return None
        url = file_url.strip()

        # Handle structural cleaning if path contains prefix metadata
        if url.startswith("s3://"):
            return url.replace(f"s3://{settings.S3_BUCKET}/", "")
        if url.startswith(cls.PUBLIC_PREFIX):
            return url[len(cls.PUBLIC_PREFIX) :].lstrip("/")
        if url.startswith("http://") or url.startswith("https://"):
            return urlparse(url).path.lstrip("/")
        
        return url

    # 💡 NEW KEY METHOD: Dynamically generates safe transient paths
    @classmethod
    def get_view_url(cls, stored_path_or_url: str) -> str:
        """
        Converts internal file key into a secure runtime asset link.
        Local: returns fallback path string.
        S3 Private: generates a secure temporary token link that expires in 15 mins.
        """
        if not stored_path_or_url:
            return ""

        if cls._use_s3():
            key = cls._key_from_url(stored_path_or_url)
            try:
                # Ask AWS to securely sign a temporary token for the private object
                presigned_url = cls._s3_client().generate_presigned_url(
                    'get_object',
                    Params={'Bucket': settings.S3_BUCKET, 'Key': key},
                    ExpiresIn=900 # 15 minutes expiration safety limit
                )
                return presigned_url
            except Exception as e:
                logger.error("Failed to generate presigned S3 view link: %s", e)
                return ""

        # Local fallback execution
        if stored_path_or_url.startswith("http"):
            return stored_path_or_url
        if stored_path_or_url.startswith(cls.PUBLIC_PREFIX):
            return stored_path_or_url
        return f"{cls.PUBLIC_PREFIX}/{stored_path_or_url.lstrip('/')}"

    @classmethod
    def save_file(
        cls,
        upload_file: UploadFile,
        folder: str,
        filename: str,
    ) -> tuple[str, str, int]:
        extension = Path(upload_file.filename or "").suffix
        stored_filename = f"{filename}{extension}"
        key = cls._object_key(folder, stored_filename)

        upload_file.file.seek(0)

        if cls._use_s3():
            body = upload_file.file.read()
            cls._s3_client().put_object(
                Bucket=settings.S3_BUCKET,
                Key=key,
                Body=body,
                ContentType=upload_file.content_type or "application/octet-stream",
            )
            # 💡 Save only the clean storage key paths to DB rather than hardcoded URLs
            return key, stored_filename, len(body)

        upload_folder = cls.BASE_UPLOAD_DIR / folder
        cls.create_directory(upload_folder)
        destination = upload_folder / stored_filename
        with destination.open("wb") as buffer:
            shutil.copyfileobj(upload_file.file, buffer)

        file_size = destination.stat().st_size
        file_url = f"{cls.PUBLIC_PREFIX}/{key}"
        return file_url, stored_filename, file_size

    @classmethod
    def delete_file(cls, file_url: str) -> None:
        if not file_url:
            return
        key = cls._key_from_url(file_url)
        if key and cls._use_s3():
            try:
                cls._s3_client().delete_object(Bucket=settings.S3_BUCKET, Key=key)
            except Exception as e:
                logger.warning("Failed to delete private object: %s", e)
        cls._delete_local_file(file_url)

    @classmethod
    def _delete_local_file(cls, file_url: str) -> None:
        key = cls._key_from_url(file_url)
        if not key:
            return
        file_path = cls.BASE_UPLOAD_DIR / key
        if file_path.exists() and file_path.is_file():
            file_path.unlink()

    @classmethod
    def replace_file(cls, old_file: str, upload_file: UploadFile, folder: str, filename: str):
        cls.delete_file(old_file)
        return cls.save_file(upload_file, folder, filename)
