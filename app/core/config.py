from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    SECRET_KEY: str = Field(
        validation_alias="JWT_SECRET_KEY",
        min_length=32,
    )

    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        validation_alias="JWT_EXPIRE_MINUTES"
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        default=7,
        validation_alias="JWT_REFRESH_EXPIRE_DAYS"
    )
    DATABASE_URL: str
    UPLOAD_DIR: str = "app/uploads"
    
    CORS_ORIGINS: str = ""


    # Public base URL for building absolute document/receipt links in Sheets
    APP_BASE_URL: str = Field(default="http://localhost:8000")

    # File storage: "local" (disk + /uploads) or "s3" (S3/R2)
    STORAGE_BACKEND: str = Field(default="local")
    S3_BUCKET: str | None = Field(default=None)
    S3_REGION: str = Field(default="auto")
    S3_ENDPOINT_URL: str | None = Field(default=None)
    S3_ACCESS_KEY_ID: str | None = Field(default=None)
    S3_SECRET_ACCESS_KEY: str | None = Field(default=None)
    S3_PUBLIC_BASE_URL: str | None = Field(
        default=None,
        description="Public HTTPS base for object URLs, e.g. https://files.example.com",
    )

    # Google Sheets
    GOOGLE_SHEETS_ENABLED: bool = Field(default=False)
    GOOGLE_SHEETS_SPREADSHEET_ID: str | None = Field(default=None)
    GOOGLE_SHEETS_WORKSHEET_NAME: str = Field(default="Leads")
    GOOGLE_SERVICE_ACCOUNT_FILE: str | None = Field(
        default=None,
        description="Path to service account JSON key file",
    )
    GOOGLE_SERVICE_ACCOUNT_JSON: str | None = Field(
        default=None,
        description="Inline service account JSON (optional alternative to file)",
    )
    GOOGLE_SHEETS_MAX_RETRIES: int = Field(default=3)
    GOOGLE_SHEETS_RETRY_BACKOFF_SECONDS: float = Field(default=1.5)

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()
