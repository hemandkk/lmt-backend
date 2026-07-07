from pathlib import Path
from uuid import uuid4
import shutil

from fastapi import UploadFile


class FileStorage:

    BASE_UPLOAD_DIR = Path("app/uploads")

    @classmethod
    def create_directory(
        cls,
        folder: Path,
    ) -> None:

        folder.mkdir(
            parents=True,
            exist_ok=True,
        )

    @classmethod
    def save_file(
        cls,
        upload_file: UploadFile,
        folder: str,
        filename: str,
    ) -> tuple[str, str, int]:

        """
        Returns

        file_url
        stored_filename
        file_size
        """

        extension = Path(
            upload_file.filename
        ).suffix

        stored_filename = (
            f"{filename}{extension}"
        )

        upload_folder = (
            cls.BASE_UPLOAD_DIR / folder
        )

        cls.create_directory(
            upload_folder
        )

        destination = (
            upload_folder / stored_filename
        )

        with destination.open("wb") as buffer:

            shutil.copyfileobj(
                upload_file.file,
                buffer,
            )

        file_size = destination.stat().st_size

        file_url = str(destination).replace(
            "\\",
            "/",
        )

        return (
            file_url,
            stored_filename,
            file_size,
        )

    @classmethod
    def delete_file(
        cls,
        file_url: str,
    ):

        file_path = Path(file_url)

        if file_path.exists():

            file_path.unlink()

    @classmethod
    def replace_file(
        cls,
        old_file: str,
        upload_file: UploadFile,
        folder: str,
        filename: str,
    ):

        cls.delete_file(
            old_file
        )

        return cls.save_file(
            upload_file,
            folder,
            filename,
        )