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
        return bool(
            settings.S3_BUCKET
            and settings.S3_ACCESS_KEY_ID
            and settings.S3_SECRET_ACCESS_KEY
            and settings.S3_PUBLIC_BASE_URL
        )

    @classmethod
    def _s3_client(cls):
        return boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL or None,
            aws_access_key_id=settings.S3_ACCESS_KEY_ID,
            aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
            region_name=settings.S3_REGION or "auto",
            config=Config(signature_version="s3v4"),
        )

    @classmethod
    def _public_base(cls) -> str:
        return (settings.S3_PUBLIC_BASE_URL or "").rstrip("/")

    @classmethod
    def _object_key(cls, folder: str, stored_filename: str) -> str:
        return f"{folder.strip('/')}/{stored_filename}"

    @classmethod
    def _key_from_url(cls, file_url: str) -> str | None:
        """Derive storage object key from a stored file_url."""
        if not file_url:
            return None

        url = file_url.strip()
        public_base = cls._public_base()

        if public_base and url.startswith(public_base):
            return url[len(public_base) :].lstrip("/")

        if url.startswith(cls.PUBLIC_PREFIX):
            return url[len(cls.PUBLIC_PREFIX) :].lstrip("/")

        if url.startswith("http://") or url.startswith("https://"):
            path = urlparse(url).path.lstrip("/")
            if path.startswith("uploads/"):
                return path[len("uploads/") :]
            return path or None

        # Legacy local path like app/uploads/...
        marker = "uploads/"
        if marker in url.replace("\\", "/"):
            normalized = url.replace("\\", "/")
            return normalized.split(marker, 1)[1].lstrip("/")

        return None

    @classmethod
    def _delete_s3_object(cls, key: str) -> None:
        if not key or not cls._s3_configured():
            return
        try:
            cls._s3_client().delete_object(Bucket=settings.S3_BUCKET, Key=key)
            logger.info("Deleted S3 object key=%s", key)
        except ClientError as exc:
            # Missing object is fine — already gone / never uploaded.
            code = exc.response.get("Error", {}).get("Code", "")
            if code in {"404", "NoSuchKey", "NotFound"}:
                logger.info("S3 object already absent key=%s", key)
                return
            logger.warning("Failed to delete S3 object key=%s: %s", key, exc)

    @classmethod
    def _delete_local_file(cls, file_url: str) -> None:
        if not file_url:
            return

        relative = file_url
        if relative.startswith(cls.PUBLIC_PREFIX):
            relative = relative[len(cls.PUBLIC_PREFIX) :].lstrip("/")
            file_path = cls.BASE_UPLOAD_DIR / relative
        elif relative.startswith("http://") or relative.startswith("https://"):
            key = cls._key_from_url(relative)
            if not key:
                return
            file_path = cls.BASE_UPLOAD_DIR / key
        else:
            file_path = Path(file_url)

        if file_path.exists() and file_path.is_file():
            file_path.unlink()

    @classmethod
    def save_file(
        cls,
        upload_file: UploadFile,
        folder: str,
        filename: str,
    ) -> tuple[str, str, int]:
        """
        Returns (public_file_url, stored_filename, file_size).
        Local: served via StaticFiles at /uploads.
        S3/R2: absolute public URL under S3_PUBLIC_BASE_URL.
        """
        extension = Path(upload_file.filename or "").suffix
        stored_filename = f"{filename}{extension}"
        key = cls._object_key(folder, stored_filename)

        upload_file.file.seek(0)

        if cls._use_s3():
            if not cls._s3_configured():
                raise RuntimeError(
                    "STORAGE_BACKEND=s3 but S3_BUCKET / keys / "
                    "S3_PUBLIC_BASE_URL are not fully configured."
                )
            body = upload_file.file.read()
            cls._s3_client().put_object(
                Bucket=settings.S3_BUCKET,
                Key=key,
                Body=body,
                ContentType=upload_file.content_type or "application/octet-stream",
            )
            file_url = f"{cls._public_base()}/{key}"
            return file_url, stored_filename, len(body)

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
        """Remove the file from object storage and/or local disk."""
        if not file_url:
            return

        key = cls._key_from_url(file_url)

        # Always free remote storage when we can resolve a key and S3 is configured
        # (covers s3-mode URLs, replace_file, and deletes after switching backends).
        if key and (
            cls._use_s3()
            or (
                settings.S3_PUBLIC_BASE_URL
                and file_url.startswith(cls._public_base())
            )
        ):
            cls._delete_s3_object(key)

        cls._delete_local_file(file_url)

    @classmethod
    def replace_file(
        cls,
        old_file: str,
        upload_file: UploadFile,
        folder: str,
        filename: str,
    ):
        # Delete old object first so storage is freed even if the new key differs.
        cls.delete_file(old_file)
        return cls.save_file(upload_file, folder, filename)
