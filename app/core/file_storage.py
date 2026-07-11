from pathlib import Path
import shutil

from fastapi import UploadFile


class FileStorage:
    BASE_UPLOAD_DIR = Path("app/uploads")
    PUBLIC_PREFIX = "/uploads"

    @classmethod
    def create_directory(cls, folder: Path) -> None:
        folder.mkdir(parents=True, exist_ok=True)

    @classmethod
    def save_file(
        cls,
        upload_file: UploadFile,
        folder: str,
        filename: str,
    ) -> tuple[str, str, int]:
        """
        Returns (public_file_url, stored_filename, file_size).
        Public URL is served via StaticFiles mount at /uploads.
        """
        extension = Path(upload_file.filename or "").suffix
        stored_filename = f"{filename}{extension}"

        upload_folder = cls.BASE_UPLOAD_DIR / folder
        cls.create_directory(upload_folder)

        destination = upload_folder / stored_filename
        with destination.open("wb") as buffer:
            shutil.copyfileobj(upload_file.file, buffer)

        file_size = destination.stat().st_size
        file_url = f"{cls.PUBLIC_PREFIX}/{folder.strip('/')}/{stored_filename}"

        return file_url, stored_filename, file_size

    @classmethod
    def delete_file(cls, file_url: str) -> None:
        if not file_url:
            return

        # Accept both /uploads/... and app/uploads/...
        relative = file_url
        if relative.startswith(cls.PUBLIC_PREFIX):
            relative = relative[len(cls.PUBLIC_PREFIX) :].lstrip("/")
            file_path = cls.BASE_UPLOAD_DIR / relative
        else:
            file_path = Path(file_url)

        if file_path.exists() and file_path.is_file():
            file_path.unlink()

    @classmethod
    def replace_file(
        cls,
        old_file: str,
        upload_file: UploadFile,
        folder: str,
        filename: str,
    ):
        cls.delete_file(old_file)
        return cls.save_file(upload_file, folder, filename)
